"""
tests/integration/test_metabase_queries.py

Validates the 4 Metabase dashboard SQL queries against a real DuckDB connection.

Tests use an in-memory DuckDB with seeded fixture data — so tests pass
in CI without a running pipeline or live lakehouse file.
"""

from datetime import UTC, datetime, timedelta

import duckdb
import pandas as pd
import pytest

# ── Fixture: seeded in-memory DuckDB with views ───────────────────────────────

@pytest.fixture
def conn():
    """
    In-memory DuckDB with vw_vwap_1min and vw_trade_stats_1min views
    backed by seeded DataFrames. Mirrors the production view schema exactly.
    """
    c = duckdb.connect()

    now = datetime.now(UTC)
    windows = [now - timedelta(minutes=i) for i in range(10, 0, -1)]

    vwap_df = pd.DataFrame({
        "window_start": windows,
        "vwap":         [77800.0 + i * 10 for i in range(10)],
        "total_volume": [0.5 + i * 0.1 for i in range(10)],
        "trade_count":  [30 + i for i in range(10)],
        "high_price":   [77850.0 + i * 10 for i in range(10)],
        "low_price":    [77750.0 + i * 10 for i in range(10)],
    })

    stats_df = pd.DataFrame({
        "window_start":  windows,
        "volatility":    [50.0 + i * 5 for i in range(10)],
        "buy_count":     [20 + i for i in range(10)],
        "sell_count":    [10 + i for i in range(10)],
        "buy_volume_pct":[60.0 + i for i in range(10)],
    })

    c.register("vwap_data",  vwap_df)
    c.register("stats_data", stats_df)

    c.execute("CREATE VIEW vw_vwap_1min AS SELECT * FROM vwap_data")
    c.execute("CREATE VIEW vw_trade_stats_1min AS SELECT * FROM stats_data")

    return c


# ── Test 1 — VWAP query returns expected columns ──────────────────────────────

def test_vwap_query_returns_expected_columns(conn):
    """Chart 1: VWAP over time must return window_start and vwap."""
    result = conn.execute("""
        SELECT window_start, vwap
        FROM vw_vwap_1min
        WHERE window_start > NOW() - INTERVAL '60 minutes'
        ORDER BY window_start
    """).fetchdf()

    assert list(result.columns) == ["window_start", "vwap"]
    assert len(result) > 0


# ── Test 2 — Volume query returns total_volume ────────────────────────────────

def test_volume_query_returns_expected_columns(conn):
    """Chart 2: Trade volume per minute must return window_start and total_volume."""
    result = conn.execute("""
        SELECT window_start, total_volume
        FROM vw_vwap_1min
        WHERE window_start > NOW() - INTERVAL '60 minutes'
        ORDER BY window_start
    """).fetchdf()

    assert list(result.columns) == ["window_start", "total_volume"]
    assert len(result) > 0


# ── Test 3 — Buy/Sell ratio returns percentages ───────────────────────────────

def test_buy_sell_ratio_query_returns_expected_columns(conn):
    """
    Chart 3: Buy vs sell ratio must return window_start, buy_volume_pct,
    and sell_volume_pct. buy + sell must always sum to 100.
    """
    result = conn.execute("""
        SELECT
            window_start,
            buy_volume_pct,
            (100 - buy_volume_pct) AS sell_volume_pct
        FROM vw_trade_stats_1min
        WHERE window_start > NOW() - INTERVAL '60 minutes'
        ORDER BY window_start
    """).fetchdf()

    assert list(result.columns) == ["window_start", "buy_volume_pct", "sell_volume_pct"]
    assert len(result) > 0
    assert ((result["buy_volume_pct"] + result["sell_volume_pct"]) - 100).abs().max() < 0.001


# ── Test 4 — Volatility query returns volatility column ──────────────────────

def test_volatility_query_returns_expected_columns(conn):
    """Chart 4: Volatility over time must return window_start and volatility."""
    result = conn.execute("""
        SELECT window_start, volatility
        FROM vw_trade_stats_1min
        WHERE window_start > NOW() - INTERVAL '60 minutes'
        ORDER BY window_start
    """).fetchdf()

    assert list(result.columns) == ["window_start", "volatility"]
    assert len(result) > 0


# ── Test 5 — Time filter excludes old data ────────────────────────────────────

def test_time_filter_excludes_old_data(conn):
    """
    Queries must exclude data older than 60 minutes.
    Seed an old row and assert it does not appear in results.
    """
    old_time = datetime.now(UTC) - timedelta(hours=2)
    old_df = pd.DataFrame({
        "window_start": [old_time],
        "vwap":         [99999.0],
        "total_volume": [999.0],
        "trade_count":  [999],
        "high_price":   [99999.0],
        "low_price":    [99999.0],
    })
    conn.register("old_data", old_df)
    conn.execute(
        "CREATE OR REPLACE VIEW vw_vwap_1min AS "
        "SELECT * FROM vwap_data UNION ALL SELECT * FROM old_data"
    )

    result = conn.execute("""
        SELECT window_start, vwap
        FROM vw_vwap_1min
        WHERE window_start > NOW() - INTERVAL '60 minutes'
        ORDER BY window_start
    """).fetchdf()

    assert 99999.0 not in result["vwap"].values
