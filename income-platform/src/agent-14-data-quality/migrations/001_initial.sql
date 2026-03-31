-- src/agent-14-data-quality/migrations/001_initial.sql
-- Data Quality Engine — initial schema
-- Run as: psql $DATABASE_URL -f migrations/001_initial.sql

SET search_path TO platform_shared;

-- ── 1. field_requirements ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS field_requirements (
    id                    SERIAL PRIMARY KEY,
    asset_class           TEXT NOT NULL,
    field_name            TEXT NOT NULL,
    required              BOOLEAN NOT NULL DEFAULT TRUE,
    fetch_source_primary  TEXT,            -- 'fmp' | 'massive' | NULL
    fetch_source_fallback TEXT,            -- 'fmp' | 'massive' | NULL
    source                TEXT NOT NULL DEFAULT 'core',  -- 'core' | 'analyst_promoted'
    promoted_from_gap_id  INTEGER,         -- FK → feature_gap_log.id (cross-service)
    source_endpoint       TEXT,            -- e.g. 'fmp:/etf-info'
    description           TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_field_requirements UNIQUE (asset_class, field_name)
);

-- ── 2. data_quality_issues ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id               SERIAL PRIMARY KEY,
    symbol           TEXT NOT NULL,
    field_name       TEXT NOT NULL,
    asset_class      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'missing',
    severity         TEXT NOT NULL DEFAULT 'warning',
    attempt_count    INTEGER NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    resolved_at      TIMESTAMPTZ,
    source_used      TEXT,
    diagnostic       JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dq_issues UNIQUE (symbol, field_name)
);

CREATE INDEX IF NOT EXISTS idx_dqi_status   ON data_quality_issues (status);
CREATE INDEX IF NOT EXISTS idx_dqi_severity ON data_quality_issues (severity);
CREATE INDEX IF NOT EXISTS idx_dqi_symbol   ON data_quality_issues (symbol);

-- ── 3. data_quality_exemptions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_exemptions (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL,
    field_name  TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    reason      TEXT,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dq_exemptions UNIQUE (symbol, field_name)
);

-- ── 4. data_quality_gate ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_gate (
    id                    SERIAL PRIMARY KEY,
    portfolio_id          UUID NOT NULL,
    gate_date             DATE NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending',
    gate_passed_at        TIMESTAMPTZ,
    blocking_issue_count  INTEGER NOT NULL DEFAULT 0,
    scoring_triggered_at  TIMESTAMPTZ,
    scoring_completed_at  TIMESTAMPTZ,
    CONSTRAINT uq_dq_gate UNIQUE (portfolio_id, gate_date)
);

CREATE INDEX IF NOT EXISTS idx_dqg_portfolio ON data_quality_gate (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_dqg_date      ON data_quality_gate (gate_date);

-- ── 5. data_refresh_log ───────────────────────────────────────────────────────
-- One row per portfolio; upserted on each refresh / scoring cycle.
CREATE TABLE IF NOT EXISTS data_refresh_log (
    portfolio_id               UUID PRIMARY KEY,
    market_data_refreshed_at   TIMESTAMPTZ,
    scores_recalculated_at     TIMESTAMPTZ,
    market_staleness_hrs       NUMERIC(6,2),
    holdings_complete_count    INTEGER,
    holdings_incomplete_count  INTEGER,
    critical_issues_count      INTEGER,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Seed: field_requirements ──────────────────────────────────────────────────
-- Universal fields (all asset classes)
DO $$
DECLARE
    classes TEXT[] := ARRAY['CommonStock','ETF','CEF','BDC','REIT','MLP','Preferred'];
    universal TEXT[] := ARRAY['price','week52_high','week52_low','dividend_yield','div_frequency','sma_50','sma_200','rsi_14d'];
    -- Note: MORTGAGE_REIT securities map to 'REIT' asset_class in the scanner
    -- (ASSET_TYPE_TO_CLASS: EQUITY_REIT → REIT, MORTGAGE_REIT → REIT)
    -- so MORTGAGE_REIT is NOT a separate asset_class in field_requirements.
    cls TEXT;
    fld TEXT;
BEGIN
    FOREACH cls IN ARRAY classes LOOP
        FOREACH fld IN ARRAY universal LOOP
            INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source)
            VALUES (cls, fld, TRUE, 'massive', 'fmp', 'core')
            ON CONFLICT (asset_class, field_name) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;

-- Class-specific fields
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source) VALUES
    ('CommonStock', 'payout_ratio',          TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('CommonStock', 'chowder_number',         TRUE,  'fmp',     NULL,      'fmp:/dividends',       'core'),
    ('CommonStock', 'consecutive_growth_yrs', TRUE,  'fmp',     NULL,      'fmp:/dividends-history','core'),
    -- REIT covers both EQUITY_REIT and MORTGAGE_REIT securities (both map to 'REIT' asset_class)
    ('REIT',        'payout_ratio',           TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('REIT',        'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('REIT',        'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('ETF',         'nav_value',              TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('ETF',         'nav_discount_pct',       FALSE, 'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('CEF',         'nav_value',              TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('CEF',         'nav_discount_pct',       TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('CEF',         'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('CEF',         'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('BDC',         'nav_value',              TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('BDC',         'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('BDC',         'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('MLP',         'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('MLP',         'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;
