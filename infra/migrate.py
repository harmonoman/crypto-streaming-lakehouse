#!/usr/bin/env python3
"""
infra/migrate.py

Lightweight SQL migration runner.
Executes numbered .sql files from migrations/ in order, skipping already-applied ones.

Usage:
    python infra/migrate.py

Exits 0 on success, 1 on failure.
"""

import os
import re
import sys
from pathlib import Path

import psycopg2


# ── Config ────────────────────────────────────────────────────────────────────

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

GET_APPLIED    = "SELECT version FROM public.schema_migrations;"
RECORD_MIGRATION = "INSERT INTO public.schema_migrations (version) VALUES (%s);"


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection() -> psycopg2.extensions.connection:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
        conn.autocommit = False
        return conn
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Could not connect to Postgres: {exc}", file=sys.stderr)
        sys.exit(1)


# ── Migration files ───────────────────────────────────────────────────────────

def _numeric_prefix(path: Path) -> int:
    """Extract leading integer from filename for correct ordering (001, 002, ..., 010)."""
    match = re.match(r"^(\d+)", path.name)
    if not match:
        print(f"WARNING: Skipping non-numeric migration file: {path.name}", file=sys.stderr)
        return -1
    return int(match.group(1))


def get_migration_files() -> list[Path]:
    """Return .sql files from migrations/ sorted by numeric prefix."""
    files = [
        f for f in MIGRATIONS_DIR.glob("*.sql")
        if re.match(r"^\d+", f.name)
    ]
    files.sort(key=_numeric_prefix)
    if not files:
        print(f"WARNING: No migration files found in {MIGRATIONS_DIR}")
    return files


# ── Runner ────────────────────────────────────────────────────────────────────

def run_migrations(conn: psycopg2.extensions.connection) -> None:

    # Step 1: ensure tracking table exists (own transaction)
    with conn.cursor() as cur:
        cur.execute(CREATE_MIGRATIONS_TABLE)
    conn.commit()

    # Step 2: read applied versions (own cursor scope, clean state after commit)
    with conn.cursor() as cur:
        cur.execute(GET_APPLIED)
        applied = {row[0] for row in cur.fetchall()}

    # Step 3: apply pending migrations
    migration_files = get_migration_files()
    applied_count = 0
    skipped_count = 0

    for path in migration_files:
        version = path.name

        if version in applied:
            print(f"  skip    {version} (already applied)")
            skipped_count += 1
            continue

        print(f"  apply   {version}...")
        sql = path.read_text()

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(RECORD_MIGRATION, (version,))
            conn.commit()
            print(f"  applied {version}")
            applied_count += 1
        except psycopg2.Error as exc:
            conn.rollback()
            print(f"ERROR: Migration {version} failed:\n{exc}", file=sys.stderr)
            sys.exit(1)

    print(f"\nMigrations complete: {applied_count} applied, {skipped_count} skipped.")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    print("Running migrations...")
    conn = get_connection()
    try:
        run_migrations(conn)
    finally:
        conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
