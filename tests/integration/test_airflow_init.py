"""
tests/integration/test_airflow_init.py

Validates the Airflow initialization script and setup documentation.
No live Airflow required — checks file existence, permissions, and content.
"""

import os
from pathlib import Path

INIT_SCRIPT = Path("infra/init_airflow.sh")
DOCS_PATH   = Path("docs/airflow_setup.md")
ENV_EXAMPLE = Path(".env.example")


# ── Test 1 — Script exists ────────────────────────────────────────────────────

def test_init_script_exists():
    assert INIT_SCRIPT.exists(), f"Expected init script at {INIT_SCRIPT}"


# ── Test 2 — Script is executable ────────────────────────────────────────────

def test_init_script_is_executable():
    assert os.access(INIT_SCRIPT, os.X_OK), f"{INIT_SCRIPT} must be executable (chmod +x)"


# ── Test 3 — Docs exist ───────────────────────────────────────────────────────

def test_airflow_setup_docs_exist():
    assert DOCS_PATH.exists(), f"Expected setup docs at {DOCS_PATH}"


# ── Test 4 — Docs reference the init script ──────────────────────────────────

def test_docs_reference_init_script():
    content = DOCS_PATH.read_text()
    assert "init_airflow.sh" in content


# ── Test 5 — AIRFLOW_ADMIN_PASSWORD in .env.example ──────────────────────────

def test_env_example_has_admin_password():
    assert "AIRFLOW_ADMIN_PASSWORD" in ENV_EXAMPLE.read_text()


def test_init_script_has_set_e():
    assert "set -e" in INIT_SCRIPT.read_text()


def test_init_script_references_correct_container():
    assert "crypto_airflow" in INIT_SCRIPT.read_text()


def test_docs_reference_localhost_url():
    assert "localhost:8080" in DOCS_PATH.read_text()
