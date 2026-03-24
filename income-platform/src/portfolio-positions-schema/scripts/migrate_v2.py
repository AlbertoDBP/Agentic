"""
Migration v2: Full data model expansion
Adds all fields required by the income-investor architecture spec.

Run from service root:
  DATABASE_URL=... python3 scripts/migrate_v2.py

Safe to re-run: all statements use ADD COLUMN IF NOT EXISTS.
"""

import asyncio
import os
import sys

import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=require")[0]


async def run_migration():
    conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    print("✓ Connected to database")

    try:
        # ── market_data_cache: technicals, fundamentals, debt, income stats ────
        print("\n[market_data_cache] Adding new columns...")
        mdc_cols = [
            # Technicals
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS sma_50            NUMERIC(12,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS sma_200           NUMERIC(12,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS rsi_14d           NUMERIC(8,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS rsi_14w           NUMERIC(8,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS support_level     NUMERIC(12,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS resistance_level  NUMERIC(12,4)",
            # Income stats (computed from dividend history)
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS yield_5yr_avg     NUMERIC(8,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS div_cagr_3yr      NUMERIC(8,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS div_cagr_10yr     NUMERIC(8,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS consecutive_growth_yrs INTEGER",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS buyback_yield     NUMERIC(8,4)",
            # Coverage / debt
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS coverage_metric_type TEXT",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS interest_coverage_ratio NUMERIC(10,2)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS net_debt_ebitda   NUMERIC(10,2)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS credit_rating     TEXT",
            # Fundamental extras (already in /ratios response)
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS free_cash_flow_yield NUMERIC(8,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS return_on_equity  NUMERIC(8,4)",
            # Analyst / timing
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS analyst_price_target NUMERIC(12,4)",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS next_earnings_date   DATE",
            "ALTER TABLE platform_shared.market_data_cache ADD COLUMN IF NOT EXISTS insider_ownership_pct NUMERIC(8,4)",
        ]
        for ddl in mdc_cols:
            await conn.execute(ddl)
            col = ddl.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
            print(f"  ✓ market_data_cache.{col}")

        # ── securities: structural / cost / tax treatment ────────────────────
        print("\n[securities] Adding new columns...")
        sec_cols = [
            "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS management_fee          DECIMAL(6,4)",
            "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS is_externally_managed   BOOLEAN DEFAULT FALSE",
            # Tax treatment percentages (sum ≈ 100)
            "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS tax_qualified_pct        DECIMAL(5,2) DEFAULT 100",
            "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS tax_ordinary_pct         DECIMAL(5,2) DEFAULT 0",
            "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS tax_roc_pct              DECIMAL(5,2) DEFAULT 0",
        ]
        for ddl in sec_cols:
            await conn.execute(ddl)
            col = ddl.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
            print(f"  ✓ securities.{col}")

        # Apply default tax treatment rules by asset_type
        print("  Applying default tax treatment by asset_type...")
        await conn.execute("""
            UPDATE platform_shared.securities SET
                tax_qualified_pct = 20,  tax_ordinary_pct = 80, tax_roc_pct = 0
            WHERE asset_type IN ('BDC','MORTGAGE_REIT') AND tax_ordinary_pct = 0
        """)
        await conn.execute("""
            UPDATE platform_shared.securities SET
                tax_qualified_pct = 0,  tax_ordinary_pct = 0, tax_roc_pct = 100
            WHERE asset_type IN ('MLP') AND tax_roc_pct = 0
        """)
        await conn.execute("""
            UPDATE platform_shared.securities SET
                tax_qualified_pct = 0,  tax_ordinary_pct = 100, tax_roc_pct = 0
            WHERE asset_type IN ('BOND','Bond') AND tax_ordinary_pct = 0
        """)
        await conn.execute("""
            UPDATE platform_shared.securities SET
                tax_qualified_pct = 50,  tax_ordinary_pct = 40, tax_roc_pct = 10
            WHERE asset_type IN ('CEF','COVERED_CALL_ETF') AND tax_qualified_pct = 100
        """)
        print("  ✓ Tax treatment defaults applied")

        # ── positions: DCA/DRIP + computed income efficiency ─────────────────
        print("\n[positions] Adding new columns...")
        pos_cols = [
            "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS dca_stage          INTEGER DEFAULT 1 CHECK (dca_stage BETWEEN 1 AND 4)",
            "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS drip_enabled        BOOLEAN DEFAULT FALSE",
            "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS annual_fee_drag     DECIMAL(12,2)",
            "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS estimated_tax_drag  DECIMAL(12,2)",
            "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS net_annual_income   DECIMAL(12,2)",
        ]
        for ddl in pos_cols:
            await conn.execute(ddl)
            col = ddl.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
            print(f"  ✓ positions.{col}")

        # ── portfolios: strategy + algorithm weights ──────────────────────────
        print("\n[portfolios] Adding new columns...")
        port_cols = [
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS benchmark_ticker       TEXT DEFAULT 'SCHD'",
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS target_yield           DECIMAL(5,2)",
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS monthly_income_target  DECIMAL(12,2)",
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS max_single_position_pct DECIMAL(5,2) DEFAULT 5.0",
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS weight_value           DECIMAL(5,2) DEFAULT 40.0",
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS weight_safety          DECIMAL(5,2) DEFAULT 40.0",
            "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS weight_technicals      DECIMAL(5,2) DEFAULT 20.0",
        ]
        for ddl in port_cols:
            await conn.execute(ddl)
            col = ddl.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
            print(f"  ✓ portfolios.{col}")

        print("\n✅ Migration v2 complete.")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        sys.exit(1)
    asyncio.run(run_migration())
