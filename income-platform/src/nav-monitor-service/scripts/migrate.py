"""
Agent 10 — NAV Erosion Monitor
Migration: CREATE TABLE IF NOT EXISTS platform_shared.nav_alerts

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
            CREATE TABLE IF NOT EXISTS platform_shared.nav_alerts (
                id              SERIAL PRIMARY KEY,
                symbol          TEXT NOT NULL,
                alert_type      TEXT NOT NULL,
                severity        TEXT NOT NULL,
                details         JSONB,
                score_at_alert  NUMERIC(5, 1),
                erosion_rate_used NUMERIC(8, 4),
                threshold_used  NUMERIC(8, 4),
                resolved_at     TIMESTAMPTZ,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_nav_alerts_symbol
            ON platform_shared.nav_alerts (symbol)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_nav_alerts_alert_type
            ON platform_shared.nav_alerts (alert_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_nav_alerts_severity
            ON platform_shared.nav_alerts (severity)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_nav_alerts_created_at
            ON platform_shared.nav_alerts (created_at DESC)
        """)
        logger.info("nav_alerts table ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
