"""
Agent 06 — Scenario Simulation Service
Migration: creates platform_shared.scenario_results table (idempotent).
Run from service root: python scripts/migrate.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from sqlalchemy import create_engine, text


def _build_url() -> str:
    url = settings.database_url
    if "?" in url:
        url = url.split("?")[0]
    return url


DDL = """
CREATE SCHEMA IF NOT EXISTS platform_shared;

CREATE TABLE IF NOT EXISTS platform_shared.scenario_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID NOT NULL,
    scenario_name   VARCHAR(50) NOT NULL,
    scenario_type   VARCHAR(20) NOT NULL,
    scenario_params JSONB,
    result_summary  JSONB NOT NULL,
    vulnerability_ranking JSONB,
    projected_income_p10  NUMERIC(12, 2),
    projected_income_p50  NUMERIC(12, 2),
    projected_income_p90  NUMERIC(12, 2),
    label           VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_scenario_results_portfolio_created
    ON platform_shared.scenario_results (portfolio_id, created_at);
"""


def main():
    engine = create_engine(
        _build_url(),
        connect_args={"sslmode": "require"},
    )
    with engine.begin() as conn:
        conn.execute(text(DDL))
    print("Migration complete: platform_shared.scenario_results ready.")


if __name__ == "__main__":
    main()
