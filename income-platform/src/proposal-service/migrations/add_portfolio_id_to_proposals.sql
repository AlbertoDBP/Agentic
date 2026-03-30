ALTER TABLE platform_shared.proposals
    ADD COLUMN IF NOT EXISTS portfolio_id TEXT NULL;
