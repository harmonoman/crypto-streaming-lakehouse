{{
    config(
        materialized='incremental',
        unique_key='window_start'
    )
}}

-- gold_vwap_1min.sql
--
-- Aggregates individual trades from Silver into 1-minute market summary windows.
-- Each row represents one minute of trading activity for BTC-USD.
--
-- VWAP (Volume Weighted Average Price):
--   The average price paid, weighted by how much was traded at each price.
--   SUM(price * size) / SUM(size) gives larger trades more influence
--   than smaller ones — a more accurate reflection of true market price
--   than a simple average.
--
-- Incremental strategy:
--   On each run, only process trades from windows not yet in this model.
--   Filter on traded_at (not window_start) so late-arriving trades for
--   a window that's already been computed are still captured.


-- ── Step 1: Select trades to process ─────────────────────────────────────────
-- Apply the incremental filter before aggregation to minimise the rows scanned.

with base as (

    select
        traded_at,
        price,
        size

    from {{ ref('stg_trades') }}

    {% if is_incremental() %}
        where traded_at > (
            select coalesce(max(window_start), '1900-01-01'::timestamptz)
            from {{ this }}
        )
    {% endif %}

)

-- ── Step 2: Aggregate into 1-minute windows ───────────────────────────────────

select
    date_trunc('minute', traded_at)                  as window_start,
    sum(price * size) / nullif(sum(size), 0)         as vwap,
    sum(size)                                        as total_volume,
    count(*)                                         as trade_count,
    max(price)                                       as high_price,
    min(price)                                       as low_price

from base

group by 1
