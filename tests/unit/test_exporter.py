"""
tests/unit/test_exporter.py

Unit tests for GoldExporter — written BEFORE implementation (TDD).

Tests are isolated: no live Postgres, no live DuckDB disk I/O.
We mock the DuckDB connection so tests run fast and deterministically.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from lakehouse.exporter import GoldExporter

PG_CONN = "postgresql://user:pass@localhost:5432/crypto_pipeline"
OUTPUT  = "/tmp/test_lakehouse_output"


@pytest.fixture
def exporter():
    return GoldExporter(pg_conn_str=PG_CONN, output_path=OUTPUT)


@pytest.fixture(autouse=True)
def clean_output(tmp_path):
    """Ensure output directory is clean between tests."""
    yield


# ── Test 1 — full_export issues the correct SQL ───────────────────────────────

def test_full_export_queries_entire_table(exporter):
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchdf.return_value = _empty_df()

    with patch("lakehouse.exporter.duckdb.connect", return_value=mock_conn):
        exporter.full_export("gold_vwap_1min")

    all_sql = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    assert "gold_vwap_1min" in all_sql
    assert "WHERE" not in all_sql.upper().split("GOLD_VWAP_1MIN")[1]


# ── Test 2 — incremental_export filters by high-water mark ────────────────────

def test_incremental_export_filters_by_high_water_mark(exporter):
    """
    incremental_export() must include WHERE window_start > high_water_mark
    in the SQL sent to DuckDB/Postgres.
    """
    hwm = datetime(2026, 4, 23, 15, 0, 0, tzinfo=UTC)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchdf.return_value = _empty_df()

    with patch("lakehouse.exporter.duckdb.connect", return_value=mock_conn):
        exporter.incremental_export("gold_vwap_1min", high_water_mark=hwm)

    # Find the data query call and assert it contains the filter
    all_calls = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    assert "window_start" in all_calls
    assert "2026-04-23" in all_calls  # high_water_mark date appears in query


# ── Test 3 — correct partitioned path structure ───────────────────────────────

def test_full_export_writes_partitioned_parquet(tmp_path):
    """
    full_export() must write Parquet files under:
        {output_path}/gold/{table}/year=YYYY/month=MM/day=DD/part-*.parquet
    """
    exporter = GoldExporter(pg_conn_str=PG_CONN, output_path=str(tmp_path))

    sample_df = pd.DataFrame({
        "window_start": [datetime(2026, 4, 23, 15, 0, tzinfo=UTC)],
        "vwap":         [77853.64],
        "total_volume": [0.5],
        "trade_count":  [42],
        "high_price":   [78000.0],
        "low_price":    [77700.0],
    })

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchdf.return_value = sample_df

    with patch("lakehouse.exporter.duckdb.connect", return_value=mock_conn):
        exporter.full_export("gold_vwap_1min")

    # Assert at least one parquet file exists under the expected partition path
    expected_dir = tmp_path / "gold" / "gold_vwap_1min" / "year=2026" / "month=04" / "day=23"
    parquet_files = list(expected_dir.glob("part-*.parquet"))
    assert len(parquet_files) >= 1, f"Expected parquet in {expected_dir}, found none"


# ── Test 4 — empty result set writes nothing ─────────────────────────────────

def test_full_export_empty_result_writes_no_files(tmp_path):
    """
    If the Gold table is empty, full_export() must not write any Parquet files.
    """
    exporter = GoldExporter(pg_conn_str=PG_CONN, output_path=str(tmp_path))

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchdf.return_value = _empty_df()

    with patch("lakehouse.exporter.duckdb.connect", return_value=mock_conn):
        exporter.full_export("gold_vwap_1min")

    output_dir = tmp_path / "gold" / "gold_vwap_1min"
    parquet_files = list(output_dir.rglob("*.parquet")) if output_dir.exists() else []
    assert len(parquet_files) == 0


# ── Test 5 — invalid table name raises clearly ────────────────────────────────

def test_full_export_invalid_table_raises(exporter):
    """
    full_export() with a table name containing SQL-unsafe characters must raise ValueError.
    """
    with pytest.raises(ValueError, match="Invalid table name"):
        exporter.full_export("gold_vwap; DROP TABLE gold_vwap_1min;--")


# ── Test 6 — repeated full_export does not create duplicate files ─────────────────

def test_full_export_repeated_does_not_duplicate(tmp_path):
    """Calling full_export() twice should not accumulate duplicate files."""
    exporter = GoldExporter(pg_conn_str=PG_CONN, output_path=str(tmp_path))
    sample_df = pd.DataFrame({
        "window_start": [datetime(2026, 4, 23, 15, 0, tzinfo=UTC)],
        "vwap": [77853.64], "total_volume": [0.5],
        "trade_count": [42], "high_price": [78000.0], "low_price": [77700.0],
    })

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchdf.return_value = sample_df

    with patch("lakehouse.exporter.duckdb.connect", return_value=mock_conn):
        exporter.full_export("gold_vwap_1min")
        exporter.full_export("gold_vwap_1min")

    all_parquet = list((tmp_path / "gold" / "gold_vwap_1min").rglob("*.parquet"))
    assert len(all_parquet) == 1


# ── Test 7 — incremental export with empty result writes no files ────────────────

def test_incremental_export_empty_result_writes_no_files(tmp_path):
    """incremental_export() with no new rows must write nothing."""
    exporter = GoldExporter(pg_conn_str=PG_CONN, output_path=str(tmp_path))
    hwm = datetime(2026, 4, 23, 15, 0, 0, tzinfo=UTC)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchdf.return_value = _empty_df()

    with patch("lakehouse.exporter.duckdb.connect", return_value=mock_conn):
        exporter.incremental_export("gold_vwap_1min", high_water_mark=hwm)

    output_dir = tmp_path / "gold" / "gold_vwap_1min"
    parquet_files = list(output_dir.rglob("*.parquet")) if output_dir.exists() else []
    assert len(parquet_files) == 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_df():
    """Return an empty DataFrame with the expected Gold schema."""
    return pd.DataFrame(columns=[
        "window_start", "vwap", "total_volume", "trade_count", "high_price", "low_price"
    ])
