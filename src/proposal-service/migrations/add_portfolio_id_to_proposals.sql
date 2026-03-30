-- src/proposal-service/migrations/add_portfolio_id_to_proposals.sql
-- Add portfolio_id to proposals table for grouping in execution UI
ALTER TABLE platform_shared.proposals
    ADD COLUMN IF NOT EXISTS portfolio_id UUID NULL;

COMMENT ON COLUMN platform_shared.proposals.portfolio_id
    IS 'Target portfolio for this proposal — set at generation time';
