"""
Migration v3: Add HHS/IES computed columns to income_scores.

Run with:
  DATABASE_URL=postgresql://... python3 scripts/migrate_v3_hhs_ies.py

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
        print("\n[income_scores] Adding HHS/IES columns...")
        cols = [
            # HHS pillars
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS hhs_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS income_pillar_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS durability_pillar_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS income_weight NUMERIC(6,4)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS durability_weight NUMERIC(6,4)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS unsafe_flag BOOLEAN",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS unsafe_threshold INTEGER DEFAULT 20",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS hhs_status TEXT",
            # IES
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS ies_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS ies_calculated BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS ies_blocked_reason TEXT",
            # Quality gate
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS quality_gate_status TEXT DEFAULT 'PASS'",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS quality_gate_reasons JSONB",
            # Commentary
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS hhs_commentary TEXT",
            # valid_until already exists — expose in API only
        ]
        for ddl in cols:
            await conn.execute(ddl)
            col = ddl.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
            print(f"  ✓ income_scores.{col}")
        print("\n✓ Migration complete")
    finally:
        await conn.close()


if __name__ == "__main__":
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run_migration())
