-- =============================================================================
-- migration: 002_bronze_trade_id_index.sql
--
-- Replaces the partial unique index on bronze.raw_trades(trade_id) from 001
-- with a full unique index.
--
-- Why:
--   The partial index (WHERE trade_id IS NOT NULL) requires a matching WHERE
--   predicate in every ON CONFLICT clause:
--
--     ON CONFLICT (trade_id) WHERE trade_id IS NOT NULL DO NOTHING
--
--   This is fragile — any consumer INSERT that omits the WHERE predicate raises:
--     "there is no unique or exclusion constraint matching the ON CONFLICT specification"
--
--   A full unique index allows the simpler and safer form:
--     ON CONFLICT (trade_id) DO NOTHING
--
--   Multiple NULLs are still allowed (standard SQL: NULL != NULL), so rows
--   with no trade_id are unaffected.
--
-- Idempotent: IF NOT EXISTS / IF EXISTS guards make this safe to re-run.
-- =============================================================================

-- Drop the partial index created in 001
DROP INDEX IF EXISTS bronze.idx_raw_trades_trade_id;

-- Replace with a full unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_bronze_trade_id
    ON bronze.raw_trades (trade_id);
