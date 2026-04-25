# Airflow Setup — Crypto Pipeline Orchestration

Airflow orchestrates the full pipeline refresh on a schedule, replacing the
manual run sequence with an automated DAG.

---

## Why Airflow?

The pipeline refresh currently requires running these commands manually:

```bash
cd dbt && dbt run && dbt test && cd ..
python lakehouse/export.py
```

Airflow automates this entire sequence on a configurable schedule (default: hourly).

---

## First-Time Setup

Airflow requires a one-time database initialization before the UI is accessible.
This only needs to run once per fresh environment.

**Step 1 — Start the services:**

```bash
docker compose up -d postgres
docker compose up -d airflow airflow-scheduler
```

**Step 2 — Wait for containers to be healthy** (~60 seconds), then run:

```bash
./infra/init_airflow.sh
```

**Step 3 — Open the UI:**
http://localhost:8080

Login with:
- **Username:** admin
- **Password:** value of `AIRFLOW_ADMIN_PASSWORD` in your `.env`

---

## Environment Variables

Add these to your `.env` file:

```bash
AIRFLOW_FERNET_KEY=    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
AIRFLOW_SECRET_KEY=    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
AIRFLOW_ADMIN_PASSWORD= # Your chosen admin password
```

---

## DAG Schedule

The `crypto_pipeline` DAG runs hourly and executes:
dbt_run → dbt_test → lakehouse_export → sync_metabase

---

## Notes

- `infra/init_airflow.sh` only needs to run once — re-running is safe but unnecessary
- Airflow metadata is stored in a dedicated `airflow` database in Postgres
- The `lakehouse_data` volume is shared between Airflow and Metabase — no manual `docker cp` needed
- The `airflow-init` container automatically runs database migrations on every `docker compose up` — the init script only needs to run once to create the admin user
