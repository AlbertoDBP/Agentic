"""
Agent 03 — Income Scoring Service
Migration: Create all tables in platform_shared schema.

v1.0: scoring_runs, quality_gate_results, income_scores
v2.0: scoring_weight_profiles, weight_change_audit, signal_penalty_config
      + new columns on income_scores (weight_profile_id, signal_penalty)
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
                DROP TABLE IF EXISTS platform_shared.weight_change_audit CASCADE;
                DROP TABLE IF EXISTS platform_shared.signal_penalty_config CASCADE;
                DROP TABLE IF EXISTS platform_shared.income_scores CASCADE;
                DROP TABLE IF EXISTS platform_shared.quality_gate_results CASCADE;
                DROP TABLE IF EXISTS platform_shared.scoring_runs CASCADE;
                DROP TABLE IF EXISTS platform_shared.scoring_weight_profiles CASCADE;
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
            CREATE TABLE IF NOT EXISTS platform_shared.scoring_weight_profiles (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                asset_class         VARCHAR(50)  NOT NULL,
                version             INTEGER      NOT NULL DEFAULT 1,
                is_active           BOOLEAN      NOT NULL DEFAULT true,
                weight_yield        SMALLINT     NOT NULL,
                weight_durability   SMALLINT     NOT NULL,
                weight_technical    SMALLINT     NOT NULL,
                yield_sub_weights   JSONB        NOT NULL,
                durability_sub_weights JSONB     NOT NULL,
                technical_sub_weights  JSONB     NOT NULL,
                source              VARCHAR(30)  NOT NULL DEFAULT 'MANUAL',
                change_reason       TEXT,
                created_by          VARCHAR(100),
                created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                activated_at        TIMESTAMPTZ,
                superseded_at       TIMESTAMPTZ,
                superseded_by_id    UUID REFERENCES platform_shared.scoring_weight_profiles(id),
                CONSTRAINT chk_swp_weights_sum CHECK (weight_yield + weight_durability + weight_technical = 100),
                CONSTRAINT chk_swp_pillar_range CHECK (
                    weight_yield BETWEEN 1 AND 98 AND
                    weight_durability BETWEEN 1 AND 98 AND
                    weight_technical BETWEEN 1 AND 98
                )
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
                quality_gate_id             UUID REFERENCES platform_shared.quality_gate_results(id),
                weight_profile_id           UUID REFERENCES platform_shared.scoring_weight_profiles(id),
                signal_penalty              FLOAT NOT NULL DEFAULT 0.0
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.weight_change_audit (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                asset_class         VARCHAR(50)  NOT NULL,
                old_profile_id      UUID REFERENCES platform_shared.scoring_weight_profiles(id),
                new_profile_id      UUID NOT NULL REFERENCES platform_shared.scoring_weight_profiles(id),
                delta_weight_yield      SMALLINT,
                delta_weight_durability SMALLINT,
                delta_weight_technical  SMALLINT,
                trigger_type        VARCHAR(30)  NOT NULL,
                trigger_details     JSONB,
                changed_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                changed_by          VARCHAR(100)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS platform_shared.signal_penalty_config (
                id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                is_active                   BOOLEAN      NOT NULL DEFAULT true,
                version                     INTEGER      NOT NULL DEFAULT 1,
                bearish_strong_penalty      NUMERIC(4,1) NOT NULL DEFAULT 8.0,
                bearish_moderate_penalty    NUMERIC(4,1) NOT NULL DEFAULT 5.0,
                bearish_weak_penalty        NUMERIC(4,1) NOT NULL DEFAULT 2.0,
                bullish_strong_bonus_cap    NUMERIC(4,1) NOT NULL DEFAULT 0.0,
                min_n_analysts              INTEGER      NOT NULL DEFAULT 1,
                min_decay_weight            NUMERIC(5,4) NOT NULL DEFAULT 0.3000,
                consensus_bearish_threshold NUMERIC(4,3) NOT NULL DEFAULT -0.200,
                consensus_bullish_threshold NUMERIC(4,3) NOT NULL DEFAULT 0.200,
                created_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                created_by                  VARCHAR(100),
                notes                       TEXT
            )
        """))

        conn.commit()

    # ── ADD columns to income_scores if upgrading from v1.0 ──────────────────
    logger.info("Applying v2.0 column additions (idempotent)...")
    with engine.connect() as conn:
        for col_sql in [
            """ALTER TABLE platform_shared.income_scores
               ADD COLUMN IF NOT EXISTS weight_profile_id UUID
               REFERENCES platform_shared.scoring_weight_profiles(id)""",
            """ALTER TABLE platform_shared.income_scores
               ADD COLUMN IF NOT EXISTS signal_penalty FLOAT NOT NULL DEFAULT 0.0""",
        ]:
            conn.execute(text(col_sql))
        conn.commit()

    logger.info("Creating indexes...")
    with engine.connect() as conn:
        for idx in [
            "CREATE INDEX IF NOT EXISTS ix_scoring_runs_started ON platform_shared.scoring_runs(started_at)",
            "CREATE INDEX IF NOT EXISTS ix_scoring_runs_status ON platform_shared.scoring_runs(status)",
            "CREATE INDEX IF NOT EXISTS ix_qg_ticker_evaluated ON platform_shared.quality_gate_results(ticker, evaluated_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_income_scores_ticker_scored ON platform_shared.income_scores(ticker, scored_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_income_scores_recommendation ON platform_shared.income_scores(recommendation)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_swp_asset_class_active ON platform_shared.scoring_weight_profiles(asset_class) WHERE is_active = true",
            "CREATE INDEX IF NOT EXISTS ix_swp_asset_class_history ON platform_shared.scoring_weight_profiles(asset_class, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_wca_asset_class_changed ON platform_shared.weight_change_audit(asset_class, changed_at DESC)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_spc_active ON platform_shared.signal_penalty_config(is_active) WHERE is_active = true",
        ]:
            conn.execute(text(idx))
        conn.commit()

    _seed_weight_profiles(engine)
    _seed_signal_penalty_config(engine)

    logger.info("✅ Migration complete. All Agent 03 tables are ready.")


