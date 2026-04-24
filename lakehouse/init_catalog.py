"""
lakehouse/init_catalog.py

Registers Parquet files as DuckDB views for analyst-friendly querying.

Why views?
    Without views, analysts must reference raw file paths every time:
        SELECT * FROM read_parquet('data/gold/gold_vwap_1min/**/*.parquet')
    With views, they write:
        SELECT * FROM vw_vwap_1min
    The view hides the file system complexity behind a stable SQL name.
    If the path ever changes, only this file needs updating — not every
    downstream query.

Why read_parquet() with glob patterns?
    The exporter writes one file per date partition:
        data/gold/gold_vwap_1min/year=2026/month=04/day=23/part-abc.parquet
    The `**/*.parquet` glob reads all files across all partitions and
    presents them as a single virtual table. DuckDB handles the union
    automatically and pushes partition filters down for performance.

Why CREATE OR REPLACE VIEW?
    Idempotency — safe to call on every startup without error or
    stale state. If the view already exists, it is replaced in place.
    No need to check for existence before creating.

Why placeholder Parquet files?
    DuckDB 1.5.x raises IOException when read_parquet() finds no files
    matching a glob pattern — even at view creation time. An empty
    placeholder file ensures the glob always matches, returning zero
    rows rather than raising. Real export files are unaffected since
    the placeholder schema aligns with the actual Gold table schema.

Usage:
    from lakehouse.init_catalog import init_catalog
    init_catalog()                          # uses default paths
    init_catalog(db_path="custom.duckdb")   # custom path for testing
"""

from pathlib import Path

import duckdb
import pandas as pd

_DEFAULT_DB_PATH      = "data/crypto_lakehouse.duckdb"
_DEFAULT_PARQUET_BASE = "data/gold"

# Schema definitions for placeholder files — must match Gold table columns.
_VWAP_COLS        = ["window_start", "vwap", "total_volume", "trade_count", "high_price", "low_price"]
_TRADE_STATS_COLS = ["window_start", "volatility", "buy_count", "sell_count", "buy_volume_pct"]


def _write_placeholder(directory: Path, columns: list) -> None:
    """
    Write an empty Parquet file so read_parquet() glob always finds a match.
    Only written once — skipped if placeholder already exists.
    """
    placeholder = directory / ".placeholder.parquet"
    if not placeholder.exists():
        pd.DataFrame(columns=columns).to_parquet(placeholder, index=False)


def init_catalog(
    db_path: str = _DEFAULT_DB_PATH,
    parquet_base: str = _DEFAULT_PARQUET_BASE,
) -> None:
    """
    Connect to the DuckDB lakehouse and register Gold Parquet files as views.

    Args:
        db_path:      Path to the DuckDB file. Created if it doesn't exist.
        parquet_base: Root directory containing Gold Parquet partitions.
                      Defaults to 'data/gold'.
    """
    # Ensure Gold partition directories exist and contain at least one
    # Parquet file so read_parquet() glob never raises on an empty directory.
    vwap_dir        = Path(parquet_base, "gold_vwap_1min")
    trade_stats_dir = Path(parquet_base, "gold_trade_stats_1min")

    vwap_dir.mkdir(parents=True, exist_ok=True)
    trade_stats_dir.mkdir(parents=True, exist_ok=True)

    _write_placeholder(vwap_dir,        _VWAP_COLS)
    _write_placeholder(trade_stats_dir, _TRADE_STATS_COLS)

    conn = duckdb.connect(db_path)

    # VWAP 1-minute view
    conn.execute(f"""
        CREATE OR REPLACE VIEW vw_vwap_1min AS
        SELECT *
        FROM read_parquet('{parquet_base}/gold_vwap_1min/**/*.parquet',
                          union_by_name=true)
    """)

    # Trade stats 1-minute view
    conn.execute(f"""
        CREATE OR REPLACE VIEW vw_trade_stats_1min AS
        SELECT *
        FROM read_parquet('{parquet_base}/gold_trade_stats_1min/**/*.parquet',
                          union_by_name=true)
    """)

    conn.close()
