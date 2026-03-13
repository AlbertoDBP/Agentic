"""
Agent 08 — Rebalancing Service
Migration: CREATE TABLE platform_shared.rebalancing_results

Safe to re-run — uses IF NOT EXISTS.
Usage: DATABASE_URL=... JWT_SECRET=x python scripts/migrate.py
"""
import asyncio
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _strip(url: str) -> str:
    return re.sub(r"\?.+$", "", url)


async def run_migration() -> None:
    import asyncpg
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(_strip(db_url), ssl="require")
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_shared.rebalancing_results (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                portfolio_id    UUID NOT NULL,
                violations      JSONB NOT NULL,
                proposals       JSONB NOT NULL,
                filters         JSONB NOT NULL,
                total_tax_savings NUMERIC(12,2),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_rebalancing_results_portfolio_id
            ON platform_shared.rebalancing_results (portfolio_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_rebalancing_results_created_at
            ON platform_shared.rebalancing_results (created_at DESC)
        """)
        logger.info("rebalancing_results table ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
