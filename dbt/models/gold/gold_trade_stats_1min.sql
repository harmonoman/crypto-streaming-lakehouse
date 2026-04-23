{{ config(materialized='table') }}

-- gold_trade_stats_1min.sql
--
-- 1-minute market microstructure statistics for BTC-USD trades.
-- Each row is a one-minute snapshot of market behaviour:
--   volatility     → how erratic prices were within the minute
--   buy/sell counts → directional flow of market participants
--   buy_volume_pct  → what percentage of traded volume was buyer-driven
--
-- Materialized as a table (not incremental) because:
--   - Volatility (STDDEV) requires all rows in the window to be correct
--   - A partial window would produce misleading volatility figures
--   - This model is small enough that a full rebuild is fast


-- ── Step 1: Select trades from Silver ────────────────────────────────────────

with base as (

    select
        traded_at,
        price,
        size,
        side

    from {{ ref('stg_trades') }}

)

-- ── Step 2: Aggregate into 1-minute windows ───────────────────────────────────

select
    date_trunc('minute', traded_at)                         as window_start,

    -- Price volatility: standard deviation of execution prices in the window.
    -- NULL when fewer than 2 trades exist (STDDEV is undefined for n < 2).
    stddev(price)                                           as volatility,

    -- Directional trade counts
    count(*) filter (where side = 'buy')                    as buy_count,
    count(*) filter (where side = 'sell')                   as sell_count,

    -- Buy volume as a percentage of total volume.
    -- Numerator multiplied by 100.0 first to avoid integer division
    -- and make operator precedence explicit.
    (sum(case when side = 'buy' then size else 0 end) * 100.0)
        / nullif(sum(size), 0)                              as buy_volume_pct

from base

group by 1
