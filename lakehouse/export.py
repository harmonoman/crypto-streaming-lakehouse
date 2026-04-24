"""
lakehouse/export.py

Orchestrates the full lakehouse export pipeline:

    1. Initialize DuckDB schema (export_state table)
    2. Read high-water mark for each Gold table
    3. Export new data from Postgres → Parquet (full or incremental)
    4. Update export_state bookmark (only after successful export)
    5. Optionally upload Parquet files to S3
    6. Refresh DuckDB views so analysts see the latest data

Design:
    Each table is exported independently. A failure on one table does not
    prevent other tables from being exported.

    The high-water mark is only updated AFTER a successful Parquet write.
    If the process crashes mid-export, the next run re-exports from the
    last successful checkpoint — no data loss, no corruption.

Usage (manual):
    python lakehouse/export.py

    Environment variables required:
        DATABASE_URL  — Postgres connection string
        DBT_PROFILES_DIR — not needed here, but set in .env

Usage (Airflow):
    from lakehouse.export import run_export
    run_export()
"""

import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from lakehouse.exporter import GoldExporter
from lakehouse.init_catalog import init_catalog
from lakehouse.s3_uploader import upload_file_to_s3
from lakehouse.schema import init_ducklake_schema, upsert_export_state
from shared.logger import get_logger

logger = get_logger("lakehouse")

# ── Configuration ─────────────────────────────────────────────────────────────

GOLD_TABLES   = ["gold_vwap_1min", "gold_trade_stats_1min"]
DB_PATH       = "data/crypto_lakehouse.duckdb"
PARQUET_BASE  = "data"


# ── Core export logic ─────────────────────────────────────────────────────────

def _get_high_water_mark(conn, table: str) -> datetime | None:
    """
    Read the last exported timestamp for a table from export_state.
    Returns None if the table has never been exported (triggers full export).
    """
    row = conn.execute(
        "SELECT last_exported_at FROM ducklake.export_state WHERE table_name = ?",
        [table],
    ).fetchone()
    return row[0] if row else None


def _count_exported_rows(parquet_base: str, table: str) -> int:
    try:
        conn = duckdb.connect()
        count = conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_base}/gold/{table}/**/*.parquet', "
            f"union_by_name=true)"
        ).fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _upload_new_files(parquet_base: str, table: str) -> None:
    """
    Upload all Parquet files for a table to S3 if S3_BUCKET is configured.
    Skips placeholder files.
    """
    table_path = Path(parquet_base) / table
    if not table_path.exists():
        return

    for parquet_file in table_path.rglob("*.parquet"):
        if parquet_file.name == ".placeholder.parquet":
            continue
        upload_file_to_s3(str(parquet_file), parquet_base)


def export_table(duck_conn, exporter: GoldExporter, table: str) -> bool:
    """
    Export a single Gold table from Postgres to Parquet.

    Returns True on success, False on failure.
    export_state is only updated on success.
    """
    try:
        hwm = _get_high_water_mark(duck_conn, table)

        if hwm is None:
            logger.info("Full export starting", extra={"table": table})
            exporter.full_export(table)
        else:
            logger.info(
                "Incremental export starting",
                extra={"table": table, "since": hwm.isoformat()},
            )
            exporter.incremental_export(table, high_water_mark=hwm)

        # Update bookmark — only after successful Parquet write
        new_hwm = datetime.now(UTC)
        rows    = _count_exported_rows(PARQUET_BASE, table)
        upsert_export_state(duck_conn, table, last_exported_at=new_hwm, rows_exported=rows)

        logger.info(
            "Export complete",
            extra={"table": table, "rows_exported": rows, "new_hwm": new_hwm.isoformat()},
        )

        # Optional S3 upload — failure here does not affect export success
        _upload_new_files(PARQUET_BASE, table)

        return True

    except Exception as exc:
        logger.error(
            "Export failed",
            extra={"table": table, "error": str(exc)},
        )
        return False


# ── Main entrypoint ───────────────────────────────────────────────────────────

def run_export() -> None:
    """
    Run the full lakehouse export pipeline for all Gold tables.

    Called directly (manual run) or from an Airflow PythonOperator.
    """
    pg_conn_str = os.environ["DATABASE_URL"]

    # Ensure output directories and DuckDB schema exist
    Path(PARQUET_BASE).mkdir(parents=True, exist_ok=True)
    duck_conn = duckdb.connect(DB_PATH)
    init_ducklake_schema(duck_conn)

    exporter = GoldExporter(pg_conn_str=pg_conn_str, output_path=PARQUET_BASE)

    results = {}
    for table in GOLD_TABLES:
        results[table] = export_table(duck_conn, exporter, table)

    duck_conn.close()

    # Refresh DuckDB views so analysts see the latest data
    init_catalog(db_path=DB_PATH, parquet_base=PARQUET_BASE)

    # Summary
    passed  = [t for t, ok in results.items() if ok]
    failed  = [t for t, ok in results.items() if not ok]

    logger.info("Export run complete", extra={"passed": passed, "failed": failed})

    if failed:
        raise RuntimeError(f"Export failed for tables: {failed}")


if __name__ == "__main__":
    run_export()
