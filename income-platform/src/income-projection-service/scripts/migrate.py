"""
Migration script — creates income_projections table in platform_shared.
Run once per environment: python -m scripts.migrate
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS platform_shared.income_projections (
    id                          SERIAL PRIMARY KEY,
    portfolio_id                UUID NOT NULL,
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    horizon_months              INTEGER NOT NULL DEFAULT 12,
    total_projected_annual      NUMERIC(12, 2),
    total_projected_monthly_avg NUMERIC(12, 2),
    yield_used                  VARCHAR(20),
    positions_included          INTEGER,
    positions_missing_data      INTEGER,
    position_detail             JSONB,
    metadata                    JSONB
);

CREATE INDEX IF NOT EXISTS idx_income_projections_portfolio_id
    ON platform_shared.income_projections (portfolio_id);

CREATE INDEX IF NOT EXISTS idx_income_projections_computed_at
    ON platform_shared.income_projections (computed_at DESC);
"""


def run_migration() -> None:
    # Import here so env vars are set before module-level engine is created.
    from app.database import engine
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(DDL))
    logger.info("Migration complete — income_projections table is ready.")


if __name__ == "__main__":
    run_migration()
