"""
lakehouse/exporter.py

Exports Gold tables from Postgres to partitioned Parquet files via DuckDB.

Why DuckDB?
    DuckDB's postgres_scanner reads directly from Postgres over a standard
    connection string — no intermediate CSV, no manual COPY. It parallelises
    reads automatically and writes Parquet natively with Snappy compression.

Why Parquet + partitioning?
    Parquet is columnar — analytical queries (VWAP over a date range) read
    only the columns they need. Date partitioning (year/month/day) means a
    query for "today's VWAP" reads only today's files, not the full history.

Why incremental export?
    Postgres handles live writes constantly. Running a full export every run
    would scan the entire Gold table each time and contend with the writer.
    Incremental export reads only new windows — reducing Postgres load and
    keeping export runs fast regardless of total data size.

Usage:
    from lakehouse.exporter import GoldExporter

    exporter = GoldExporter(
        pg_conn_str=os.environ["DATABASE_URL"],
        output_path="data/gold",
    )
    exporter.full_export("gold_vwap_1min")
    exporter.incremental_export("gold_vwap_1min", high_water_mark=last_run_ts)
"""

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

# Only alphanumeric characters and underscores are safe in table names.
_SAFE_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class GoldExporter:
    """
    Reads Gold tables from Postgres and writes partitioned Parquet files.

    Supports two modes:
      - full_export():        export the entire table (first run / backfill)
      - incremental_export(): export only rows newer than high_water_mark
    """

    def __init__(self, pg_conn_str: str, output_path: str) -> None:
        self.pg_conn_str = pg_conn_str
        self.output_path = Path(output_path)

    # ── Public API ────────────────────────────────────────────────────────────

    def full_export(self, table: str) -> None:
        self._validate_table_name(table)
        table_path = self.output_path / "gold" / table
        if table_path.exists():
            shutil.rmtree(table_path)
        sql = f"SELECT * FROM postgres_scan('{self.pg_conn_str}', 'gold', '{table}')"
        self._export(table, sql)

    def incremental_export(self, table: str, high_water_mark: datetime) -> None:
        """
        Export only rows with window_start > high_water_mark.

        Use this on subsequent runs to avoid re-exporting historical data.
        The high_water_mark is typically the MAX(window_start) from the
        last successful export.
        """
        self._validate_table_name(table)
        hwm_str = high_water_mark.isoformat()
        # Results in: "2026-04-23T15:00:00+00:00" — unambiguous UTC
        sql = f"""
            SELECT *
            FROM postgres_scan('{self.pg_conn_str}', 'gold', '{table}')
            WHERE window_start > '{hwm_str}'::timestamptz
        """
        self._export(table, sql)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _export(self, table: str, sql: str) -> None:
        """
        Execute SQL via DuckDB postgres_scanner and write results to Parquet.
        Partitioned by year/month/day derived from window_start.
        """
        conn = duckdb.connect()
        conn.execute("INSTALL postgres_scanner;")
        conn.execute("LOAD postgres_scanner;")

        df: pd.DataFrame = conn.execute(sql).fetchdf()

        if df.empty:
            return

        # Ensure window_start is datetime so we can extract date parts
        df["window_start"] = pd.to_datetime(df["window_start"], utc=True)

        # Write one Parquet file per unique date partition
        for date, partition_df in df.groupby(df["window_start"].dt.date):
            year  = date.strftime("%Y")
            month = date.strftime("%m")
            day   = date.strftime("%d")

            partition_path = (
                self.output_path
                / "gold"
                / table
                / f"year={year}"
                / f"month={month}"
                / f"day={day}"
            )
            partition_path.mkdir(parents=True, exist_ok=True)

            file_path = partition_path / f"part-{uuid.uuid4()}.parquet"
            partition_df.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)

    def _validate_table_name(self, table: str) -> None:
        """
        Reject table names that contain unsafe characters.
        Prevents SQL injection via the table name parameter.
        """
        if not _SAFE_TABLE_RE.match(table):
            raise ValueError(
                f"Invalid table name: '{table}'. "
                "Only alphanumeric characters and underscores are allowed."
            )
