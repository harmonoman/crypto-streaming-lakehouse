# Metabase Setup — DuckDB Lakehouse Connection

Metabase connects to the DuckDB lakehouse via a volume mount that makes the
local `data/` directory visible inside the container at `/data`.

---

## Why a Volume Mount?

Containers are isolated — they can't see your local filesystem by default.
A volume mount cuts a window in that wall: the `./data` folder on your machine
becomes `/data` inside the Metabase container. Metabase can then open the
DuckDB file at that path as if it were a local file.

```yaml
# docker-compose.yml — metabase service
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

## Notes

- Run `python lakehouse/export.py` after each `dbt run` to refresh the data
- The DuckDB file is recreated automatically if deleted — just re-run `python lakehouse/export.py`
- The `./data` directory is gitignored — it contains generated runtime files only

---

## DuckDB Driver

The standard Metabase image does not include the DuckDB driver. This project
uses a custom Dockerfile (`docker/metabase.Dockerfile`) based on
`eclipse-temurin:21-jre` (Debian) which pre-installs the driver from:
https://github.com/motherduckdb/metabase_duckdb_driver/releases/download/1.5.2.0/duckdb.metabase-driver.jar

The driver is baked into the image at build time — no manual installation needed.

---

## Dashboard Reference Export

A reference copy of the dashboard configuration is saved at:
metabase/dashboard_export.json

This file was exported via the Metabase API and contains the dashboard layout
and chart configurations for the **BTC-USD Live Dashboard**.

> **Note:** Metabase OSS does not support JSON dashboard import.
> To recreate the dashboard in a fresh instance, use the SQL queries in
> `docs/metabase_queries.sql` to manually recreate the 4 questions, then
> add them to a new dashboard.
