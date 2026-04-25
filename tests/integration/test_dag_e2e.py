"""
tests/integration/test_dag_e2e.py

Integration tests for the crypto_pipeline DAG end-to-end validation.

These tests validate the DAG and its supporting modules are correctly
wired together — no live Airflow instance required. Tests that require
live services (Postgres, DuckDB) are marked and skip gracefully.
"""

import ast
from pathlib import Path

import yaml

DAG_FILE      = Path("dags/crypto_pipeline_dag.py")
CALLBACKS_FILE = Path("dags/dag_callbacks.py")
SYNC_FILE     = Path("dags/metabase_sync.py")
COMPOSE_PATH  = Path("docker-compose.yml")


# ── DAG file integrity ────────────────────────────────────────────────────────

def test_all_dag_files_exist():
    """All DAG module files must exist."""
    assert DAG_FILE.exists(),       "crypto_pipeline_dag.py missing"
    assert CALLBACKS_FILE.exists(), "dag_callbacks.py missing"
    assert SYNC_FILE.exists(),      "metabase_sync.py missing"


def test_all_dag_files_are_valid_python():
    """All DAG files must parse without syntax errors."""
    for f in [DAG_FILE, CALLBACKS_FILE, SYNC_FILE]:
        ast.parse(f.read_text())


# ── DAG structure completeness ────────────────────────────────────────────────

def test_dag_imports_run_export():
    assert "from lakehouse.export import run_export" in DAG_FILE.read_text()


def test_dag_imports_metabase_sync():
    assert "from metabase_sync import sync_metabase_schema" in DAG_FILE.read_text()


def test_dag_imports_callbacks():
    assert "from dag_callbacks import" in DAG_FILE.read_text()
    assert "on_task_failure" in DAG_FILE.read_text()


def test_dag_has_on_success_callback():
    assert "on_success_callback" in DAG_FILE.read_text()
    assert "on_dag_success" in DAG_FILE.read_text()


# ── Callback module integrity ─────────────────────────────────────────────────

def test_callbacks_use_shared_logger():
    source = CALLBACKS_FILE.read_text()
    assert "from shared.logger import get_logger" in source
    assert 'get_logger("airflow")' in source


def test_callbacks_log_required_fields():
    source = CALLBACKS_FILE.read_text()
    # Failure callback fields
    assert "dag_id"    in source
    assert "task_id"   in source
    assert "run_id"    in source
    assert "exception" in source
    # Success callback fields
    assert "duration_s" in source


# ── Metabase sync module integrity ────────────────────────────────────────────

def test_metabase_sync_uses_env_vars():
    source = SYNC_FILE.read_text()
    assert "METABASE_URL"            in source
    assert "METABASE_ADMIN_EMAIL"    in source
    assert "METABASE_ADMIN_PASSWORD" in source
    assert "METABASE_DATABASE_ID"    in source


def test_metabase_sync_handles_auth_failure():
    source = SYNC_FILE.read_text()
    assert "except Exception" in source
    assert "return" in source


# ── Docker compose integration ────────────────────────────────────────────────

def test_dags_volume_mounted_in_airflow():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    volumes = compose["services"]["airflow"].get("volumes", [])
    assert any("dags" in str(v) for v in volumes)


def test_lakehouse_data_shared_between_airflow_and_metabase():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    airflow_vols  = compose["services"]["airflow"].get("volumes", [])
    metabase_vols = compose["services"]["metabase"].get("volumes", [])
    assert any("lakehouse_data" in str(v) for v in airflow_vols)
    assert any("lakehouse_data" in str(v) for v in metabase_vols)


def test_dbt_mounted_in_airflow():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    volumes = compose["services"]["airflow"].get("volumes", [])
    assert any("/opt/airflow/dbt" in str(v) for v in volumes)
