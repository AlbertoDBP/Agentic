"""
Agent 03 — Income Scoring Service
Migration: Create all 3 tables in platform_shared schema
"""
import sys
import argparse
import logging
from sqlalchemy import text

sys.path.insert(0, "..")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_migration(drop_first: bool = False):
    from app.database import engine, check_database_connection

    logger.info("Running pre-flight database checks...")
    health = check_database_connection()

    if health["status"] != "healthy":
        logger.error(f"Database connection failed: {health.get('error')}")
        sys.exit(1)

    if not health.get("schema_exists"):
        logger.info("Schema 'platform_shared' does not exist — creating...")
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS platform_shared"))
            conn.commit()

    if drop_first:
        logger.warning("Dropping all Agent 03 tables...")
        with engine.connect() as conn:
            conn.execute(text("""
                DROP TABLE IF EXISTS platform_shared.income_scores CASCADE;
                DROP TABLE IF EXISTS platform_shared.quality_gate_results CASCADE;
                DROP TABLE IF EXISTS platform_shared.scoring_runs CASCADE;
            """))
            conn.commit()

    logger.info("Creating tables...")
    with engine.connect() as conn:

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.scoring_runs (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                run_type            VARCHAR(20) NOT NULL,
                triggered_by        VARCHAR(50),
                tickers_requested   INTEGER NOT NULL DEFAULT 0,
                tickers_gate_passed INTEGER NOT NULL DEFAULT 0,
                tickers_gate_failed INTEGER NOT NULL DEFAULT 0,
                tickers_scored      INTEGER NOT NULL DEFAULT 0,
                tickers_errored     INTEGER NOT NULL DEFAULT 0,
                started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at        TIMESTAMPTZ,
                duration_seconds    FLOAT,
                status              VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
                error_summary       TEXT,
                config_snapshot     JSONB,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.quality_gate_results (
                id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ticker                  VARCHAR(20) NOT NULL,
                asset_class             VARCHAR(30) NOT NULL,
                passed                  BOOLEAN NOT NULL,
                fail_reasons            JSONB,
                credit_rating           VARCHAR(10),
                credit_rating_passed    BOOLEAN,
                consecutive_fcf_years   INTEGER,
                fcf_passed              BOOLEAN,
                dividend_history_years  INTEGER,
                dividend_history_passed BOOLEAN,
                etf_aum_millions        FLOAT,
                etf_aum_passed          BOOLEAN,
                etf_track_record_years  FLOAT,
                etf_track_record_passed BOOLEAN,
                reit_coverage_ratio     FLOAT,
                reit_coverage_passed    BOOLEAN,
                data_quality_score      FLOAT,
                evaluated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                valid_until             TIMESTAMPTZ,
                scoring_run_id          UUID REFERENCES platform_shared.scoring_runs(id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.income_scores (
                id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ticker                      VARCHAR(20) NOT NULL,
                asset_class                 VARCHAR(30) NOT NULL,
                valuation_yield_score       FLOAT NOT NULL,
                financial_durability_score  FLOAT NOT NULL,
                technical_entry_score       FLOAT NOT NULL,
                total_score_raw             FLOAT NOT NULL,
                nav_erosion_penalty         FLOAT NOT NULL DEFAULT 0,
                total_score                 FLOAT NOT NULL,
                grade                       VARCHAR(5) NOT NULL,
                recommendation              VARCHAR(20) NOT NULL,
                factor_details              JSONB,
                nav_erosion_details         JSONB,
                data_quality_score          FLOAT,
                data_completeness_pct       FLOAT,
                scored_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                valid_until                 TIMESTAMPTZ,
                scoring_run_id              UUID REFERENCES platform_shared.scoring_runs(id),
                quality_gate_id             UUID REFERENCES platform_shared.quality_gate_results(id)
            )
        """))

        conn.commit()

    logger.info("Creating indexes...")
    with engine.connect() as conn:
        for idx in [
            "CREATE INDEX IF NOT EXISTS ix_scoring_runs_started ON platform_shared.scoring_runs(started_at)",
            "CREATE INDEX IF NOT EXISTS ix_scoring_runs_status ON platform_shared.scoring_runs(status)",
            "CREATE INDEX IF NOT EXISTS ix_qg_ticker_evaluated ON platform_shared.quality_gate_results(ticker, evaluated_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_income_scores_ticker_scored ON platform_shared.income_scores(ticker, scored_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_income_scores_recommendation ON platform_shared.income_scores(recommendation)",
        ]:
            conn.execute(text(idx))
        conn.commit()

    logger.info("✅ Migration complete. All Agent 03 tables are ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 03 database migration")
    parser.add_argument("--drop-first", action="store_true")
    args = parser.parse_args()

    if args.drop_first:
        confirm = input("⚠️  This will DROP all Agent 03 tables. Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            sys.exit(0)

    run_migration(drop_first=args.drop_first)
