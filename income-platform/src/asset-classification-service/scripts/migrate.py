"""
Agent 04 Migration Script
Run from service root: PYTHONPATH=. python scripts/migrate.py
Options: --drop-first (destructive reset)
"""
import sys
import argparse
import logging
import uuid
from datetime import datetime

sys.path.insert(0, "..")

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_engine():
    from app.config import settings
    return create_engine(settings.database_url)


def drop_tables(engine):
    logger.info("⚠️  Dropping Agent 04 tables...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS platform_shared.asset_classifications CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS platform_shared.asset_class_rules CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS platform_shared.classification_overrides CASCADE"))
        conn.commit()
    logger.info("✅ Tables dropped")


def create_tables(engine):
    logger.info("Creating Agent 04 tables...")
    with engine.connect() as conn:
        pass  # schema platform_shared already exists (created by Agent 03)

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.asset_class_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                asset_class VARCHAR(50) NOT NULL,
                rule_type VARCHAR(20) NOT NULL,
                rule_config JSONB NOT NULL,
                priority INTEGER DEFAULT 100,
                confidence_weight FLOAT DEFAULT 1.0,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.asset_classifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ticker VARCHAR(20) NOT NULL,
                asset_class VARCHAR(50) NOT NULL,
                parent_class VARCHAR(50) NOT NULL,
                confidence FLOAT NOT NULL,
                is_hybrid BOOLEAN DEFAULT FALSE,
                characteristics JSONB,
                benchmarks JSONB,
                sub_scores JSONB,
                tax_efficiency JSONB,
                matched_rules JSONB,
                source VARCHAR(50) DEFAULT 'rule_engine_v1',
                is_override BOOLEAN DEFAULT FALSE,
                classified_at TIMESTAMPTZ DEFAULT NOW(),
                valid_until TIMESTAMPTZ
            )
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_asset_classifications_ticker
            ON platform_shared.asset_classifications(ticker)
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_asset_classifications_classified_at
            ON platform_shared.asset_classifications(classified_at DESC)
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.classification_overrides (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ticker VARCHAR(20) NOT NULL UNIQUE,
                asset_class VARCHAR(50) NOT NULL,
                reason TEXT,
                created_by VARCHAR(100),
                effective_from TIMESTAMPTZ DEFAULT NOW(),
                effective_until TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        conn.commit()
    logger.info("✅ Tables created")


def seed_rules(engine):
    """Seed asset_class_rules from shared utility seed data."""
    logger.info("Seeding asset class rules...")
    from shared.asset_class_detector.seed_rules import SEED_RULES

    with engine.connect() as conn:
        # Only seed if table is empty
        result = conn.execute(text("SELECT COUNT(*) FROM platform_shared.asset_class_rules"))
        count = result.scalar()
        if count > 0:
            logger.info(f"  Skipping seed — {count} rules already exist")
            return

        for rule in SEED_RULES:
            conn.execute(text("""
                INSERT INTO platform_shared.asset_class_rules
                    (id, asset_class, rule_type, rule_config, priority, confidence_weight, active)
                VALUES
                    (:id, :asset_class, :rule_type, cast(:rule_config as jsonb), :priority, :confidence_weight, true)
            """), {
                "id": str(uuid.uuid4()),
                "asset_class": rule["asset_class"],
                "rule_type": rule["rule_type"],
                "rule_config": __import__("json").dumps(rule["rule_config"]),
                "priority": rule["priority"],
                "confidence_weight": rule["confidence_weight"],
            })

        conn.commit()
    logger.info(f"✅ Seeded {len(SEED_RULES)} rules")


def main():
    parser = argparse.ArgumentParser(description="Agent 04 migration")
    parser.add_argument("--drop-first", action="store_true", help="Drop tables before creating")
    args = parser.parse_args()

    engine = get_engine()

    if args.drop_first:
        drop_tables(engine)

    create_tables(engine)
    seed_rules(engine)
    logger.info("🚀 Agent 04 migration complete")


if __name__ == "__main__":
    main()
