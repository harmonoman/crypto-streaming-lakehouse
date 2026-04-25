"""
tests/integration/test_airflow_compose.py

Validates that docker-compose.yml correctly configures Airflow
webserver and scheduler services.

No live Airflow required — parses docker-compose.yml directly.
"""

from pathlib import Path

import yaml

COMPOSE_PATH  = Path("docker-compose.yml")
ENV_EXAMPLE   = Path(".env.example")


def _compose():
    return yaml.safe_load(COMPOSE_PATH.read_text())


# ── Test 1 — Airflow webserver exists ─────────────────────────────────────────

def test_airflow_webserver_service_exists():
    assert "airflow" in _compose()["services"]


# ── Test 2 — Airflow scheduler exists ────────────────────────────────────────

def test_airflow_scheduler_service_exists():
    assert "airflow-scheduler" in _compose()["services"]


# ── Test 3 — Port 8080 exposed on localhost ───────────────────────────────────

def test_airflow_port_8080_exposed():
    ports = _compose()["services"]["airflow"].get("ports", [])
    assert any("8080" in str(p) for p in ports)
    assert any("127.0.0.1" in str(p) for p in ports)


# ── Test 4 — DAGs directory mounted ──────────────────────────────────────────

def test_airflow_dags_volume_mounted():
    volumes = _compose()["services"]["airflow"].get("volumes", [])
    assert any("dags" in str(v) and "/opt/airflow/dags" in str(v) for v in volumes)


# ── Test 5 — lakehouse_data volume shared ────────────────────────────────────

def test_airflow_shares_lakehouse_data_volume():
    airflow_vols  = _compose()["services"]["airflow"].get("volumes", [])
    metabase_vols = _compose()["services"]["metabase"].get("volumes", [])
    assert any("lakehouse_data" in str(v) for v in airflow_vols)
    assert any("lakehouse_data" in str(v) for v in metabase_vols)


# ── Test 6 — airflow_logs volume declared ────────────────────────────────────

def test_airflow_logs_volume_declared():
    top_level = _compose().get("volumes", {})
    assert "airflow_logs" in top_level


# ── Test 7 — Environment variables in .env.example ───────────────────────────

def test_env_example_has_airflow_fernet_key():
    content = ENV_EXAMPLE.read_text()
    assert "AIRFLOW_FERNET_KEY" in content


def test_env_example_has_airflow_secret_key():
    content = ENV_EXAMPLE.read_text()
    assert "AIRFLOW_SECRET_KEY" in content


# ── Test 9 — dags directory exists ───────────────────────────────────────────

def test_dags_directory_exists():
    assert Path("dags").exists(), "dags/ directory must exist for Airflow volume mount"


# ── Test 10 — airflow-init service exists ────────────────────────────────────

def test_airflow_init_service_exists():
    assert "airflow-init" in _compose()["services"]


# ── Test 11 — webserver depends on airflow-init ───────────────────────────────

def test_airflow_webserver_depends_on_init():
    depends = _compose()["services"]["airflow"].get("depends_on", {})
    assert "airflow-init" in depends


# ── Test 12 — scheduler depends on airflow-init ───────────────────────────────

def test_airflow_scheduler_depends_on_init():
    depends = _compose()["services"]["airflow-scheduler"].get("depends_on", {})
    assert "airflow-init" in depends


# ── Test 13 — AIRFLOW_ADMIN_PASSWORD in .env.example ─────────────────────────

def test_env_example_has_airflow_admin_password():
    assert "AIRFLOW_ADMIN_PASSWORD" in ENV_EXAMPLE.read_text()
