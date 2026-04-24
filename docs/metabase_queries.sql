-- docs/metabase_queries.sql
--
-- Dashboard SQL queries for Metabase — powered by DuckDB lakehouse views.
--
-- Why views instead of raw tables?
--   vw_vwap_1min and vw_trade_stats_1min hide file paths and partitioning
--   complexity. Queries are simple, stable, and portable.
--
-- Why the 60-minute filter?
--   Dashboards show recent market activity, not full history.
--   Limiting to 60 minutes keeps queries fast and charts readable.
--
-- Why simple SELECT statements?
--   Simple queries are easy to debug, fast to execute, and impossible to
--   misread. Metabase also renders them as native chart types without issue.
--
-- Usage:
--   Paste each query directly into a Metabase "Native Query" question.
--   Connect to the DuckDB database at /data/crypto_lakehouse.duckdb first.


-- ── Chart 1 — VWAP Over Time ─────────────────────────────────────────────────
-- Shows the Volume Weighted Average Price per minute for the last hour.
-- Use as a Line Chart with window_start on X axis and vwap on Y axis.

SELECT
    window_start,
    vwap
FROM vw_vwap_1min
WHERE window_start > NOW() - INTERVAL '60 minutes'
ORDER BY window_start;


-- ── Chart 2 — Trade Volume Per Minute ────────────────────────────────────────
-- Shows how much BTC traded each minute.
-- Use as a Bar Chart with window_start on X axis and total_volume on Y axis.

SELECT
    window_start,
    total_volume
FROM vw_vwap_1min
WHERE window_start > NOW() - INTERVAL '60 minutes'
ORDER BY window_start;


-- ── Chart 3 — Buy vs Sell Pressure ───────────────────────────────────────────
-- Shows the percentage of volume from buyers vs sellers each minute.
-- sell_volume_pct is derived as (100 - buy_volume_pct) since they always sum to 100%.
-- Use as a Stacked Bar Chart with both pct columns as series.

SELECT
    window_start,
    buy_volume_pct,
    (100 - buy_volume_pct) AS sell_volume_pct
FROM vw_trade_stats_1min
WHERE window_start > NOW() - INTERVAL '60 minutes'
ORDER BY window_start;


-- ── Chart 4 — Price Volatility ────────────────────────────────────────────────
-- Shows the standard deviation of price within each 1-minute window.
-- Higher volatility = more price movement = choppier market.
-- Use as a Line Chart with window_start on X axis and volatility on Y axis.

SELECT
    window_start,
    volatility
FROM vw_trade_stats_1min
WHERE window_start > NOW() - INTERVAL '60 minutes'
ORDER BY window_start;