# ── Seed data ─────────────────────────────────────────────────────────────────

# Sub-weights derived from v1.0 scorer's fixed point allocation:
#   Yield (40 pts):      payout_sustainability=16 (40%), yield_vs_market=14 (35%), fcf_coverage=10 (25%)
#   Durability (40 pts): debt_safety=16 (40%), dividend_consistency=14 (35%), volatility_score=10 (25%)
#   Technical (20 pts):  price_momentum=12 (60%), price_range_position=8 (40%)
_DEFAULT_YIELD_SUB       = '{"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25}'
_DEFAULT_DURABILITY_SUB  = '{"debt_safety": 40, "dividend_consistency": 35, "volatility_score": 25}'
_DEFAULT_TECHNICAL_SUB   = '{"price_momentum": 60, "price_range_position": 40}'

# Initial seed pillar weights per asset class (sum = 100 each)
_SEED_PROFILES = [
    ("MORTGAGE_REIT",    30, 45, 25),
    ("BDC",              35, 40, 25),
    ("COVERED_CALL_ETF", 40, 30, 30),
    ("EQUITY_REIT",      30, 40, 30),
    ("DIVIDEND_STOCK",   25, 45, 30),
    ("BOND",             35, 50, 15),
    ("PREFERRED_STOCK",  40, 45, 15),
]


def _seed_weight_profiles(engine) -> None:
    """Insert initial weight profiles if they don't already exist."""
    import json
    now_sql = "NOW()"
    with engine.connect() as conn:
        for asset_class, wy, wd, wt in _SEED_PROFILES:
            existing = conn.execute(text(
                "SELECT 1 FROM platform_shared.scoring_weight_profiles "
                "WHERE asset_class = :ac LIMIT 1"
            ), {"ac": asset_class}).fetchone()
            if existing:
                logger.info("Weight profile already exists for %s — skipping seed", asset_class)
                continue

            conn.execute(text("""
                INSERT INTO platform_shared.scoring_weight_profiles
                    (asset_class, version, is_active,
                     weight_yield, weight_durability, weight_technical,
                     yield_sub_weights, durability_sub_weights, technical_sub_weights,
                     source, change_reason, created_by, created_at, activated_at)
                VALUES
                    (:ac, 1, true,
                     :wy, :wd, :wt,
                     :ysub::jsonb, :dsub::jsonb, :tsub::jsonb,
                     'INITIAL_SEED', 'v2.0 initial seed weights', 'migration',
                     NOW(), NOW())
            """), {
                "ac": asset_class, "wy": wy, "wd": wd, "wt": wt,
                "ysub": _DEFAULT_YIELD_SUB,
                "dsub": _DEFAULT_DURABILITY_SUB,
                "tsub": _DEFAULT_TECHNICAL_SUB,
            })

            # Write audit row for initial seed
            profile_id = conn.execute(text(
                "SELECT id FROM platform_shared.scoring_weight_profiles "
                "WHERE asset_class = :ac AND source = 'INITIAL_SEED' ORDER BY created_at DESC LIMIT 1"
            ), {"ac": asset_class}).fetchone()[0]

            conn.execute(text("""
                INSERT INTO platform_shared.weight_change_audit
                    (asset_class, old_profile_id, new_profile_id,
                     delta_weight_yield, delta_weight_durability, delta_weight_technical,
                     trigger_type, trigger_details, changed_at, changed_by)
                VALUES
                    (:ac, NULL, :pid,
                     NULL, NULL, NULL,
                     'INITIAL_SEED',
                     '{"source": "v2.0 migration"}'::jsonb,
                     NOW(), 'migration')
            """), {"ac": asset_class, "pid": profile_id})

            logger.info("Seeded weight profile for %s (Y=%d/D=%d/T=%d)", asset_class, wy, wd, wt)

        conn.commit()


def _seed_signal_penalty_config(engine) -> None:
    """Insert default signal penalty config if none exists."""
    with engine.connect() as conn:
        existing = conn.execute(text(
            "SELECT 1 FROM platform_shared.signal_penalty_config LIMIT 1"
        )).fetchone()
        if existing:
            logger.info("Signal penalty config already exists — skipping seed")
            return

        conn.execute(text("""
            INSERT INTO platform_shared.signal_penalty_config
                (is_active, version,
                 bearish_strong_penalty, bearish_moderate_penalty, bearish_weak_penalty,
                 bullish_strong_bonus_cap,
                 min_n_analysts, min_decay_weight,
                 consensus_bearish_threshold, consensus_bullish_threshold,
                 created_by, notes)
            VALUES
                (true, 1,
                 8.0, 5.0, 2.0, 0.0,
                 1, 0.3000,
                 -0.200, 0.200,
                 'migration', 'v2.0 default signal penalty configuration')
        """))
        conn.commit()
        logger.info("Seeded default signal penalty config")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 03 database migration")
    parser.add_argument("--drop-first", action="store_true")
    args = parser.parse_args()

    if args.drop_first:
        confirm = input("⚠️  This will DROP all Agent 03 tables. Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            sys.exit(0)

    run_migration(drop_first=args.drop_first)
