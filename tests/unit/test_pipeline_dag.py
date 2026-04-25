"""
tests/unit/test_pipeline_dag.py

Unit tests for dags/crypto_pipeline_dag.py.

Tests validate DAG structure by parsing the source file directly —
no live Airflow instance or airflow package required in the dev environment.
The DAG is validated at runtime when Airflow loads it from the container.
"""

import ast
from pathlib import Path

DAG_FILE = Path("dags/crypto_pipeline_dag.py")


def _source() -> str:
    return DAG_FILE.read_text()


# ── Test 1 — DAG file exists ──────────────────────────────────────────────────

def test_dag_file_exists():
    assert DAG_FILE.exists(), "dags/crypto_pipeline_dag.py must exist"


# ── Test 2 — DAG file is valid Python ────────────────────────────────────────

def test_dag_file_is_valid_python():
    source = _source()
    ast.parse(source)  # raises SyntaxError if invalid


# ── Test 3 — DAG ID is correct ───────────────────────────────────────────────

def test_dag_id_is_crypto_pipeline():
    assert '"crypto_pipeline"' in _source() or "'crypto_pipeline'" in _source()


# ── Test 4 — All 4 task IDs present ──────────────────────────────────────────

def test_all_task_ids_present():
    source = _source()
    assert "dbt_run"          in source
    assert "dbt_test"         in source
    assert "lakehouse_export" in source
    assert "sync_metabase"    in source


# ── Test 5 — Task dependency chain present ───────────────────────────────────

def test_task_dependency_chain():
    source = _source()
    assert "dbt_run >> dbt_test >> lakehouse_export >> sync_metabase" in source


# ── Test 6 — Schedule is hourly ──────────────────────────────────────────────

def test_schedule_is_hourly():
    assert "@hourly" in _source()


# ── Test 7 — Retry config present ────────────────────────────────────────────

def test_retries_configured():
    assert "retries" in _source()
    assert "retry_delay" in _source()
    assert "timedelta" in _source()


# ── Test 8 — Catchup disabled ────────────────────────────────────────────────

def test_catchup_is_false():
    assert "catchup=False" in _source()


# ── Test 9 — run_export imported from lakehouse.export ───────────────────────

def test_run_export_imported():
    assert "from lakehouse.export import run_export" in _source()


# ── Test 10 — dbt paths correct ──────────────────────────────────────────────

def test_dbt_paths_correct():
    assert "/opt/airflow/dbt" in _source()


# ── Test 11 — BashOperator used for dbt tasks ────────────────────────────────

def test_bash_operator_used_for_dbt():
    assert "BashOperator" in _source()
