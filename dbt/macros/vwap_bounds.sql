{% macro test_vwap_bounds(model, vwap_column, high_column, low_column) %}

-- vwap_bounds
--
-- Generic dbt test that validates VWAP is always within the observed price range.
--
-- dbt generic tests work by returning rows that FAIL the assertion.
-- This macro returns rows where VWAP is outside [low_price, high_price].
--
-- 0 rows returned → PASS (all VWAPs are within bounds)
-- 1+ rows returned → FAIL (at least one VWAP is outside bounds)
--
-- NULL handling:
--   BETWEEN returns NULL (not TRUE) when any operand is NULL.
--   NOT BETWEEN NULL AND x is NULL — not TRUE — so NULL VWAPs
--   are excluded from failures. This is intentional: a NULL VWAP
--   means the window had no tradeable volume (NULLIF guard upstream),
--   and is caught separately by a not_null test on the vwap column.

select *
from {{ model }}
where {{ vwap_column }} not between {{ low_column }} and {{ high_column }}

{% endmacro %}
