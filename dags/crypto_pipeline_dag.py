"""
dags/crypto_pipeline_dag.py

Crypto pipeline DAG — orchestrates the full data refresh pipeline on a schedule.

Pipeline flow:
    dbt_run → dbt_test → lakehouse_export → sync_metabase

Why strict ordering?
    Each step depends on the previous one being correct:
    - dbt_test only runs if dbt_run succeeded (no point testing broken models)
    - lakehouse_export only runs if tests passed (no point exporting bad data)
    - sync_metabase only runs if export succeeded (no point refreshing stale views)

Why catchup=False?
    Without this, Airflow would try to backfill every hourly run since
    start_date (2026-01-01) on first boot — potentially thousands of runs.
    catchup=False means "only run from now forward".

Why retries=1?
    Transient failures (network blip, brief Postgres lock) should be retried
    once before alerting. More than 1 retry masks real problems.
"""

from datetime import UTC, datetime, timedelta

from airflow import DAG  # type: ignore[import]
from airflow.operators.bash import BashOperator  # type: ignore[import]
from airflow.operators.python import PythonOperator  # type: ignore[import]

from lakehouse.export import run_export
from shared.logger import get_logger

logger = get_logger("airflow")

# ── Stub for sync_metabase — implemented in AIRFLOW-002-T2 ───────────────────

def sync_metabase_schema() -> None:
    """
    Trigger Metabase to re-sync the DuckDB schema after export.
    Full implementation in AIRFLOW-002-T2.
    """
    logger.info("sync_metabase_schema: stub — implemented in AIRFLOW-002-T2")


# ── Default args ──────────────────────────────────────────────────────────────

default_args = {
    "owner":        "data-engineering",
    "retries":      1,
    "retry_delay":  timedelta(minutes=2),
    # on_failure_callback added in AIRFLOW-002-T3
}

# ── DAG definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="crypto_pipeline",
    default_args=default_args,
    description="dbt → lakehouse export → Metabase refresh",
    schedule_interval="@hourly",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["crypto", "pipeline"],
) as dag:

    # Task 1 — Run dbt models (Bronze → Silver → Gold)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt",
    )

    # Task 2 — Run dbt data quality tests
    # Blocks downstream tasks if any test fails — bad data never reaches the lakehouse
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir /opt/airflow/dbt",
    )

    # Task 3 — Export Gold tables to Parquet and update DuckDB views
    lakehouse_export = PythonOperator(
        task_id="lakehouse_export",
        python_callable=run_export,
    )

    # Task 4 — Trigger Metabase schema sync so dashboards see fresh data
    sync_metabase = PythonOperator(
        task_id="sync_metabase",
        python_callable=sync_metabase_schema,
    )

    # ── Dependency chain ──────────────────────────────────────────────────────
    dbt_run >> dbt_test >> lakehouse_export >> sync_metabase
