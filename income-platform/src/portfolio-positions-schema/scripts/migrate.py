"""
Migration: portfolio-positions-v2
Description: Foundation schema + Portfolio persistence layer
Phases:
  0 - Foundation: securities, features_historical, user_preferences
  1 - Asset layer: nav_snapshots
  2 - Portfolio layer: accounts, portfolios, portfolio_constraints
  3 - Position layer: positions, transactions, dividend_events
  4 - Metrics layer: portfolio_income_metrics, portfolio_health_scores
Date: 2026-03-09
Run from service root: python3 scripts/migrate.py
Note: symbol TEXT PK used throughout (see ADR-P09 for UUID migration path)
"""

import sys
import os
import asyncio
import asyncpg

sys.path.insert(0, "..")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=require")[0]


async def run_migration():
    conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    print("✓ Connected to database")

    try:
        await conn.execute("BEGIN")

        # ----------------------------------------------------------------
        # PHASE 0 — Foundation
        # ----------------------------------------------------------------
        print("\n[Phase 0] Foundation tables...")

        print("  Creating platform_shared.securities...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.securities (
                symbol              TEXT PRIMARY KEY,
                name                TEXT,
                asset_type          TEXT,
                sector              TEXT,
                industry            TEXT,
                exchange            TEXT,
                currency            TEXT NOT NULL DEFAULT 'USD',
                is_active           BOOLEAN NOT NULL DEFAULT TRUE,
                listed_date         DATE,
                delisted_date       DATE,
                expense_ratio       DECIMAL(6,4),
                aum_millions        DECIMAL(12,2),
                inception_date      DATE,
                metadata            JSONB,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_securities_asset_type
                ON platform_shared.securities (asset_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_securities_active
                ON platform_shared.securities (is_active) WHERE is_active = TRUE
        """)

        print("  Creating platform_shared.features_historical...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.features_historical (
                id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                symbol                  TEXT NOT NULL
                                            REFERENCES platform_shared.securities(symbol),
                as_of_date              DATE NOT NULL,
                yield_trailing_12m      DECIMAL(6,4),
                yield_forward           DECIMAL(6,4),
                yield_5yr_avg           DECIMAL(6,4),
                div_cagr_1y             DECIMAL(6,4),
                div_cagr_3y             DECIMAL(6,4),
                div_cagr_5y             DECIMAL(6,4),
                chowder_number          DECIMAL(6,2),
                payout_ratio            DECIMAL(6,4),
                volatility_1y           DECIMAL(6,4),
                max_drawdown_1y         DECIMAL(6,4),
                max_drawdown_3y         DECIMAL(6,4),
                beta_equity             DECIMAL(6,4),
                beta_sector             DECIMAL(6,4),
                fcf_to_debt             DECIMAL(8,4),
                roe                     DECIMAL(8,4),
                interest_coverage       DECIMAL(8,2),
                pe_ratio                DECIMAL(8,2),
                pe_vs_sector_z          DECIMAL(6,4),
                ev_ebitda               DECIMAL(8,2),
                credit_rating           TEXT,
                credit_quality_proxy    TEXT,
                advisor_coverage_count  INTEGER,
                advisor_net_buy_signal  DECIMAL(4,2),
                missing_feature_ratio   DECIMAL(4,2),
                days_since_ipo          INTEGER,
                raw_features            JSONB,
                created_at              TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (symbol, as_of_date)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_features_historical_symbol_date
                ON platform_shared.features_historical (symbol, as_of_date DESC)
        """)

        print("  Creating platform_shared.user_preferences...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.user_preferences (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id           UUID NOT NULL,
                preference_key      TEXT NOT NULL,
                preference_value    TEXT NOT NULL,
                value_type          TEXT DEFAULT 'string' CHECK (
                                        value_type IN (
                                            'string','integer','decimal',
                                            'boolean','json'
                                        )
                                    ),
                description         TEXT,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (tenant_id, preference_key)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_preferences_tenant
                ON platform_shared.user_preferences (tenant_id)
        """)

        # ----------------------------------------------------------------
        # PHASE 1 — Asset layer
        # ----------------------------------------------------------------
        print("\n[Phase 1] Asset layer...")

        print("  Creating platform_shared.nav_snapshots...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.nav_snapshots (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                symbol              TEXT NOT NULL
                                        REFERENCES platform_shared.securities(symbol),
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
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nav_snapshots_symbol_date
                ON platform_shared.nav_snapshots (symbol, snapshot_date DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nav_snapshots_erosion
                ON platform_shared.nav_snapshots (erosion_flag, snapshot_date DESC)
                WHERE erosion_flag = TRUE
        """)

        # ----------------------------------------------------------------
        # PHASE 2 — Portfolio layer
        # ----------------------------------------------------------------
        print("\n[Phase 2] Portfolio layer...")

        print("  Creating platform_shared.accounts...")
        await conn.execute("""
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
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_tenant
                ON platform_shared.accounts (tenant_id)
        """)

        print("  Creating platform_shared.portfolios...")
        await conn.execute("""
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
                capital_to_deploy           DECIMAL(15,2),
                health_score                DECIMAL(5,2),
                health_score_computed_at    TIMESTAMPTZ,
                health_score_ttl_hours      INTEGER DEFAULT 24,
                last_rebalanced_at          TIMESTAMPTZ,
                created_at                  TIMESTAMPTZ DEFAULT NOW(),
                updated_at                  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolios_tenant
                ON platform_shared.portfolios (tenant_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolios_active
                ON platform_shared.portfolios (tenant_id, status)
                WHERE status = 'ACTIVE'
        """)

        print("  Creating platform_shared.portfolio_constraints...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.portfolio_constraints (
                id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id                UUID NOT NULL
                                                REFERENCES platform_shared.portfolios(id),
                target_yield_pct            DECIMAL(5,2),
                target_income_annual        DECIMAL(12,2),
                target_income_monthly       DECIMAL(10,2),
                max_position_pct            DECIMAL(5,2),
                min_position_pct            DECIMAL(5,2),
                max_sector_pct              DECIMAL(5,2),
                max_asset_class_pct         DECIMAL(5,2),
                max_single_issuer_pct       DECIMAL(5,2),
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
                sector_limits               JSONB,
                asset_class_limits          JSONB,
                version                     INTEGER NOT NULL DEFAULT 1,
                previous_constraints        JSONB,
                effective_date              DATE NOT NULL DEFAULT CURRENT_DATE,
                created_at                  TIMESTAMPTZ DEFAULT NOW(),
                updated_at                  TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (portfolio_id)
            )
        """)

        # ----------------------------------------------------------------
        # PHASE 3 — Position layer
        # ----------------------------------------------------------------
        print("\n[Phase 3] Position layer...")

        print("  Creating platform_shared.positions...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.positions (
                id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id            UUID NOT NULL
                                            REFERENCES platform_shared.portfolios(id),
                symbol                  TEXT NOT NULL
                                            REFERENCES platform_shared.securities(symbol),
                status                  TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (
                                            status IN ('PROPOSED','ACTIVE','CLOSED')
                                        ),
                quantity                DECIMAL(15,4) NOT NULL DEFAULT 0,
                avg_cost_basis          DECIMAL(12,4),
                total_cost_basis        DECIMAL(15,2),
                current_price           DECIMAL(12,4),
                current_value           DECIMAL(15,2),
                price_updated_at        TIMESTAMPTZ,
                annual_income           DECIMAL(12,2),
                yield_on_cost           DECIMAL(6,4),
                yield_on_value          DECIMAL(6,4),
                total_dividends_received DECIMAL(12,2) DEFAULT 0,
                portfolio_weight_pct    DECIMAL(6,3),
                acquired_date           DATE,
                closed_date             DATE,
                notes                   TEXT,
                created_at              TIMESTAMPTZ DEFAULT NOW(),
                updated_at              TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (portfolio_id, symbol, status)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_portfolio_status
                ON platform_shared.positions (portfolio_id, status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_symbol
                ON platform_shared.positions (symbol)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_proposed
                ON platform_shared.positions (portfolio_id)
                WHERE status = 'PROPOSED'
        """)

        print("  Creating platform_shared.transactions...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.transactions (
                id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id                UUID NOT NULL
                                                REFERENCES platform_shared.portfolios(id),
                position_id                 UUID REFERENCES platform_shared.positions(id),
                symbol                      TEXT NOT NULL
                                                REFERENCES platform_shared.securities(symbol),
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
                                                    'qualified','ordinary',
                                                    'return_of_capital',
                                                    'long_term_gain',
                                                    'short_term_gain','exempt'
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
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_portfolio_date
                ON platform_shared.transactions (portfolio_id, transaction_date DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_symbol_date
                ON platform_shared.transactions (symbol, transaction_date DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_wash_sale
                ON platform_shared.transactions (symbol, transaction_date)
                WHERE wash_sale_flag = TRUE
        """)

        print("  Creating platform_shared.dividend_events...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.dividend_events (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id        UUID NOT NULL
                                        REFERENCES platform_shared.portfolios(id),
                position_id         UUID NOT NULL
                                        REFERENCES platform_shared.positions(id),
                symbol              TEXT NOT NULL
                                        REFERENCES platform_shared.securities(symbol),
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
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dividend_events_portfolio_date
                ON platform_shared.dividend_events (portfolio_id, ex_date DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dividend_events_symbol_date
                ON platform_shared.dividend_events (symbol, ex_date DESC)
        """)

        # ----------------------------------------------------------------
        # PHASE 4 — Metrics & health
        # ----------------------------------------------------------------
        print("\n[Phase 4] Metrics & health layer...")

        print("  Creating platform_shared.portfolio_income_metrics...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.portfolio_income_metrics (
                id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id                UUID NOT NULL
                                                REFERENCES platform_shared.portfolios(id),
                as_of_date                  DATE NOT NULL,
                actual_yield_pct            DECIMAL(6,4),
                actual_income_annual        DECIMAL(12,2),
                actual_income_monthly       DECIMAL(10,2),
                yield_on_cost               DECIMAL(6,4),
                target_yield_pct            DECIMAL(6,4),
                target_income_annual        DECIMAL(12,2),
                income_gap_annual           DECIMAL(12,2),
                income_gap_pct              DECIMAL(6,4),
                monthly_income_schedule     JSONB,
                income_growth_rate_1y       DECIMAL(6,4),
                weighted_avg_score          DECIMAL(5,2),
                weighted_avg_chowder        DECIMAL(6,2),
                income_at_risk_pct          DECIMAL(6,4),
                nav_erosion_exposure_pct    DECIMAL(6,4),
                created_at                  TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (portfolio_id, as_of_date)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_income_metrics_portfolio_date
                ON platform_shared.portfolio_income_metrics
                (portfolio_id, as_of_date DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_income_gap_shortfall
                ON platform_shared.portfolio_income_metrics
                (portfolio_id, income_gap_annual)
                WHERE income_gap_annual < 0
        """)

        print("  Creating platform_shared.portfolio_health_scores...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.portfolio_health_scores (
                id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id                UUID NOT NULL
                                                REFERENCES platform_shared.portfolios(id),
                computed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                score                       DECIMAL(5,2) NOT NULL,
                grade                       TEXT CHECK (
                                                grade IN ('A','B','C','D','F')
                                            ),
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
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_health_scores_portfolio_time
                ON platform_shared.portfolio_health_scores
                (portfolio_id, computed_at DESC)
        """)

        await conn.execute("COMMIT")
        print("\n✅ Migration complete.")
        print("\nTables created:")
        print("  Phase 0: securities, features_historical, user_preferences")
        print("  Phase 1: nav_snapshots")
        print("  Phase 2: accounts, portfolios, portfolio_constraints")
        print("  Phase 3: positions, transactions, dividend_events")
        print("  Phase 4: portfolio_income_metrics, portfolio_health_scores")
        print("\nTotal: 12 tables")

    except Exception as e:
        await conn.execute("ROLLBACK")
        print(f"\n❌ Migration failed (rolled back): {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
