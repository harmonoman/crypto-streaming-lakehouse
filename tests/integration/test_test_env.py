"""
tests/integration/test_test_env.py

Validates docker-compose.test.yml — the ephemeral CI test environment.
No live Docker required — parses the config file directly.
"""

from pathlib import Path

import yaml

TEST_COMPOSE = Path("docker-compose.test.yml")


def _load():
    return yaml.safe_load(TEST_COMPOSE.read_text())


# ── Test 1 — File exists ──────────────────────────────────────────────────────

def test_test_compose_file_exists():
    assert TEST_COMPOSE.exists(), f"Expected {TEST_COMPOSE}"


# ── Test 2 — Services defined ─────────────────────────────────────────────────

def test_required_services_defined():
    config = _load()
    services = config["services"]
    assert "postgres"  in services
    assert "rabbitmq" in services


# ── Test 3 — No named volumes ─────────────────────────────────────────────────

def test_no_named_volumes():
    """CI must be stateless — no persistent named volumes."""
    config = _load()
    top_level_volumes = config.get("volumes", {})
    assert len(top_level_volumes) == 0, (
        f"CI compose must have no named volumes, found: {list(top_level_volumes.keys())}"
    )


# ── Test 4 — Healthchecks present ────────────────────────────────────────────

def test_postgres_has_healthcheck():
    config = _load()
    assert "healthcheck" in config["services"]["postgres"]


def test_rabbitmq_has_healthcheck():
    config = _load()
    assert "healthcheck" in config["services"]["rabbitmq"]


# ── Test 5 — Test credentials used ───────────────────────────────────────────

def test_postgres_uses_test_credentials():
    config = _load()
    env = config["services"]["postgres"]["environment"]
    assert env.get("POSTGRES_USER")     == "test_user"
    assert env.get("POSTGRES_DB")       == "test_db"
    assert env.get("POSTGRES_PASSWORD") == "test_pass"


def test_rabbitmq_uses_test_credentials():
    config = _load()
    env = config["services"]["rabbitmq"]["environment"]
    assert env.get("RABBITMQ_DEFAULT_USER") == "test_user"


# ── Test 6 — Ports exposed ────────────────────────────────────────────────────

def test_postgres_port_exposed():
    config = _load()
    ports = config["services"]["postgres"].get("ports", [])
    assert any("5432" in str(p) for p in ports)


def test_rabbitmq_amqp_port_exposed():
    config = _load()
    ports = config["services"]["rabbitmq"].get("ports", [])
    assert any("5672" in str(p) for p in ports)
