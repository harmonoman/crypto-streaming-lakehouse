"""
tests/integration/test_metabase_mount.py

Validates that docker-compose.yml correctly configures the Metabase container
to access the DuckDB lakehouse file via a volume mount.

These are configuration tests — no live Docker or Metabase instance required.
We parse docker-compose.yml and docs/metabase_setup.md directly.
"""

from pathlib import Path

import yaml

COMPOSE_PATH     = Path("docker-compose.yml")
DOCS_PATH        = Path("docs/metabase_setup.md")
EXPECTED_MOUNT   = "./data:/data"
EXPECTED_DB_PATH = "/data/crypto_lakehouse.duckdb"


# ── Test 1 — Volume mount exists in docker-compose ───────────────────────────

def test_metabase_volume_mount_exists():
    """
    The metabase service in docker-compose.yml must declare:
        volumes:
          - ./data:/data
    """
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    metabase = compose["services"]["metabase"]
    volumes = metabase.get("volumes", [])

    assert EXPECTED_MOUNT in volumes, (
        f"Expected volume '{EXPECTED_MOUNT}' in metabase service, got: {volumes}"
    )


# ── Test 2 — DuckDB file path documented correctly ───────────────────────────

def test_metabase_setup_docs_reference_duckdb_path():
    """
    docs/metabase_setup.md must reference the correct DuckDB file path:
        /data/crypto_lakehouse.duckdb
    """
    assert DOCS_PATH.exists(), f"Expected docs file at {DOCS_PATH}"
    content = DOCS_PATH.read_text()
    assert EXPECTED_DB_PATH in content, (
        f"Expected '{EXPECTED_DB_PATH}' in {DOCS_PATH}"
    )


# ── Test 3 — Mount path convention is correct ────────────────────────────────

def test_volume_mount_uses_relative_host_path():
    """
    The host path in the volume mount must be relative (./data), not absolute.
    Absolute paths like /Users/... are machine-specific and break portability.
    """
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    volumes = compose["services"]["metabase"].get("volumes", [])

    data_mounts = [v for v in volumes if ":/data" in v]
    assert len(data_mounts) == 1, f"Expected exactly one /data mount, got: {data_mounts}"

    host_path = data_mounts[0].split(":")[0]
    assert host_path.startswith("./"), (
        f"Host path must be relative (start with ./), got: '{host_path}'"
    )
