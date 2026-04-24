"""
tests/unit/test_init_catalog.py

Unit tests for lakehouse/init_catalog.py — written BEFORE implementation (TDD).

Uses a temporary directory so tests never pollute the real lakehouse database.
"""


import duckdb

from lakehouse.init_catalog import init_catalog

# ── Test 1 — DuckDB file is created ──────────────────────────────────────────

def test_init_catalog_creates_database_file(tmp_path):
    """
    init_catalog() must create the DuckDB file on disk.
    """
    db_path = tmp_path / "crypto_lakehouse.duckdb"
    init_catalog(db_path=str(db_path))
    assert db_path.exists(), f"Expected DuckDB file at {db_path}"


# ── Test 2 — vw_vwap_1min view exists ────────────────────────────────────────

def test_vw_vwap_1min_view_exists(tmp_path):
    """
    After init_catalog(), vw_vwap_1min must be queryable without error.
    Empty result is acceptable — the view just needs to exist.
    """
    db_path = tmp_path / "crypto_lakehouse.duckdb"
    parquet_dir = tmp_path / "gold" / "gold_vwap_1min"
    parquet_dir.mkdir(parents=True)

    init_catalog(db_path=str(db_path), parquet_base=str(tmp_path / "gold"))

    conn = duckdb.connect(str(db_path))
    result = conn.execute("SELECT * FROM vw_vwap_1min LIMIT 1").fetchall()
    conn.close()
    # No exception = view exists and is queryable
    assert isinstance(result, list)


# ── Test 3 — vw_trade_stats_1min view exists ─────────────────────────────────

def test_vw_trade_stats_1min_view_exists(tmp_path):
    """
    After init_catalog(), vw_trade_stats_1min must be queryable without error.
    """
    db_path = tmp_path / "crypto_lakehouse.duckdb"
    parquet_dir = tmp_path / "gold" / "gold_trade_stats_1min"
    parquet_dir.mkdir(parents=True)

    init_catalog(db_path=str(db_path), parquet_base=str(tmp_path / "gold"))

    conn = duckdb.connect(str(db_path))
    result = conn.execute("SELECT * FROM vw_trade_stats_1min LIMIT 1").fetchall()
    conn.close()
    assert isinstance(result, list)


# ── Test 4 — Idempotency ──────────────────────────────────────────────────────

def test_init_catalog_is_idempotent(tmp_path):
    """
    Calling init_catalog() twice must not raise or corrupt the views.
    CREATE OR REPLACE VIEW handles this correctly.
    """
    db_path = tmp_path / "crypto_lakehouse.duckdb"
    parquet_base = str(tmp_path / "gold")

    init_catalog(db_path=str(db_path), parquet_base=parquet_base)
    init_catalog(db_path=str(db_path), parquet_base=parquet_base)  # must not raise

    conn = duckdb.connect(str(db_path))
    # DuckDB 1.5.x uses table_name (not view_name) in information_schema.views
    views = conn.execute(
        "SELECT table_name FROM information_schema.views WHERE table_name LIKE 'vw_%'"
    ).fetchall()
    conn.close()

    view_names = [v[0] for v in views]
    assert "vw_vwap_1min"        in view_names
    assert "vw_trade_stats_1min" in view_names
