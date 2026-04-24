"""
tests/integration/test_metabase_mount.py

Validates that docker-compose.yml correctly configures the Metabase container
to access the DuckDB lakehouse via a named volume mount.

These are configuration tests — no live Docker or Metabase instance required.
We parse docker-compose.yml and docs/metabase_setup.md directly.
"""

from pathlib import Path

import yaml

COMPOSE_PATH     = Path("docker-compose.yml")
DOCS_PATH        = Path("docs/metabase_setup.md")
EXPECTED_VOLUME  = "lakehouse_data:/data"
EXPECTED_DB_PATH = "/data/crypto_lakehouse.duckdb"


# ── Test 1 — Named volume mount exists in docker-compose ─────────────────────

def test_metabase_volume_mount_exists():
    """
    The metabase service must declare the lakehouse_data named volume at /data.
    """
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    metabase = compose["services"]["metabase"]
    volumes = metabase.get("volumes", [])

    assert EXPECTED_VOLUME in volumes, (
        f"Expected volume '{EXPECTED_VOLUME}' in metabase service, got: {volumes}"
    )


# ── Test 2 — DuckDB file path documented correctly ───────────────────────────

def test_metabase_setup_docs_reference_duckdb_path():
    """
    docs/metabase_setup.md must reference the correct DuckDB file path.
    """
    assert DOCS_PATH.exists(), f"Expected docs file at {DOCS_PATH}"
    content = DOCS_PATH.read_text()
    assert EXPECTED_DB_PATH in content, (
        f"Expected '{EXPECTED_DB_PATH}' in {DOCS_PATH}"
    )


# ── Test 3 — Named volume declared in top-level volumes section ───────────────

def test_lakehouse_data_volume_declared():
    """
    lakehouse_data must be declared in the top-level volumes section.
    """
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    top_level_volumes = compose.get("volumes", {})
    assert "lakehouse_data" in top_level_volumes, (
        f"Expected 'lakehouse_data' in top-level volumes, got: {list(top_level_volumes.keys())}"
    )
