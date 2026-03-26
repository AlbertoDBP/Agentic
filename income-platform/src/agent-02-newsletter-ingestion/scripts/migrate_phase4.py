"""
Agent 02 — Phase 4 Migration: Newsletter Deep Intelligence tables

Creates in platform_shared:
  - article_frameworks          Pass 2 extraction output per article per ticker
  - analyst_framework_profiles  Synthesized per-analyst mental models
  - analyst_suggestions         Investment ideas queue for Agent 07
  - feature_gap_log             Untracked metrics identified by Pass 2
  - feature_registry            Canonical feature catalog for Agent 01

Safe to re-run — uses CREATE TABLE IF NOT EXISTS.

Usage:
    cd src/agent-02-newsletter-ingestion
    PYTHONPATH=. python scripts/migrate_phase4.py
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

    logger.info("Phase 4 migration: creating deep intelligence tables...")

    with engine.connect() as conn:
        # 1. article_frameworks
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.article_frameworks (
                id                       SERIAL PRIMARY KEY,
                article_id               INTEGER NOT NULL
                    REFERENCES platform_shared.analyst_articles(id) ON DELETE CASCADE,
                analyst_id               INTEGER NOT NULL
                    REFERENCES platform_shared.analysts(id) ON DELETE CASCADE,
                ticker                   VARCHAR(20) NOT NULL,
                valuation_metrics_cited  JSONB,
                thresholds_identified    JSONB,
                reasoning_structure      VARCHAR(30),
                conviction_level         VARCHAR(10),
                catalysts                JSONB,
                price_guidance_type      VARCHAR(20),
                price_guidance_value     JSONB,
                risk_factors_cited       JSONB,
                macro_factors            JSONB,
                evaluation_narrative     TEXT,
                framework_embedding      VECTOR(1536),
                extracted_at             TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_article_frameworks_article_id
                ON platform_shared.article_frameworks(article_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_article_frameworks_analyst_ticker
                ON platform_shared.article_frameworks(analyst_id, ticker)
        """))
        logger.info("article_frameworks — OK")

        # 2. analyst_framework_profiles
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.analyst_framework_profiles (
                id                        SERIAL PRIMARY KEY,
                analyst_id                INTEGER NOT NULL
                    REFERENCES platform_shared.analysts(id) ON DELETE CASCADE,
                asset_class               VARCHAR(30) NOT NULL,
                metric_frequency          JSONB,
                typical_thresholds        JSONB,
                preferred_reasoning_style VARCHAR(30),
                conviction_patterns       JSONB,
                catalyst_sensitivity      JSONB,
                framework_summary         TEXT,
                consistency_score         NUMERIC(5,4),
                article_count             INTEGER DEFAULT 0,
                synthesized_at            TIMESTAMPTZ DEFAULT NOW(),
                profile_embedding         VECTOR(1536),
                UNIQUE (analyst_id, asset_class)
            )
        """))
        logger.info("analyst_framework_profiles — OK")

        # 3. analyst_suggestions
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.analyst_suggestions (
                id                    SERIAL PRIMARY KEY,
                analyst_id            INTEGER NOT NULL
                    REFERENCES platform_shared.analysts(id) ON DELETE CASCADE,
                article_framework_id  INTEGER NOT NULL
                    REFERENCES platform_shared.article_frameworks(id) ON DELETE CASCADE,
                ticker                VARCHAR(20) NOT NULL,
                asset_class           VARCHAR(30),
                recommendation        VARCHAR(20) NOT NULL,
                sentiment_score       NUMERIC(5,4),
                price_guidance_type   VARCHAR(20),
                price_guidance_value  JSONB,
                staleness_weight      NUMERIC(5,4) DEFAULT 1.0,
                is_active             BOOLEAN DEFAULT TRUE,
                sourced_at            TIMESTAMPTZ NOT NULL,
                expires_at            TIMESTAMPTZ NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uix_analyst_suggestions_active
                ON platform_shared.analyst_suggestions(analyst_id, ticker)
                WHERE is_active = TRUE
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_analyst_suggestions_active_expiry
                ON platform_shared.analyst_suggestions(is_active, expires_at, staleness_weight)
        """))
        logger.info("analyst_suggestions — OK")

        # 4. feature_gap_log
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.feature_gap_log (
                id                 SERIAL PRIMARY KEY,
                metric_name_raw    VARCHAR(200) NOT NULL,
                canonical_candidate VARCHAR(200),
                asset_class        VARCHAR(30),
                article_id         INTEGER
                    REFERENCES platform_shared.analyst_articles(id) ON DELETE SET NULL,
                analyst_id         INTEGER
                    REFERENCES platform_shared.analysts(id) ON DELETE SET NULL,
                occurrence_count   INTEGER DEFAULT 1,
                resolution_status  VARCHAR(30) DEFAULT 'pending',
                resolved_at        TIMESTAMPTZ,
                UNIQUE (metric_name_raw, asset_class)
            )
        """))
        logger.info("feature_gap_log — OK")

        # 5. feature_registry
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.feature_registry (
                id               SERIAL PRIMARY KEY,
                feature_name     VARCHAR(200) UNIQUE NOT NULL,
                aliases          JSONB,
                category         VARCHAR(20) NOT NULL,
                source           VARCHAR(30),
                asset_classes    JSONB,
                fetch_config     JSONB,
                computation_rule TEXT,
                is_active        BOOLEAN DEFAULT FALSE,
                validation_status VARCHAR(20) DEFAULT 'pending',
                added_at         TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        logger.info("feature_registry — OK")

        conn.commit()

    logger.info("Phase 4 migration complete.")


if __name__ == "__main__":
    run_migration()
