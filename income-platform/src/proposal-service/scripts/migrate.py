"""
Migration script — creates proposals table in platform_shared.
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
CREATE SCHEMA IF NOT EXISTS platform_shared;

CREATE TABLE IF NOT EXISTS platform_shared.proposals (
    id                    SERIAL PRIMARY KEY,
    ticker                VARCHAR(20) NOT NULL,
    analyst_signal_id     INTEGER,
    analyst_id            INTEGER,
    platform_score        NUMERIC(5,1),
    platform_alignment    VARCHAR(20),
    veto_flags            JSONB,
    divergence_notes      TEXT,

    analyst_recommendation  VARCHAR(20),
    analyst_sentiment       NUMERIC(6,4),
    analyst_thesis_summary  TEXT,
    analyst_yield_estimate  NUMERIC(8,4),
    analyst_safety_grade    VARCHAR(10),

    platform_yield_estimate NUMERIC(8,4),
    platform_safety_result  JSONB,
    platform_income_grade   VARCHAR(5),

    entry_price_low         NUMERIC(10,2),
    entry_price_high        NUMERIC(10,2),
    position_size_pct       NUMERIC(5,2),
    recommended_account     VARCHAR(50),
    sizing_rationale        TEXT,

    status                  VARCHAR(30) DEFAULT 'pending',
    trigger_mode            VARCHAR(30),
    trigger_ref_id          TEXT,
    override_rationale      TEXT,
    user_acknowledged_veto  BOOLEAN DEFAULT FALSE,
    reviewed_by             TEXT,
    decided_at              TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_proposals_ticker ON platform_shared.proposals(ticker);
CREATE INDEX IF NOT EXISTS ix_proposals_status ON platform_shared.proposals(status);
"""


def _strip(url: str) -> str:
    import re
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
        logger.info("proposals table ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
