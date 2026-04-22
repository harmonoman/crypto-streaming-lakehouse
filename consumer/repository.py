"""
consumer/repository.py

Handles inserts into bronze.raw_trades.
Uses ON CONFLICT (trade_id) DO NOTHING for idempotent deduplication.

Every insert is safe to retry — duplicates are silently skipped at the
database level and counted as a metric for observability.

Usage:
    from consumer.repository import TradeRepository

    repo = TradeRepository(conn)
    repo.insert_one(trade_dict)
    repo.insert_batch([trade_dict, trade_dict, ...])
"""

import json
from datetime import UTC, datetime

import psycopg2
from psycopg2.extras import execute_values

from consumer.metrics import duplicates_skipped_total
from shared.logger import get_logger

logger = get_logger("consumer")


class TradeRepository:
    """
    Writes trade messages to bronze.raw_trades.

    Accepts a live psycopg2 connection. Does not manage connection lifecycle —
    that is the caller's responsibility.
    """

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn

    def insert_one(self, trade: dict) -> None:
        """
        Insert a single trade message.

        If the trade_id already exists, the insert is silently skipped
        and duplicates_skipped_total is incremented.
        """
        payload = json.dumps(trade)
        received_at = datetime.now(UTC)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bronze.raw_trades (payload, received_at)
                VALUES (%s, %s)
                ON CONFLICT (trade_id) DO NOTHING
                """,
                (payload, received_at),
            )
            self.conn.commit()

            if cur.rowcount == 0:
                duplicates_skipped_total.inc()
                logger.info(
                    "Duplicate trade skipped",
                    extra={"trade_id": trade.get("trade_id")},
                )

    def insert_batch(self, trades: list[dict]) -> None:
        """
        Insert multiple trade messages in a single statement.

        Duplicates within the batch or against existing rows are silently
        skipped. The difference between attempted and inserted row count
        is recorded as duplicates_skipped_total.
        """
        if not trades:
            return

        received_at = datetime.now(UTC)
        attempted = len(trades)

        # Build parameterized VALUES list — one tuple per trade.
        # psycopg2 execute_values handles flattening and quoting safely.
        rows = [(json.dumps(t), received_at) for t in trades]

        with self.conn.cursor() as cur:
            result = execute_values(
                cur,
                """
                INSERT INTO bronze.raw_trades (payload, received_at)
                VALUES %s
                ON CONFLICT (trade_id) DO NOTHING
                RETURNING trade_id
                """,
                rows,
                fetch=True,
            )
            self.conn.commit()

            inserted = len(result)
            skipped = attempted - inserted

            if skipped > 0:
                duplicates_skipped_total.inc(skipped)
                logger.info(
                    "Duplicate trades skipped in batch",
                    extra={"attempted": attempted, "inserted": inserted, "skipped": skipped},
                )
