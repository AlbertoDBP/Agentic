"""
Migration script — creates income_projections table in platform_shared.
Safe to re-run — uses IF NOT EXISTS.
Usage: DATABASE_URL=... python3 scripts/migrate.py
"""
import asyncio
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DDL = """
CREATE TABLE IF NOT EXISTS platform_shared.income_projections (
    id                          SERIAL PRIMARY KEY,
    portfolio_id                UUID NOT NULL,
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    horizon_months              INTEGER NOT NULL DEFAULT 12,
    total_projected_annual      NUMERIC(12, 2),
    total_projected_monthly_avg NUMERIC(12, 2),
    yield_used                  VARCHAR(20),
    positions_included          INTEGER,
    positions_missing_data      INTEGER,
    position_detail             JSONB,
    metadata                    JSONB
);

CREATE INDEX IF NOT EXISTS idx_income_projections_portfolio_id
    ON platform_shared.income_projections (portfolio_id);

CREATE INDEX IF NOT EXISTS idx_income_projections_computed_at
    ON platform_shared.income_projections (computed_at DESC);
"""


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
        await conn.execute(DDL)
        logger.info("income_projections table ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
