-- =============================================================================
-- Income Fortress Platform — Portfolio & Positions Schema v2
-- Migration: portfolio-positions-v2
-- Date: 2026-03-09
-- Changes from v1: symbol TEXT PK (not UUID), securities + features_historical
--                  + user_preferences created fresh (not assumed to exist)
-- Run from service root: python3 scripts/migrate.py
-- =============================================================================

-- =============================================================================
-- PHASE 0 — Foundation tables (must exist before portfolio layer)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- securities — master ticker registry
-- PK: symbol TEXT (consistent with all deployed agents)
-- v2 migration path: add id UUID, backfill, migrate FKs (see ADR-P09)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.securities (
    symbol              TEXT PRIMARY KEY,              -- 'JEPI', 'AAPL', 'O'
    name                TEXT,
    asset_type          TEXT,                          -- from asset_classifications
    sector              TEXT,
    industry            TEXT,
    exchange            TEXT,
    currency            TEXT NOT NULL DEFAULT 'USD',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    listed_date         DATE,
    delisted_date       DATE,
    -- ETF-specific
    expense_ratio       DECIMAL(6,4),
    aum_millions        DECIMAL(12,2),
    inception_date      DATE,
    -- metadata
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_securities_asset_type
    ON platform_shared.securities (asset_type);
CREATE INDEX IF NOT EXISTS idx_securities_active
    ON platform_shared.securities (is_active)
    WHERE is_active = TRUE;

-- -----------------------------------------------------------------------------
-- features_historical — 50+ scoring features per ticker per date
-- Created fresh (was not in prod schema)
-- Consumed by: Agent 03 (scoring), Agent 04 (entry signals)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.features_historical (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol                  TEXT NOT NULL REFERENCES platform_shared.securities(symbol),
    as_of_date              DATE NOT NULL,
    -- yield metrics
    yield_trailing_12m      DECIMAL(6,4),
    yield_forward           DECIMAL(6,4),
    yield_5yr_avg           DECIMAL(6,4),              -- NEW: 5yr rolling avg yield
    div_cagr_1y             DECIMAL(6,4),
    div_cagr_3y             DECIMAL(6,4),
    div_cagr_5y             DECIMAL(6,4),
    chowder_number          DECIMAL(6,2),              -- NEW: yield_ttm + div_cagr_5y
    payout_ratio            DECIMAL(6,4),
    -- risk metrics
    volatility_1y           DECIMAL(6,4),
    max_drawdown_1y         DECIMAL(6,4),
    max_drawdown_3y         DECIMAL(6,4),
    beta_equity             DECIMAL(6,4),
    beta_sector             DECIMAL(6,4),
    -- fundamentals
    fcf_to_debt             DECIMAL(8,4),
    roe                     DECIMAL(8,4),
    interest_coverage       DECIMAL(8,2),
    -- valuation
    pe_ratio                DECIMAL(8,2),
    pe_vs_sector_z          DECIMAL(6,4),
    ev_ebitda               DECIMAL(8,2),
    -- credit
    credit_rating           TEXT,                      -- from Finnhub (ADR-P07)
    credit_quality_proxy    TEXT,                      -- INVESTMENT_GRADE / BORDERLINE / SPECULATIVE_GRADE
    -- analyst signals
    advisor_coverage_count  INTEGER,
    advisor_net_buy_signal  DECIMAL(4,2),              -- -1 to +1
    -- meta
    missing_feature_ratio   DECIMAL(4,2),
    days_since_ipo          INTEGER,
    raw_features            JSONB,                     -- all 50+ features
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_features_historical_symbol_date
    ON platform_shared.features_historical (symbol, as_of_date DESC);

-- -----------------------------------------------------------------------------
-- user_preferences — per-tenant key-value settings
-- Includes: data_freshness_hours (TTL), income_gap_trigger_pct, etc.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.user_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    preference_key      TEXT NOT NULL,
    preference_value    TEXT NOT NULL,
    value_type          TEXT DEFAULT 'string' CHECK (
                            value_type IN ('string','integer','decimal','boolean','json')
                        ),
    description         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, preference_key)
);
CREATE INDEX IF NOT EXISTS idx_user_preferences_tenant
    ON platform_shared.user_preferences (tenant_id);

