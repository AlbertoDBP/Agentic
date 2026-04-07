-- src/agent-14-data-quality/migrations/002_missing_fields.sql
-- Adds field_requirements for missing market attributes:
--   return_on_equity, net_debt_ebitda, yield_5yr_avg, insider_ownership_pct, credit_rating
-- Also fixes known UNKNOWN asset_type entries in securities.
-- Run as: psql $DATABASE_URL -f migrations/002_missing_fields.sql

SET search_path TO platform_shared;

-- ── 0. Add columns not yet in market_data_cache schema ────────────────────────
ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS profit_margin       NUMERIC(8,4);
ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS forward_pe          NUMERIC(10,2);
ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS debt_to_equity      FLOAT;

-- ── 1. Fix UNKNOWN asset_types ─────────────────────────────────────────────────
-- These symbols are confirmed by ticker-list rules in seed_rules.py but
-- landed as UNKNOWN due to the old ON CONFLICT DO NOTHING upsert in broker.py.
UPDATE securities SET asset_type = 'EQUITY_REIT'   WHERE symbol = 'MPT'  AND (asset_type IS NULL OR asset_type = 'UNKNOWN');
UPDATE securities SET asset_type = 'EQUITY_REIT'   WHERE symbol = 'ONL'  AND (asset_type IS NULL OR asset_type = 'UNKNOWN');
UPDATE securities SET asset_type = 'MORTGAGE_REIT' WHERE symbol = 'AGNZ' AND (asset_type IS NULL OR asset_type = 'UNKNOWN');
UPDATE securities SET asset_type = 'MORTGAGE_REIT' WHERE symbol = 'BRSP' AND (asset_type IS NULL OR asset_type = 'UNKNOWN');

-- ── 2. Invalidate stale UNKNOWN data_quality_issues for these symbols ──────────
-- So the scanner re-creates them with the correct asset_class on next scan.
DELETE FROM data_quality_issues
WHERE symbol IN ('MPT', 'ONL', 'AGNZ', 'BRSP')
  AND status IN ('missing', 'fetching', 'unresolvable');

-- ── 2b. Add debt_to_equity for CommonStock (missed in 001_initial) ────────────
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'debt_to_equity', TRUE,  'fmp', 'massive', 'fmp:/ratios', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 2c. Add profit_margin ──────────────────────────────────────────────────────
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'profit_margin', TRUE,  'fmp', NULL, 'fmp:/ratios', 'core'),
    ('REIT',        'profit_margin', FALSE, 'fmp', NULL, 'fmp:/ratios', 'core'),
    ('BDC',         'profit_margin', FALSE, 'fmp', NULL, 'fmp:/ratios', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 2d. Add forward_pe ─────────────────────────────────────────────────────────
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'forward_pe', FALSE, 'fmp', NULL, 'fmp:/ratios-ttm', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 3. Add return_on_equity to all fundamental asset classes ───────────────────
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'return_on_equity', TRUE,  'fmp', NULL, 'fmp:/ratios', 'core'),
    ('REIT',        'return_on_equity', TRUE,  'fmp', NULL, 'fmp:/ratios', 'core'),
    ('BDC',         'return_on_equity', TRUE,  'fmp', NULL, 'fmp:/ratios', 'core'),
    ('MLP',         'return_on_equity', TRUE,  'fmp', NULL, 'fmp:/ratios', 'core'),
    ('CEF',         'return_on_equity', FALSE, 'fmp', NULL, 'fmp:/ratios', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 4. Add net_debt_ebitda ─────────────────────────────────────────────────────
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'net_debt_ebitda', TRUE,  'fmp', NULL, 'fmp:/key-metrics', 'core'),
    ('REIT',        'net_debt_ebitda', TRUE,  'fmp', NULL, 'fmp:/key-metrics', 'core'),
    ('BDC',         'net_debt_ebitda', TRUE,  'fmp', NULL, 'fmp:/key-metrics', 'core'),
    ('MLP',         'net_debt_ebitda', TRUE,  'fmp', NULL, 'fmp:/key-metrics', 'core'),
    ('CEF',         'net_debt_ebitda', FALSE, 'fmp', NULL, 'fmp:/key-metrics', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 5. Add credit_rating ────────────────────────────────────────────────────────
-- Bonds require it; REITs / CommonStock / BDC as optional quality signal.
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('Bond',        'credit_rating', TRUE,  'fmp', NULL, 'fmp:/rating', 'core'),
    ('CommonStock', 'credit_rating', FALSE, 'fmp', NULL, 'fmp:/rating', 'core'),
    ('REIT',        'credit_rating', FALSE, 'fmp', NULL, 'fmp:/rating', 'core'),
    ('BDC',         'credit_rating', FALSE, 'fmp', NULL, 'fmp:/rating', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 6. Add yield_5yr_avg ────────────────────────────────────────────────────────
-- Computed by market-data-service (dividend history); healer cannot resolve this
-- directly. Required=FALSE so it's tracked but doesn't block quality gate.
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'yield_5yr_avg', FALSE, NULL, NULL, 'computed:dividend-history', 'core'),
    ('REIT',        'yield_5yr_avg', FALSE, NULL, NULL, 'computed:dividend-history', 'core'),
    ('BDC',         'yield_5yr_avg', FALSE, NULL, NULL, 'computed:dividend-history', 'core'),
    ('CEF',         'yield_5yr_avg', FALSE, NULL, NULL, 'computed:dividend-history', 'core'),
    ('MLP',         'yield_5yr_avg', FALSE, NULL, NULL, 'computed:dividend-history', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;

-- ── 7. Add insider_ownership_pct ────────────────────────────────────────────────
-- Sourced from FMP /insider-ownership; optional signal.
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source)
VALUES
    ('CommonStock', 'insider_ownership_pct', FALSE, 'fmp', NULL, 'fmp:/insider-ownership', 'core'),
    ('REIT',        'insider_ownership_pct', FALSE, 'fmp', NULL, 'fmp:/insider-ownership', 'core'),
    ('BDC',         'insider_ownership_pct', FALSE, 'fmp', NULL, 'fmp:/insider-ownership', 'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;
