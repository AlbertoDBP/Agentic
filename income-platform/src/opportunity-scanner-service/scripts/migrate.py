"""
Migration: opportunity-scanner-v1
Description: Creates platform_shared.scan_results table for Agent 07.
Date: 2026-03-12
Run from service root: python3 scripts/migrate.py
"""
import asyncio
import os
import sys

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

        print("  Creating platform_shared.scan_results...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.scan_results (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                total_scanned   INTEGER NOT NULL,
                total_passed    INTEGER NOT NULL,
                total_vetoed    INTEGER NOT NULL,
                filters         JSONB NOT NULL,
                items           JSONB NOT NULL,
                status          TEXT NOT NULL DEFAULT 'COMPLETE',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_scan_results_created_at
                ON platform_shared.scan_results (created_at DESC)
        """)

        await conn.execute("COMMIT")
        print("\n✅ Migration complete.")
        print("  Table created: platform_shared.scan_results")

    except Exception as e:
        await conn.execute("ROLLBACK")
        print(f"\n❌ Migration failed (rolled back): {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