-- Default preference keys (insert on tenant creation, not here):
-- data_freshness_hours     → '24'        (integer) — price + health score TTL
-- income_gap_trigger_pct   → '5.0'       (decimal) — Agent 07 trigger threshold
-- min_score_grade          → 'B'         (string)  — default quality gate
-- dca_threshold_usd        → '2000'      (integer) — Agent 12 DCA minimum

-- =============================================================================
-- PHASE 1 — NAV snapshots (platform_shared, asset-level)
-- =============================================================================

CREATE TABLE IF NOT EXISTS platform_shared.nav_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT NOT NULL REFERENCES platform_shared.securities(symbol),
    snapshot_date       DATE NOT NULL,
    nav                 DECIMAL(12,4) NOT NULL,
    market_price        DECIMAL(12,4),
    premium_discount    DECIMAL(6,4),
    distribution_rate   DECIMAL(6,4),
    erosion_rate_30d    DECIMAL(6,4),
    erosion_rate_90d    DECIMAL(6,4),
    erosion_rate_1y     DECIMAL(6,4),
    erosion_flag        BOOLEAN DEFAULT FALSE,
    source              TEXT DEFAULT 'agent_01',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_nav_snapshots_symbol_date
    ON platform_shared.nav_snapshots (symbol, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_nav_snapshots_erosion
    ON platform_shared.nav_snapshots (erosion_flag, snapshot_date DESC)
    WHERE erosion_flag = TRUE;

-- =============================================================================
-- PHASE 2 — Portfolio layer
-- =============================================================================

-- -----------------------------------------------------------------------------
-- accounts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    account_name        TEXT NOT NULL,
    account_type        TEXT NOT NULL CHECK (
                            account_type IN (
                                'taxable','traditional_ira','roth_ira',
                                '401k','403b','hsa','custodial'
                            )
                        ),
    broker              TEXT,
    broker_account_id   TEXT,
    currency            TEXT NOT NULL DEFAULT 'USD',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_accounts_tenant
    ON platform_shared.accounts (tenant_id);

-- -----------------------------------------------------------------------------
-- portfolios
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.portfolios (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID NOT NULL,
    account_id                  UUID REFERENCES platform_shared.accounts(id),
    portfolio_name              TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (
                                    status IN ('DRAFT','ACTIVE','ARCHIVED')
                                ),
    total_value                 DECIMAL(15,2),
    cash_balance                DECIMAL(15,2) DEFAULT 0,
    capital_to_deploy           DECIMAL(15,2),          -- DRAFT portfolios only
    health_score                DECIMAL(5,2),
    health_score_computed_at    TIMESTAMPTZ,
    health_score_ttl_hours      INTEGER DEFAULT 24,      -- overrides user_preferences
    last_rebalanced_at          TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_portfolios_tenant
    ON platform_shared.portfolios (tenant_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_active
    ON platform_shared.portfolios (tenant_id, status)
    WHERE status = 'ACTIVE';

-- -----------------------------------------------------------------------------
-- portfolio_constraints
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.portfolio_constraints (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id                UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    -- income targets (yield ↔ income duality — both stored)
    target_yield_pct            DECIMAL(5,2),
    target_income_annual        DECIMAL(12,2),
    target_income_monthly       DECIMAL(10,2),
    -- position sizing
    max_position_pct            DECIMAL(5,2),
    min_position_pct            DECIMAL(5,2),
    -- concentration limits
    max_sector_pct              DECIMAL(5,2),
    max_asset_class_pct         DECIMAL(5,2),
    max_single_issuer_pct       DECIMAL(5,2),
    -- quality gates
    min_income_score_grade      TEXT DEFAULT 'B' CHECK (
                                    min_income_score_grade IN ('A','B','C','D')
                                ),
    min_chowder_signal          TEXT DEFAULT 'BORDERLINE' CHECK (
                                    min_chowder_signal IN (
                                        'ATTRACTIVE','BORDERLINE','UNATTRACTIVE'
                                    )
                                ),
    exclude_junk_bond_risk      BOOLEAN DEFAULT TRUE,
    exclude_nav_erosion_risk    BOOLEAN DEFAULT TRUE,
    -- flexible concentration maps
    sector_limits               JSONB,          -- {"REIT": 20.0, "Financials": 30.0}
    asset_class_limits          JSONB,          -- {"covered_call_etf": 40.0, "bdc": 15.0}
    -- version control
    version                     INTEGER NOT NULL DEFAULT 1,
    previous_constraints        JSONB,          -- snapshot of prior version
    effective_date              DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (portfolio_id)
);

-- =============================================================================
-- PHASE 3 — Position layer
-- Entity chain: securities(symbol PK) → positions(symbol FK, portfolio_id FK)
--                                                      → portfolios(id PK)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- positions — average cost basis, one row per symbol per portfolio per status
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.positions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id            UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    symbol                  TEXT NOT NULL REFERENCES platform_shared.securities(symbol),
    status                  TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (
                                status IN ('PROPOSED','ACTIVE','CLOSED')
                            ),
    -- sizing
    quantity                DECIMAL(15,4) NOT NULL DEFAULT 0,
    avg_cost_basis          DECIMAL(12,4),
    total_cost_basis        DECIMAL(15,2),
    -- current value (from Valkey cache, refreshed by Agent 01)
    current_price           DECIMAL(12,4),
    current_value           DECIMAL(15,2),
    price_updated_at        TIMESTAMPTZ,
    -- income
    annual_income           DECIMAL(12,2),
    yield_on_cost           DECIMAL(6,4),
    yield_on_value          DECIMAL(6,4),
    total_dividends_received DECIMAL(12,2) DEFAULT 0,
    -- weight
    portfolio_weight_pct    DECIMAL(6,3),
    -- lifecycle
    acquired_date           DATE,
    closed_date             DATE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (portfolio_id, symbol, status)
);
CREATE INDEX IF NOT EXISTS idx_positions_portfolio_status
    ON platform_shared.positions (portfolio_id, status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol
    ON platform_shared.positions (symbol);
CREATE INDEX IF NOT EXISTS idx_positions_proposed
    ON platform_shared.positions (portfolio_id)
    WHERE status = 'PROPOSED';

-- -----------------------------------------------------------------------------
-- transactions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.transactions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id                UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    position_id                 UUID REFERENCES platform_shared.positions(id),
    symbol                      TEXT NOT NULL REFERENCES platform_shared.securities(symbol),
    transaction_type            TEXT NOT NULL CHECK (
                                    transaction_type IN (
                                        'buy','sell','dividend','drip',
                                        'fee','transfer_in','transfer_out',
                                        'split','spinoff'
                                    )
                                ),
    quantity                    DECIMAL(15,4),
    price                       DECIMAL(12,4),
    fee                         DECIMAL(10,2) DEFAULT 0,
    total_amount                DECIMAL(15,2),
    tax_treatment               TEXT CHECK (
                                    tax_treatment IN (
                                        'qualified','ordinary','return_of_capital',
                                        'long_term_gain','short_term_gain','exempt'
                                    )
                                ),
    wash_sale_flag              BOOLEAN DEFAULT FALSE,
    wash_sale_disallowed_loss   DECIMAL(12,2),
    transaction_date            DATE NOT NULL,
    settlement_date             DATE,
    source                      TEXT DEFAULT 'manual' CHECK (
                                    source IN (
                                        'manual','alpaca','schwab',
                                        'fidelity','plaid','drip_agent'
                                    )
                                ),
    external_ref                TEXT,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_transactions_portfolio_date
    ON platform_shared.transactions (portfolio_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_symbol_date
    ON platform_shared.transactions (symbol, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_wash_sale
    ON platform_shared.transactions (symbol, transaction_date)
    WHERE wash_sale_flag = TRUE;

-- -----------------------------------------------------------------------------
-- dividend_events
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.dividend_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id        UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    position_id         UUID NOT NULL REFERENCES platform_shared.positions(id),
    symbol              TEXT NOT NULL REFERENCES platform_shared.securities(symbol),
    transaction_id      UUID REFERENCES platform_shared.transactions(id),
    ex_date             DATE NOT NULL,
    pay_date            DATE,
    declared_date       DATE,
    amount_per_share    DECIMAL(10,4) NOT NULL,
    shares_held         DECIMAL(15,4) NOT NULL,
    total_amount        DECIMAL(12,2) NOT NULL,
    dividend_type       TEXT CHECK (
                            dividend_type IN (
                                'regular','special','qualified',
                                'return_of_capital','drip'
                            )
                        ),
    tax_treatment       TEXT,
    reinvested          BOOLEAN DEFAULT FALSE,
    reinvest_shares     DECIMAL(15,4),
    reinvest_price      DECIMAL(12,4),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dividend_events_portfolio_date
    ON platform_shared.dividend_events (portfolio_id, ex_date DESC);
CREATE INDEX IF NOT EXISTS idx_dividend_events_symbol_date
    ON platform_shared.dividend_events (symbol, ex_date DESC);

-- =============================================================================
-- PHASE 4 — Metrics & health
-- =============================================================================

-- -----------------------------------------------------------------------------
-- portfolio_income_metrics
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.portfolio_income_metrics (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id                UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    as_of_date                  DATE NOT NULL,
    actual_yield_pct            DECIMAL(6,4),
    actual_income_annual        DECIMAL(12,2),
    actual_income_monthly       DECIMAL(10,2),
    yield_on_cost               DECIMAL(6,4),
    target_yield_pct            DECIMAL(6,4),
    target_income_annual        DECIMAL(12,2),
    income_gap_annual           DECIMAL(12,2),  -- negative = shortfall → triggers Agent 07
    income_gap_pct              DECIMAL(6,4),
    monthly_income_schedule     JSONB,          -- {"2026-04": 122.50, "2026-05": 118.00}
    income_growth_rate_1y       DECIMAL(6,4),
    weighted_avg_score          DECIMAL(5,2),
    weighted_avg_chowder        DECIMAL(6,2),
    income_at_risk_pct          DECIMAL(6,4),
    nav_erosion_exposure_pct    DECIMAL(6,4),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (portfolio_id, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_income_metrics_portfolio_date
    ON platform_shared.portfolio_income_metrics (portfolio_id, as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_income_gap_shortfall
    ON platform_shared.portfolio_income_metrics (portfolio_id, income_gap_annual)
    WHERE income_gap_annual < 0;

-- -----------------------------------------------------------------------------
-- portfolio_health_scores
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform_shared.portfolio_health_scores (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id                UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    score                       DECIMAL(5,2) NOT NULL,
    grade                       TEXT CHECK (grade IN ('A','B','C','D','F')),
    income_quality_score        DECIMAL(5,2),
    diversification_score       DECIMAL(5,2),
    safety_score                DECIMAL(5,2),
    tax_efficiency_score        DECIMAL(5,2),
    constraint_compliance_score DECIMAL(5,2),
    flags                       TEXT[],
    position_count              INTEGER,
    total_value                 DECIMAL(15,2),
    actual_yield_pct            DECIMAL(6,4),
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_health_scores_portfolio_time
    ON platform_shared.portfolio_health_scores (portfolio_id, computed_at DESC);
