"""
Agent 02 — Newsletter Ingestion Service
Migration Phase 2: Create flow_run_log table

Tracks Prefect flow run history for health checks and observability.
Safe to re-run — uses IF NOT EXISTS.

Usage:
    PYTHONPATH=. python scripts/migrate_phase2.py
"""
import sys
import logging
from sqlalchemy import text

sys.path.insert(0, "..")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_migration():
    from app.database import engine, check_database_connection

    logger.info("Running pre-flight database checks...")
    health = check_database_connection()

    if health["status"] != "healthy":
        logger.error(f"Database connection failed: {health.get('error')}")
        sys.exit(1)

    logger.info("Creating flow_run_log table...")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.flow_run_log (
                id                  SERIAL PRIMARY KEY,
                flow_name           VARCHAR(100) UNIQUE NOT NULL,
                last_run_at         TIMESTAMPTZ,
                last_run_status     VARCHAR(20),
                next_scheduled_at   TIMESTAMPTZ,
                articles_processed  INTEGER DEFAULT 0,
                duration_seconds    NUMERIC(10,2),
                metadata            JSONB,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_flow_run_log_name
            ON platform_shared.flow_run_log(flow_name)
        """))
        conn.commit()

    logger.info("flow_run_log table ready.")


if __name__ == "__main__":
    run_migration()
