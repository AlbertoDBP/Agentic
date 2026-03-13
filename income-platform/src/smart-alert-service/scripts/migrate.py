"""
Idempotent migration script: creates platform_shared.unified_alerts if not present.
Run with: python -m scripts.migrate
"""
import logging
import sys

from sqlalchemy import text

from app.database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

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


def run_migration() -> None:
    logger.info("Running Smart Alert Service migration...")
    with engine.begin() as conn:
        conn.execute(text(DDL))
    logger.info("Migration complete.")


if __name__ == "__main__":
    run_migration()
