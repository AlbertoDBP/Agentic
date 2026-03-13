"""Migration script: create platform_shared.proposals table."""
import os
import sys

from sqlalchemy import create_engine, text

DDL = """
CREATE SCHEMA IF NOT EXISTS platform_shared;

CREATE TABLE IF NOT EXISTS platform_shared.proposals (
    id                    SERIAL PRIMARY KEY,
    ticker                VARCHAR(20) NOT NULL,
    analyst_signal_id     INTEGER,
    analyst_id            INTEGER,
    platform_score        NUMERIC(5,1),
    platform_alignment    VARCHAR(20),
    veto_flags            JSONB,
    divergence_notes      TEXT,

    -- Lens 1: Analyst
    analyst_recommendation  VARCHAR(20),
    analyst_sentiment       NUMERIC(6,4),
    analyst_thesis_summary  TEXT,
    analyst_yield_estimate  NUMERIC(8,4),
    analyst_safety_grade    VARCHAR(10),

    -- Lens 2: Platform
    platform_yield_estimate NUMERIC(8,4),
    platform_safety_result  JSONB,
    platform_income_grade   VARCHAR(5),

    -- Execution Parameters (from Agent 04 entry-price)
    entry_price_low         NUMERIC(10,2),
    entry_price_high        NUMERIC(10,2),
    position_size_pct       NUMERIC(5,2),
    recommended_account     VARCHAR(50),
    sizing_rationale        TEXT,

    -- State
    status                  VARCHAR(30) DEFAULT 'pending',
    trigger_mode            VARCHAR(30),
    trigger_ref_id          TEXT,
    override_rationale      TEXT,
    user_acknowledged_veto  BOOLEAN DEFAULT FALSE,
    reviewed_by             TEXT,
    decided_at              TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_proposals_ticker ON platform_shared.proposals(ticker);
CREATE INDEX IF NOT EXISTS ix_proposals_status ON platform_shared.proposals(status);
"""


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Strip query params for psycopg2
    url = database_url.split("?")[0] if "?" in database_url else database_url

    engine = create_engine(url, connect_args={"sslmode": "require"})
    with engine.begin() as conn:
        conn.execute(text(DDL))
    print("Migration complete: platform_shared.proposals table created/verified.")


if __name__ == "__main__":
    main()
