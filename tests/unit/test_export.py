"""
tests/unit/test_export.py

Unit tests for lakehouse/export.py — the full export orchestration.

All external dependencies (DuckDB, GoldExporter, S3, catalog) are mocked
so tests run fast with no live services required.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from lakehouse.export import (
    _get_high_water_mark,
    export_table,
    run_export,
)

# ── _get_high_water_mark ──────────────────────────────────────────────────────

def test_get_high_water_mark_returns_none_when_no_row():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    result = _get_high_water_mark(conn, "gold_vwap_1min")
    assert result is None


def test_get_high_water_mark_returns_timestamp_when_row_exists():
    ts = datetime(2026, 4, 24, 15, 0, 0, tzinfo=UTC)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (ts,)
    result = _get_high_water_mark(conn, "gold_vwap_1min")
    assert result == ts


# ── export_table ──────────────────────────────────────────────────────────────

def test_export_table_calls_full_export_when_no_hwm():
    """No high-water mark → full_export() must be called."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None  # no HWM

    exporter = MagicMock()

    with patch("lakehouse.export.upsert_export_state"), \
         patch("lakehouse.export._count_exported_rows", return_value=75), \
         patch("lakehouse.export._upload_new_files"):
        result = export_table(conn, exporter, "gold_vwap_1min")

    exporter.full_export.assert_called_once_with("gold_vwap_1min")
    exporter.incremental_export.assert_not_called()
    assert result is True


def test_export_table_calls_incremental_export_when_hwm_exists():
    """High-water mark present → incremental_export() must be called."""
    ts = datetime(2026, 4, 24, 15, 0, 0, tzinfo=UTC)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (ts,)

    exporter = MagicMock()

    with patch("lakehouse.export.upsert_export_state"), \
         patch("lakehouse.export._count_exported_rows", return_value=10), \
         patch("lakehouse.export._upload_new_files"):
        result = export_table(conn, exporter, "gold_vwap_1min")

    exporter.incremental_export.assert_called_once_with("gold_vwap_1min", high_water_mark=ts)
    exporter.full_export.assert_not_called()
    assert result is True


def test_export_table_updates_bookmark_after_success():
    """upsert_export_state must be called after a successful export."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    exporter = MagicMock()

    with patch("lakehouse.export.upsert_export_state") as mock_upsert, \
         patch("lakehouse.export._count_exported_rows", return_value=42), \
         patch("lakehouse.export._upload_new_files"):
        export_table(conn, exporter, "gold_vwap_1min")

    mock_upsert.assert_called_once()
    call_kwargs = mock_upsert.call_args
    assert call_kwargs[0][1] == "gold_vwap_1min"  # table name
    assert call_kwargs[1]["rows_exported"] == 42


def test_export_table_returns_false_on_exception():
    """If the exporter raises, export_table must catch it and return False."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    exporter = MagicMock()
    exporter.full_export.side_effect = Exception("DuckDB connection failed")

    result = export_table(conn, exporter, "gold_vwap_1min")
    assert result is False


def test_export_table_does_not_update_bookmark_on_failure():
    """Bookmark must NOT be updated if export raises."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    exporter = MagicMock()
    exporter.full_export.side_effect = Exception("failure")

    with patch("lakehouse.export.upsert_export_state") as mock_upsert:
        export_table(conn, exporter, "gold_vwap_1min")

    mock_upsert.assert_not_called()


# ── run_export ────────────────────────────────────────────────────────────────

def test_run_export_raises_on_any_table_failure():
    with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), \
         patch("lakehouse.export.Path.mkdir"), \
         patch("lakehouse.export.duckdb.connect"), \
         patch("lakehouse.export.init_ducklake_schema"), \
         patch("lakehouse.export.GoldExporter"), \
         patch("lakehouse.export.export_table", return_value=False), \
         patch("lakehouse.export.init_catalog"), \
         pytest.raises(RuntimeError, match="Export failed for tables"):
        run_export()


def test_run_export_succeeds_when_all_tables_pass():
    """run_export() must not raise when all tables export successfully."""
    with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), \
         patch("lakehouse.export.Path.mkdir"), \
         patch("lakehouse.export.duckdb.connect"), \
         patch("lakehouse.export.init_ducklake_schema"), \
         patch("lakehouse.export.GoldExporter"), \
         patch("lakehouse.export.export_table", return_value=True), \
         patch("lakehouse.export.init_catalog"):
        run_export()  # must not raise


def test_run_export_calls_init_catalog_after_export():
    """init_catalog() must always be called after exports complete."""
    with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), \
         patch("lakehouse.export.Path.mkdir"), \
         patch("lakehouse.export.duckdb.connect"), \
         patch("lakehouse.export.init_ducklake_schema"), \
         patch("lakehouse.export.GoldExporter"), \
         patch("lakehouse.export.export_table", return_value=True), \
         patch("lakehouse.export.init_catalog") as mock_catalog:
        run_export()

    mock_catalog.assert_called_once()
