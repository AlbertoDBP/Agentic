"""
Agent 02 — Newsletter Ingestion Service
Migration: Create all 6 tables in platform_shared schema

Run once against the production database before starting the service.
Requires pgvector extension to be pre-installed on the PostgreSQL instance.

Usage:
    python scripts/migrate.py
    python scripts/migrate.py --drop-first   # WARNING: destroys all data
"""
import sys
import argparse
import logging
from sqlalchemy import text

# Add parent to path so we can import app modules
sys.path.insert(0, "..")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_migration(drop_first: bool = False):
    """
    Create all Agent 02 tables in the platform_shared schema.
    Safe to re-run — uses IF NOT EXISTS throughout.
    """
    from app.database import engine, check_database_connection
    from app.models.models import Base

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    logger.info("Running pre-flight database checks...")
    health = check_database_connection()

    if health["status"] != "healthy":
        logger.error(f"Database connection failed: {health.get('error')}")
        sys.exit(1)

    if not health.get("pgvector_installed"):
        logger.error(
            "pgvector extension is NOT installed. "
            "Run: CREATE EXTENSION IF NOT EXISTS vector; "
            "as a superuser on the target database."
        )
        sys.exit(1)

    if not health.get("schema_exists"):
        logger.info("Schema 'platform_shared' does not exist — creating...")
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS platform_shared"))
            conn.commit()

    # ── Optional drop ─────────────────────────────────────────────────────────
    if drop_first:
        logger.warning("⚠️  DROP FIRST requested — dropping all Agent 02 tables...")
        with engine.connect() as conn:
            conn.execute(text("""
                DROP TABLE IF EXISTS platform_shared.analyst_accuracy_log CASCADE;
                DROP TABLE IF EXISTS platform_shared.analyst_recommendations CASCADE;
                DROP TABLE IF EXISTS platform_shared.analyst_articles CASCADE;
                DROP TABLE IF EXISTS platform_shared.analysts CASCADE;
                DROP TABLE IF EXISTS platform_shared.credit_overrides CASCADE;
            """))
            conn.commit()
        logger.info("Tables dropped.")

    # ── Create tables ─────────────────────────────────────────────────────────
    logger.info("Creating tables...")

    with engine.connect() as conn:

        # Enable pgvector (idempotent)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

        # analysts
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.analysts (
                id                      SERIAL PRIMARY KEY,
                sa_publishing_id        VARCHAR(100) UNIQUE NOT NULL,
                display_name            VARCHAR(200) NOT NULL,
                is_active               BOOLEAN NOT NULL DEFAULT TRUE,
                philosophy_cluster      INTEGER,
                philosophy_summary      TEXT,
                philosophy_source       VARCHAR(10) DEFAULT 'llm',
                philosophy_vector       vector(1536),
                philosophy_tags         JSONB,
                overall_accuracy        NUMERIC(5,4),
                sector_alpha            JSONB,
                article_count           INTEGER DEFAULT 0,
                last_article_fetched_at TIMESTAMPTZ,
                last_backtest_at        TIMESTAMPTZ,
                config                  JSONB,
                created_at              TIMESTAMPTZ DEFAULT NOW(),
                updated_at              TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        # analyst_articles
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.analyst_articles (
                id                SERIAL PRIMARY KEY,
                analyst_id        INTEGER NOT NULL
                                    REFERENCES platform_shared.analysts(id),
                sa_article_id     VARCHAR(100) UNIQUE NOT NULL,
                url_hash          CHAR(64),
                content_hash      CHAR(64),
                title             TEXT NOT NULL,
                full_text         TEXT,
                published_at      TIMESTAMPTZ NOT NULL,
                fetched_at        TIMESTAMPTZ DEFAULT NOW(),
                content_embedding vector(1536),
                tickers_mentioned TEXT[],
                metadata          JSONB,
                created_at        TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        # analyst_recommendations
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.analyst_recommendations (
                id                  SERIAL PRIMARY KEY,
                analyst_id          INTEGER NOT NULL
                                      REFERENCES platform_shared.analysts(id),
                article_id          INTEGER NOT NULL
                                      REFERENCES platform_shared.analyst_articles(id),
                ticker              VARCHAR(20) NOT NULL,
                sector              VARCHAR(50),
                asset_class         VARCHAR(20),
                recommendation      VARCHAR(20),
                sentiment_score     NUMERIC(4,3),
                yield_at_publish    NUMERIC(6,4),
                payout_ratio        NUMERIC(6,4),
                dividend_cagr_3yr   NUMERIC(6,4),
                dividend_cagr_5yr   NUMERIC(6,4),
                safety_grade        VARCHAR(5),
                source_reliability  VARCHAR(20),
                content_embedding   vector(1536),
                metadata            JSONB,
                published_at        TIMESTAMPTZ NOT NULL,
                expires_at          TIMESTAMPTZ NOT NULL,
                decay_weight        NUMERIC(5,4) DEFAULT 1.0,
                is_active           BOOLEAN NOT NULL DEFAULT TRUE,
                superseded_by       INTEGER
                                      REFERENCES platform_shared.analyst_recommendations(id),
                platform_alignment  VARCHAR(20),
                platform_scored_at  TIMESTAMPTZ,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        # analyst_accuracy_log
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.analyst_accuracy_log (
                id                      SERIAL PRIMARY KEY,
                analyst_id              INTEGER NOT NULL
                                          REFERENCES platform_shared.analysts(id),
                recommendation_id       INTEGER NOT NULL
                                          REFERENCES platform_shared.analyst_recommendations(id),
                ticker                  VARCHAR(20) NOT NULL,
                sector                  VARCHAR(50),
                asset_class             VARCHAR(20),
                original_recommendation VARCHAR(20),
                price_at_publish        NUMERIC(12,4),
                price_at_t30            NUMERIC(12,4),
                price_at_t90            NUMERIC(12,4),
                dividend_cut_occurred   BOOLEAN,
                dividend_cut_at         TIMESTAMPTZ,
                outcome_label           VARCHAR(20),
                accuracy_delta          NUMERIC(5,4),
                sector_accuracy_before  NUMERIC(5,4),
                sector_accuracy_after   NUMERIC(5,4),
                user_override_occurred  BOOLEAN DEFAULT FALSE,
                override_outcome_label  VARCHAR(20),
                backtest_run_at         TIMESTAMPTZ DEFAULT NOW(),
                notes                   TEXT
            )
        """))

        # credit_overrides
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.credit_overrides (
                id              SERIAL PRIMARY KEY,
                ticker          VARCHAR(20) UNIQUE NOT NULL,
                override_grade  VARCHAR(5) NOT NULL,
                reason          TEXT,
                set_by          VARCHAR(100),
                reviewed_at     TIMESTAMPTZ,
                expires_at      TIMESTAMPTZ,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        conn.commit()

    # ── Indexes ───────────────────────────────────────────────────────────────
    logger.info("Creating indexes...")

    with engine.connect() as conn:
        indexes = [
            # analysts
            "CREATE INDEX IF NOT EXISTS ix_analysts_sa_id ON platform_shared.analysts(sa_publishing_id)",
            "CREATE INDEX IF NOT EXISTS ix_analysts_active ON platform_shared.analysts(is_active)",

            # analyst_articles
            "CREATE INDEX IF NOT EXISTS ix_articles_analyst_published ON platform_shared.analyst_articles(analyst_id, published_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_articles_url_hash ON platform_shared.analyst_articles(url_hash)",
            "CREATE INDEX IF NOT EXISTS ix_articles_content_hash ON platform_shared.analyst_articles(content_hash)",

            # analyst_recommendations — composite for consensus queries
            "CREATE INDEX IF NOT EXISTS ix_recs_ticker_active_weight ON platform_shared.analyst_recommendations(ticker, is_active, decay_weight DESC)",
            "CREATE INDEX IF NOT EXISTS ix_recs_analyst_ticker_published ON platform_shared.analyst_recommendations(analyst_id, ticker, published_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_recs_expires_at ON platform_shared.analyst_recommendations(expires_at)",

            # analyst_accuracy_log
            "CREATE INDEX IF NOT EXISTS ix_accuracy_analyst ON platform_shared.analyst_accuracy_log(analyst_id)",
            "CREATE INDEX IF NOT EXISTS ix_accuracy_ticker ON platform_shared.analyst_accuracy_log(ticker)",

            # credit_overrides
            "CREATE INDEX IF NOT EXISTS ix_credit_overrides_ticker ON platform_shared.credit_overrides(ticker)",
        ]

        for idx_sql in indexes:
            conn.execute(text(idx_sql))

        conn.commit()

    # ── Vector indexes (IVFFlat for approximate nearest neighbor) ─────────────
    logger.info("Creating vector indexes (IVFFlat)...")

    with engine.connect() as conn:
        # Note: IVFFlat requires data to be present before it can be built.
        # These are created with IF NOT EXISTS — will no-op if already present.
        # If tables are empty, run this again after seeding initial data.
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_articles_embedding
                ON platform_shared.analyst_articles
                USING ivfflat (content_embedding vector_cosine_ops)
                WITH (lists = 100)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_recs_embedding
                ON platform_shared.analyst_recommendations
                USING ivfflat (content_embedding vector_cosine_ops)
                WITH (lists = 100)
            """))
            conn.commit()
            logger.info("Vector indexes created.")
        except Exception as e:
            conn.rollback()
            logger.warning(
                f"Vector indexes skipped (likely empty table — re-run after seeding data): {e}"
            )

    logger.info("✅ Migration complete. All Agent 02 tables are ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 02 database migration")
    parser.add_argument(
        "--drop-first",
        action="store_true",
        help="Drop all Agent 02 tables before creating (DESTRUCTIVE — use with caution)"
    )
    args = parser.parse_args()

    if args.drop_first:
        confirm = input("⚠️  This will DROP all Agent 02 tables. Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            logger.info("Aborted.")
            sys.exit(0)

    run_migration(drop_first=args.drop_first)
