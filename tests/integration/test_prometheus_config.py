"""
tests/integration/test_prometheus_config.py

Validates infra/prometheus.yml and docker-compose.yml Prometheus configuration.
No live Prometheus instance required — parses config files directly.
"""

from pathlib import Path

import yaml

PROMETHEUS_CONFIG = Path("infra/prometheus.yml")
COMPOSE_PATH      = Path("docker-compose.yml")


# ── Test 1 — Config file exists ───────────────────────────────────────────────

def test_prometheus_config_file_exists():
    assert PROMETHEUS_CONFIG.exists(), f"Expected config at {PROMETHEUS_CONFIG}"


# ── Test 2 — Valid YAML ───────────────────────────────────────────────────────

def test_prometheus_config_is_valid_yaml():
    config = yaml.safe_load(PROMETHEUS_CONFIG.read_text())
    assert isinstance(config, dict)


# ── Test 3 — Scrape interval is 15s ──────────────────────────────────────────

def test_scrape_interval_is_15s():
    config = yaml.safe_load(PROMETHEUS_CONFIG.read_text())
    assert config["global"]["scrape_interval"] == "15s"


# ── Test 4 — All targets present ─────────────────────────────────────────────

def test_all_scrape_targets_present():
    config = yaml.safe_load(PROMETHEUS_CONFIG.read_text())
    all_targets = []
    for job in config["scrape_configs"]:
        for static in job["static_configs"]:
            all_targets.extend(static["targets"])

    assert "producer:8000"  in all_targets
    assert "consumer:8001"  in all_targets
    assert "rabbitmq:15692" in all_targets


# ── Test 5 — Docker compose includes Prometheus service ───────────────────────

def test_docker_compose_has_prometheus_service():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    assert "prometheus" in compose["services"]

    prometheus = compose["services"]["prometheus"]
    assert any("9090" in str(p) for p in prometheus.get("ports", []))
    assert any("prometheus.yml" in str(v) for v in prometheus.get("volumes", []))


# ── Test 6 — Prometheus on correct network ─────────────────────────────────────

def test_prometheus_on_correct_network():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    networks = compose["services"]["prometheus"].get("networks", [])
    assert "crypto_net" in networks
