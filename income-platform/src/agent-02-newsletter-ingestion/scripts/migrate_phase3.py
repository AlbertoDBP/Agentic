"""
Agent 02 — Newsletter Ingestion Service
Migration Phase 3: Churn tracking + platform alignment columns

Adds:
  - analyst_recommendations.flip_count    INTEGER DEFAULT 0
  - analysts.churn_rate                   NUMERIC(5,4)

Safe to re-run — uses ADD COLUMN IF NOT EXISTS.

Usage:
    PYTHONPATH=. python scripts/migrate_phase3.py
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

    logger.info("Phase 3 migration: adding flip_count + churn_rate columns...")

    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE platform_shared.analyst_recommendations
              ADD COLUMN IF NOT EXISTS flip_count INTEGER DEFAULT 0
        """))
        logger.info("analyst_recommendations.flip_count — OK")

        conn.execute(text("""
            ALTER TABLE platform_shared.analysts
              ADD COLUMN IF NOT EXISTS churn_rate NUMERIC(5,4)
        """))
        logger.info("analysts.churn_rate — OK")

        conn.commit()

    logger.info("Phase 3 migration complete.")


if __name__ == "__main__":
    run_migration()
