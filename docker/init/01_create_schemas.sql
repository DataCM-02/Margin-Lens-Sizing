CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA raw IS
    'Synthetic source data loaded without analytical transformations.';

COMMENT ON SCHEMA staging IS
    'Cleaned and standardized source models managed by dbt.';

COMMENT ON SCHEMA intermediate IS
    'Reusable business logic and manufacturing cost calculations.';

COMMENT ON SCHEMA marts IS
    'Analytics-ready models consumed by Power BI and executive analysis.';

COMMENT ON SCHEMA audit IS
    'Load controls, data quality results, and reconciliation records.';