# Metabase Setup — DuckDB Lakehouse Connection

Metabase connects to the DuckDB lakehouse via a named volume shared with
Airflow. Both containers mount `lakehouse_data:/data` — when Airflow writes
a new DuckDB file, Metabase can read it immediately with no file transfer.

---

## Why a Shared Volume?

Containers are isolated — they can't see each other's filesystems by default.
A named volume cuts a window in that wall: `lakehouse_data` is mounted at
`/data` in both the Metabase and Airflow containers. No `docker cp` needed.

```yaml
# docker-compose.yml — both services mount the same volume
volumes:
  - lakehouse_data:/data
```

---

## DuckDB Connection Setup

**Database File Path:**
/data/crypto_lakehouse.duckdb

**JDBC Connection String (if required):**
jdbc:duckdb:/data/crypto_lakehouse.duckdb

---

## Step-by-Step

1. Open Metabase at http://localhost:3000
2. Go to **Settings → Admin → Databases → Add database**
3. Select **DuckDB** as the database type
4. Set the database file path to `/data/crypto_lakehouse.duckdb`
5. Click **Save**

Once connected, the following views are available:

| View | Description |
|---|---|
| `vw_vwap_1min` | 1-minute Volume Weighted Average Price |
| `vw_trade_stats_1min` | 1-minute volatility, buy/sell counts, volume % |

---

## Data Refresh (Automated via Airflow)

When the `crypto_pipeline` Airflow DAG runs, it automatically:

1. Runs `dbt run` and `dbt test` to refresh Gold tables
2. Runs `lakehouse/export.py` to write new Parquet files and update the DuckDB file
3. Calls the Metabase API to trigger a schema sync — no manual steps needed

**Manual refresh (without Airflow):**

```bash
python lakehouse/export.py
```

Then in Metabase: **Admin → Databases → Crypto Lakehouse → Sync database schema now**

---

## Notes

- The DuckDB file is recreated automatically if deleted — just re-run `python lakehouse/export.py`
- The `./data` directory is gitignored — it contains generated runtime files only
- Schema sync is triggered automatically by the Airflow `sync_metabase` task via the Metabase API

---

## DuckDB Driver

The standard Metabase image does not include the DuckDB driver. This project
uses a custom Dockerfile (`docker/metabase.Dockerfile`) based on
`eclipse-temurin:21-jre` (Debian) which pre-installs the driver from:
https://github.com/motherduckdb/metabase_duckdb_driver/releases/download/1.5.2.0/duckdb.metabase-driver.jar

The driver is baked into the image at build time — no manual installation needed.

---

## ⚠️ After Container Restart

If the Metabase container is recreated, the DuckDB views inside the container
must be re-registered. Run:

```bash
docker exec crypto_metabase python3 -c "
import duckdb
conn = duckdb.connect('/data/crypto_lakehouse.duckdb')
conn.execute(\"CREATE OR REPLACE VIEW vw_vwap_1min AS SELECT * FROM read_parquet('/data/gold/gold_vwap_1min/**/*.parquet', union_by_name=true)\")
conn.execute(\"CREATE OR REPLACE VIEW vw_trade_stats_1min AS SELECT * FROM read_parquet('/data/gold/gold_trade_stats_1min/**/*.parquet', union_by_name=true)\")
conn.close()
"
```

---

## Dashboard Reference Export

A reference copy of the dashboard configuration is saved at:
`metabase/dashboard_export.json`

This file was exported via the Metabase API and contains the dashboard layout
and chart configurations for the **BTC-USD Live Dashboard**.

> **Note:** Metabase OSS does not support JSON dashboard import.
> To recreate the dashboard in a fresh instance, use the SQL queries in
> `docs/metabase_queries.sql` to manually recreate the 4 questions, then
> add them to a new dashboard.
