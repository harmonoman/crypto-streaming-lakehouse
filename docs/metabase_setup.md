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
  - ./data:/data
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