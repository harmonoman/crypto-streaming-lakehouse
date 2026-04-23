"""
tests/unit/test_schema.py

Unit tests for lakehouse/schema.py — written BEFORE implementation (TDD).

Uses an in-memory DuckDB connection so tests are fast, isolated, and
require no filesystem or external services.
"""

from datetime import UTC, datetime

import duckdb
import pytest

from lakehouse.schema import init_ducklake_schema, upsert_export_state


@pytest.fixture
def conn():
    """Fresh in-memory DuckDB connection per test — no state leaks."""
    return duckdb.connect()


# ── Test 1 — Table creation ───────────────────────────────────────────────────

def test_init_creates_export_state_table(conn):
    """
    init_ducklake_schema() must create ducklake.export_state.
    """
    init_ducklake_schema(conn)

    result = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'ducklake' AND table_name = 'export_state'"
    ).fetchone()

    assert result is not None, "ducklake.export_state table was not created"


# ── Test 2 — Schema correctness ───────────────────────────────────────────────

def test_export_state_has_correct_columns(conn):
    """
    export_state must have exactly: table_name, last_exported_at, rows_exported.
    """
    init_ducklake_schema(conn)

    columns = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'ducklake' AND table_name = 'export_state' "
        "ORDER BY column_name"
    ).fetchall()

    column_names = [c[0] for c in columns]
    assert "table_name"       in column_names
    assert "last_exported_at" in column_names
    assert "rows_exported"    in column_names
    assert len(column_names) == 3


# ── Test 3 — Idempotency ──────────────────────────────────────────────────────

def test_init_is_idempotent(conn):
    """
    Calling init_ducklake_schema() twice must not raise or duplicate the table.
    """
    init_ducklake_schema(conn)
    init_ducklake_schema(conn)  # must not raise

    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'ducklake' AND table_name = 'export_state'"
    ).fetchone()[0]

    assert result == 1


# ── Test 4 — Upsert behavior ──────────────────────────────────────────────────

def test_upsert_inserts_new_row(conn):
    """
    upsert_export_state() must insert a row when table_name doesn't exist.
    """
    init_ducklake_schema(conn)

    ts = datetime(2026, 4, 23, 15, 0, 0, tzinfo=UTC)
    upsert_export_state(conn, "gold_vwap_1min", last_exported_at=ts, rows_exported=27)

    row = conn.execute(
        "SELECT table_name, rows_exported FROM ducklake.export_state "
        "WHERE table_name = 'gold_vwap_1min'"
    ).fetchone()

    assert row is not None
    assert row[0] == "gold_vwap_1min"
    assert row[1] == 27


def test_upsert_updates_existing_row(conn):
    """
    upsert_export_state() must update (not duplicate) an existing row.
    """
    init_ducklake_schema(conn)

    ts1 = datetime(2026, 4, 23, 15, 0, 0, tzinfo=UTC)
    ts2 = datetime(2026, 4, 23, 16, 0, 0, tzinfo=UTC)

    upsert_export_state(conn, "gold_vwap_1min", last_exported_at=ts1, rows_exported=27)
    upsert_export_state(conn, "gold_vwap_1min", last_exported_at=ts2, rows_exported=54)

    row = conn.execute(
        "SELECT rows_exported, last_exported_at FROM ducklake.export_state "
        "WHERE table_name = 'gold_vwap_1min'"
    ).fetchone()
    assert row[0] == 54
    assert row[1] is not None  # last_exported_at was updated


def test_upsert_tracks_multiple_tables_independently(conn):
    """
    Each table_name is tracked as a separate row.
    """
    init_ducklake_schema(conn)

    ts = datetime(2026, 4, 23, 15, 0, 0, tzinfo=UTC)
    upsert_export_state(conn, "gold_vwap_1min",        last_exported_at=ts, rows_exported=27)
    upsert_export_state(conn, "gold_trade_stats_1min", last_exported_at=ts, rows_exported=27)

    count = conn.execute(
        "SELECT COUNT(*) FROM ducklake.export_state"
    ).fetchone()[0]

    assert count == 2

def test_upsert_raises_on_naive_datetime(conn):
    """upsert_export_state() must reject timezone-naive datetimes."""
    init_ducklake_schema(conn)
    naive_ts = datetime(2026, 4, 23, 15, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="timezone-aware"):
        upsert_export_state(conn, "gold_vwap_1min", last_exported_at=naive_ts, rows_exported=27)
