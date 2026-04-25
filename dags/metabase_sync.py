"""
dags/metabase_sync.py

Metabase schema sync utility.

Why shared volume replaces docker cp?
    Both Airflow and Metabase mount lakehouse_data:/data. When the lakehouse
    exporter writes a new DuckDB file to /data, Metabase can already read it
    — no file transfer needed. We just need to tell Metabase to refresh.

Why API trigger?
    Metabase caches schema metadata. Without a sync trigger, it may serve
    stale column/table info even though the underlying file changed.

Why env vars?
    URL, credentials, and database ID vary between environments. Never
    hardcode connection details — always read from environment.
"""

import os

import requests

from shared.logger import get_logger

logger = get_logger("airflow")


def sync_metabase_schema() -> None:
    """
    Authenticate with Metabase and trigger a schema sync on the DuckDB database.
    Logs errors but does not raise — a sync failure should not crash the DAG.
    """
    base_url     = os.environ.get("METABASE_URL", "http://metabase:3000")
    email        = os.environ.get("METABASE_ADMIN_EMAIL", "")
    password     = os.environ.get("METABASE_ADMIN_PASSWORD", "")
    database_id  = os.environ.get("METABASE_DATABASE_ID", "2")

    # Step 1 — Authenticate and get session token
    try:
        session_resp = requests.post(
            f"{base_url}/api/session",
            json={"username": email, "password": password},
        )
        session_resp.raise_for_status()
        token = session_resp.json().get("id")
    except Exception as exc:
        logger.error("Metabase authentication failed", extra={"error": str(exc)})
        return

    if not token:
        logger.error("Metabase auth succeeded but no session token returned")
        return

    # Step 2 — Trigger schema sync
    try:
        sync_resp = requests.post(
            f"{base_url}/api/database/{database_id}/sync_schema",
            headers={"X-Metabase-Session": token},
        )
        sync_resp.raise_for_status()
        logger.info(
            "Metabase schema sync triggered",
            extra={"database_id": database_id},
        )
    except Exception as exc:
        logger.error("Metabase schema sync failed", extra={"error": str(exc)})
