-- migrations/001_bronze_schema.sql
-- Bronze layer: raw trade ingestion table
-- Idempotent: safe to run multiple times

-- ── Schemas ───────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS bronze;

-- Declared now for forward-compatibility — dbt and downstream scripts
-- can reference these schemas without depending on a later migration.
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ── Table ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bronze.raw_trades (
    id          BIGSERIAL    PRIMARY KEY,
    payload     JSONB        NOT NULL,
    trade_id    TEXT         GENERATED ALWAYS AS ((payload ->> 'trade_id')) STORED,
    received_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    processed   BOOLEAN      NOT NULL DEFAULT FALSE
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- GIN index for arbitrary JSONB field queries
CREATE INDEX IF NOT EXISTS idx_raw_trades_payload
    ON bronze.raw_trades USING GIN (payload);

-- Partial unique index on trade_id — enforces deduplication at DB level.
--
-- NOTE: This partial index is superseded by 002_bronze_trade_id_index.sql,
-- which drops it and replaces it with a full unique index. The full index
-- allows the simpler consumer insert form:
--   ON CONFLICT (trade_id) DO NOTHING
-- rather than requiring the WHERE predicate on every INSERT.
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_trades_trade_id
    ON bronze.raw_trades (trade_id)
    WHERE trade_id IS NOT NULL;

-- B-tree index on received_at for time-range queries and incremental dbt models
CREATE INDEX IF NOT EXISTS idx_raw_trades_received_at
    ON bronze.raw_trades (received_at);

-- Partial index for unprocessed row queries.
-- Supports: SELECT ... FROM bronze.raw_trades WHERE processed = FALSE ORDER BY received_at
-- Added now while table is empty — retrofitting on a large table requires a lock.
CREATE INDEX IF NOT EXISTS idx_raw_trades_unprocessed
    ON bronze.raw_trades (received_at)
    WHERE processed = FALSE;
