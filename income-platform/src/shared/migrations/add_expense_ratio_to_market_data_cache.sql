-- src/shared/migrations/add_expense_ratio_to_market_data_cache.sql
ALTER TABLE platform_shared.market_data_cache
  ADD COLUMN IF NOT EXISTS expense_ratio FLOAT;

COMMENT ON COLUMN platform_shared.market_data_cache.expense_ratio
  IS 'Annual expense ratio as decimal fraction (e.g. 0.0035 for 0.35%). NULL for stocks/ETFs with no reported ratio.';
