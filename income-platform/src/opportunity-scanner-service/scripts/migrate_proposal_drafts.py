"""
Create platform_shared.proposal_drafts table.
Safe to run multiple times (uses IF NOT EXISTS).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlalchemy as sa
from app.config import settings

DDL = """
CREATE TABLE IF NOT EXISTS platform_shared.proposal_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID REFERENCES platform_shared.scan_results(id),
    target_portfolio_id UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    tickers             JSONB NOT NULL,
    entry_limits        JSONB NOT NULL,
    status              TEXT NOT NULL DEFAULT 'DRAFT',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_proposal_drafts_created_at
    ON platform_shared.proposal_drafts (created_at);
"""

engine = sa.create_engine(settings.database_url)
with engine.connect() as conn:
    conn.execute(sa.text(DDL))
    conn.commit()
    print("proposal_drafts table ready.")
