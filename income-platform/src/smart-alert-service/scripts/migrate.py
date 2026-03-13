"""
Migration script — creates unified_alerts table in platform_shared.
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
CREATE TABLE IF NOT EXISTS platform_shared.unified_alerts (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    source_agent    INTEGER NOT NULL,
    alert_type      TEXT NOT NULL,
    severity        TEXT NOT NULL,
    status          TEXT DEFAULT 'PENDING',
    first_seen_at   TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at    TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    details         JSONB,
    notified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_unified_alerts_symbol
    ON platform_shared.unified_alerts(symbol);
CREATE INDEX IF NOT EXISTS ix_unified_alerts_status
    ON platform_shared.unified_alerts(status);
CREATE INDEX IF NOT EXISTS ix_unified_alerts_source
    ON platform_shared.unified_alerts(source_agent);
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
        logger.info("unified_alerts table ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
