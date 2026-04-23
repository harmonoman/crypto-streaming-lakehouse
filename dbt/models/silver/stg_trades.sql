{{
    config(
        materialized='incremental',
        unique_key='trade_id'
    )
}}

-- stg_trades.sql
--
-- Converts raw JSONB payloads from bronze.raw_trades into typed, deduplicated rows.
-- This is the first clean layer — downstream models never touch JSON again.
--
-- Incremental strategy:
--   On first run (or dbt run --full-refresh): process all rows.
--   On subsequent runs: only process rows newer than the latest ingested_at
--   already in this model — avoiding a full table scan every time.
--
-- Deduplication strategy:
--   The bronze layer can contain duplicate trade_ids from RabbitMQ re-delivery.
--   ROW_NUMBER() keeps only the most recently received version per trade_id.


-- ── Step 1: Pull raw rows from Bronze ────────────────────────────────────────
-- Apply the incremental filter here, before JSON extraction, to minimise
-- the number of rows we parse.

with source_data as (

    select
        payload,
        received_at

    from {{ source('bronze', 'raw_trades') }}

    where payload->>'trade_id' is not null

    {% if is_incremental() %}
        and received_at > (
            select coalesce(max(ingested_at), '1900-01-01'::timestamptz)
            from {{ this }}
        )
    {% endif %}

),

-- ── Step 2: Extract and cast JSON fields ─────────────────────────────────────
-- All type casting happens here. Downstream models receive clean Python/SQL types
-- and never need to know that the data originally lived in a JSONB column.

parsed as (

    select
        payload ->> 'trade_id'                          as trade_id,
        (payload ->> 'price')::numeric(18, 8)           as price,
        (payload ->> 'size')::numeric(18, 8)            as size,
        payload ->> 'side'                              as side,
        (payload ->> 'time')::timestamptz               as traded_at,
        received_at                                     as ingested_at

    from source_data

),

-- ── Step 3: Deduplicate by trade_id ──────────────────────────────────────────
-- In rare cases (RabbitMQ re-delivery, consumer restart), the same trade_id
-- can appear multiple times. Keep only the most recently ingested version.

deduped as (

    select
        trade_id,
        price,
        size,
        side,
        traded_at,
        ingested_at,
        row_number() over (
            partition by trade_id
            order by ingested_at desc
        ) as row_num

    from parsed

)

-- ── Final output ──────────────────────────────────────────────────────────────

select
    trade_id,
    price,
    size,
    side,
    traded_at,
    ingested_at

from deduped
where row_num = 1
