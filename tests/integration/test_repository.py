"""
tests/integration/test_repository.py

Integration tests for consumer/repository.py — TradeRepository.

Requires a live Postgres instance with the bronze schema migrated.
Run with DATABASE_URL pointing to a live Postgres:

    TEST_DATABASE_URL="postgresql://..." uv run pytest tests/integration/test_repository.py -v
"""

import os

import psycopg2
import pytest

from consumer.repository import TradeRepository

# Skip all tests in this module if TEST_DATABASE_URL is not set
# or if the connection fails — these are live-service tests only.
pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping repository integration tests",
)


def _make_trade(trade_id="test-trade-001", price="77853.64",
                size="0.01", side="buy"):
    return {
        "trade_id":   trade_id,
        "price":      price,
        "size":       size,
        "side":       side,
        "time":       "2026-04-24T15:00:00Z",
        "product_id": "BTC-USD",
    }


def _setup_schema(conn):
    """Ensure bronze schema and raw_trades table exist for tests."""
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bronze.raw_trades (
                trade_id    TEXT GENERATED ALWAYS AS (payload->>'trade_id') STORED,
                payload     JSONB        NOT NULL,
                received_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                CONSTRAINT raw_trades_trade_id_unique UNIQUE (trade_id)
            )
        """)
    conn.commit()


def _cleanup(conn, *trade_ids):
    """Remove test rows between tests."""
    with conn.cursor() as cur:
        for tid in trade_ids:
            cur.execute(
                "DELETE FROM bronze.raw_trades WHERE trade_id = %s", (tid,)
            )
    conn.commit()


@pytest.fixture(scope="module")
def live_conn():
    """Module-scoped connection using TEST_DATABASE_URL."""
    url = os.environ["TEST_DATABASE_URL"]
    conn = psycopg2.connect(url)
    conn.autocommit = True
    _setup_schema(conn)
    yield conn
    conn.close()


# ── insert_one ────────────────────────────────────────────────────────────────

def test_insert_one_inserts_trade(live_conn):
    repo = TradeRepository(live_conn)
    trade = _make_trade("repo-test-001")
    try:
        repo.insert_one(trade)
        with live_conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM bronze.raw_trades WHERE trade_id = %s",
                ("repo-test-001",),
            )
            row = cur.fetchone()
        assert row is not None
        assert row[0]["trade_id"] == "repo-test-001"
    finally:
        _cleanup(live_conn, "repo-test-001")


def test_insert_one_skips_duplicate(live_conn):
    repo = TradeRepository(live_conn)
    trade = _make_trade("repo-test-002")
    try:
        repo.insert_one(trade)
        repo.insert_one(trade)  # duplicate — must not raise
        with live_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bronze.raw_trades WHERE trade_id = %s",
                ("repo-test-002",),
            )
            count = cur.fetchone()[0]
        assert count == 1
    finally:
        _cleanup(live_conn, "repo-test-002")


# ── insert_batch ──────────────────────────────────────────────────────────────

def test_insert_batch_inserts_multiple_trades(live_conn):
    repo = TradeRepository(live_conn)
    trades = [
        _make_trade("repo-batch-001"),
        _make_trade("repo-batch-002"),
        _make_trade("repo-batch-003"),
    ]
    try:
        repo.insert_batch(trades)
        with live_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bronze.raw_trades WHERE trade_id LIKE 'repo-batch-%'"
            )
            count = cur.fetchone()[0]
        assert count == 3
    finally:
        _cleanup(live_conn, "repo-batch-001", "repo-batch-002", "repo-batch-003")


def test_insert_batch_skips_duplicates(live_conn):
    repo = TradeRepository(live_conn)
    trade = _make_trade("repo-dedup-001")
    try:
        repo.insert_batch([trade])
        repo.insert_batch([trade])  # duplicate — must not raise
        with live_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bronze.raw_trades WHERE trade_id = %s",
                ("repo-dedup-001",),
            )
            count = cur.fetchone()[0]
        assert count == 1
    finally:
        _cleanup(live_conn, "repo-dedup-001")


def test_insert_batch_empty_list_does_nothing(live_conn):
    repo = TradeRepository(live_conn)
    repo.insert_batch([])  # must not raise
