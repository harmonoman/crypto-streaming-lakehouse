"""
lakehouse/schema.py

DuckDB schema initialization and export state management.

Why high-water mark tracking?
    Incremental exports need to know where the last successful export ended.
    Without this, every run would re-export all historical data from Postgres —
    wasteful and increasingly slow as data grows.

Why PRIMARY KEY on table_name?
    Each Gold table has exactly one checkpoint row. PRIMARY KEY enforces this
    at the database level — no duplicates, no ambiguity about which row to read.

Why idempotency?
    Schema initialization may run on every startup. IF NOT EXISTS guards ensure
    this is safe to call repeatedly without error or data loss.

Usage:
    import duckdb
    from lakehouse.schema import init_ducklake_schema, upsert_export_state

    conn = duckdb.connect("lakehouse.duckdb")
    init_ducklake_schema(conn)
    upsert_export_state(conn, "gold_vwap_1min", last_exported_at=ts, rows_exported=27)
"""

from datetime import datetime


def init_ducklake_schema(conn) -> None:
    """
    Create the ducklake schema and export_state table if they don't exist.

    Safe to call multiple times — CREATE IF NOT EXISTS guards are idempotent.
    """
    conn.execute("CREATE SCHEMA IF NOT EXISTS ducklake")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ducklake.export_state (
            table_name       TEXT PRIMARY KEY,
            last_exported_at TIMESTAMPTZ,
            rows_exported    BIGINT
        )
    """)


def upsert_export_state(
    conn,
    table_name: str,
    last_exported_at: datetime,
    rows_exported: int,
) -> None:
    """
    Insert or update the export checkpoint for a Gold table.

    Uses DuckDB's ON CONFLICT DO UPDATE (upsert) to atomically update
    the row if it exists, or insert it if it doesn't.

    This must only be called AFTER a successful export — never before —
    to ensure the checkpoint reflects actual exported data.
    """
    if last_exported_at.tzinfo is None:
        raise ValueError("last_exported_at must be timezone-aware (UTC)")

    conn.execute("""
        INSERT INTO ducklake.export_state (table_name, last_exported_at, rows_exported)
        VALUES (?, ?, ?)
        ON CONFLICT (table_name)
        DO UPDATE SET
            last_exported_at = excluded.last_exported_at,
            rows_exported    = excluded.rows_exported
    """, [table_name, last_exported_at, rows_exported])
