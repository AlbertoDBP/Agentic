"""
Agent 02 — Migration: suggestion_ttl_config
Creates platform_shared.suggestion_ttl_config with global default + per-asset-class TTL overrides.
Safe to re-run.

Usage (from repo root):
    docker exec -w /app -e PYTHONPATH=/app agent-02-newsletter-ingestion \
        python3 scripts/migrate_suggestion_ttl.py
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

    logger.info("Creating suggestion_ttl_config table...")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.suggestion_ttl_config (
                asset_class  VARCHAR(50) PRIMARY KEY,
                ttl_days     INTEGER     NOT NULL CHECK (ttl_days >= 1),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        logger.info("suggestion_ttl_config — table OK")

        # Seed defaults — matches current hardcoded _TTL_DAYS in suggestion_store.py
        # Uses ON CONFLICT DO NOTHING so existing user-configured values are preserved on re-run
        seed_rows = [
            ("_default",        45),
            ("BDC",             45),
            ("MORTGAGE_REIT",   45),
            ("mREIT",           45),
            ("PREFERRED_STOCK", 45),
            ("Preferred",       45),
            ("DIVIDEND_STOCK",  60),
            ("Stock",           60),
            ("EQUITY_REIT",     60),
            ("REIT",            60),
            ("BOND",            30),
            ("Bond",            30),
            ("CEF",             30),
            ("COVERED_CALL_ETF", 30),
        ]
        for asset_class, ttl_days in seed_rows:
            conn.execute(
                text("""
                    INSERT INTO platform_shared.suggestion_ttl_config (asset_class, ttl_days)
                    VALUES (:ac, :days)
                    ON CONFLICT (asset_class) DO NOTHING
                """),
                {"ac": asset_class, "days": ttl_days},
            )
        logger.info("suggestion_ttl_config — seeded %d rows", len(seed_rows))

        conn.commit()

    logger.info("suggestion_ttl_config migration complete.")


if __name__ == "__main__":
    run_migration()
