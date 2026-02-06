-- Migration: NAV Erosion Analysis Tables
-- Version: V2.0__nav_erosion_analysis.sql
-- Description: Add tables for Monte Carlo NAV erosion analysis and caching

BEGIN;

-- Table: covered_call_etf_metrics
-- Stores historical data for covered call ETF analysis
CREATE TABLE IF NOT EXISTS covered_call_etf_metrics (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    data_date DATE NOT NULL,
    
    -- NAV & Price data
    nav FLOAT NOT NULL,
    market_price FLOAT NOT NULL,
    premium_discount_pct FLOAT,
    
    -- Distribution data
    monthly_distribution FLOAT,
    distribution_yield_ttm FLOAT,
    roc_percentage FLOAT,  -- Percentage that's Return of Capital
    
    -- Options data
    monthly_premium_yield FLOAT,  -- Premium captured / NAV
    implied_volatility FLOAT,
    
    -- Underlying index data
    underlying_return_1m FLOAT,
    underlying_volatility_30d FLOAT,
    
    -- Fund structure
    expense_ratio FLOAT,
    leverage_ratio FLOAT DEFAULT 1.0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_ticker_date UNIQUE(ticker, data_date),
    CONSTRAINT positive_nav CHECK (nav > 0),
    CONSTRAINT positive_price CHECK (market_price > 0),
    CONSTRAINT valid_expense_ratio CHECK (expense_ratio >= 0 AND expense_ratio <= 0.10)
);

CREATE INDEX idx_cc_etf_ticker_date ON covered_call_etf_metrics(ticker, data_date DESC);
CREATE INDEX idx_cc_etf_date ON covered_call_etf_metrics(data_date DESC);

COMMENT ON TABLE covered_call_etf_metrics IS 'Historical metrics for covered call ETFs used in NAV erosion analysis';
COMMENT ON COLUMN covered_call_etf_metrics.monthly_premium_yield IS 'Option premium captured as percentage of NAV';
COMMENT ON COLUMN covered_call_etf_metrics.roc_percentage IS 'Percentage of distribution that is Return of Capital';


-- Table: nav_erosion_analysis_cache
-- Caches Monte Carlo simulation results
CREATE TABLE IF NOT EXISTS nav_erosion_analysis_cache (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    analysis_date DATE NOT NULL DEFAULT CURRENT_DATE,
    analysis_type VARCHAR(20) NOT NULL,  -- 'quick' or 'deep'
    
    -- Simulation results (JSONB for flexibility)
    simulation_results JSONB NOT NULL,
    
    -- Key metrics (denormalized for fast queries)
    median_annualized_nav_change_pct FLOAT,
    probability_erosion_gt_5pct FLOAT,
    probability_erosion_gt_10pct FLOAT,
    
    -- Sustainability score impact
    sustainability_penalty FLOAT,  -- Points deducted from sustainability score
    
    -- Cache management
    valid_until DATE NOT NULL,  -- Cache expiry date
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_ticker_analysis UNIQUE(ticker, analysis_date, analysis_type),
    CONSTRAINT valid_analysis_type CHECK (analysis_type IN ('quick', 'deep')),
    CONSTRAINT valid_penalty CHECK (sustainability_penalty >= 0 AND sustainability_penalty <= 30)
);

CREATE INDEX idx_nav_cache_ticker ON nav_erosion_analysis_cache(ticker, valid_until DESC);
CREATE INDEX idx_nav_cache_valid ON nav_erosion_analysis_cache(valid_until DESC);
CREATE INDEX idx_nav_cache_analysis_date ON nav_erosion_analysis_cache(analysis_date DESC);

COMMENT ON TABLE nav_erosion_analysis_cache IS 'Cached Monte Carlo NAV erosion analysis results';
COMMENT ON COLUMN nav_erosion_analysis_cache.simulation_results IS 'Full JSON results from Monte Carlo simulation';
COMMENT ON COLUMN nav_erosion_analysis_cache.sustainability_penalty IS 'Points to deduct from sustainability score (0-30)';


-- Table: nav_erosion_data_collection_log
-- Audit trail for data collection
CREATE TABLE IF NOT EXISTS nav_erosion_data_collection_log (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    collection_date TIMESTAMP NOT NULL DEFAULT NOW(),
    params_json JSONB NOT NULL,
    completeness_score FLOAT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_completeness CHECK (completeness_score >= 0 AND completeness_score <= 100)
);

CREATE INDEX idx_nav_collection_ticker ON nav_erosion_data_collection_log(ticker, collection_date DESC);

COMMENT ON TABLE nav_erosion_data_collection_log IS 'Audit trail for NAV erosion data collection';
COMMENT ON COLUMN nav_erosion_data_collection_log.completeness_score IS 'Data quality score (0-100)';


-- Extend income_scores table with NAV erosion fields
-- (Only add if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'income_scores') THEN
        -- Add NAV erosion columns if they don't exist
        ALTER TABLE income_scores 
            ADD COLUMN IF NOT EXISTS nav_erosion_penalty FLOAT DEFAULT 0,
            ADD COLUMN IF NOT EXISTS nav_erosion_analysis_date DATE,
            ADD COLUMN IF NOT EXISTS nav_erosion_risk_category VARCHAR(20);
        
        -- Add constraint for valid risk categories
        ALTER TABLE income_scores 
            DROP CONSTRAINT IF EXISTS valid_nav_risk_category;
        ALTER TABLE income_scores 
            ADD CONSTRAINT valid_nav_risk_category 
            CHECK (nav_erosion_risk_category IN ('minimal', 'low', 'moderate', 'high', 'severe', NULL));
        
        -- Add index for NAV erosion queries
        CREATE INDEX IF NOT EXISTS idx_income_scores_nav_risk 
            ON income_scores(nav_erosion_risk_category);
    END IF;
END$$;


-- Function: Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for covered_call_etf_metrics
DROP TRIGGER IF EXISTS update_cc_etf_metrics_updated_at ON covered_call_etf_metrics;
CREATE TRIGGER update_cc_etf_metrics_updated_at
    BEFORE UPDATE ON covered_call_etf_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- View: Latest NAV Erosion Analysis
CREATE OR REPLACE VIEW v_latest_nav_erosion_analysis AS
SELECT DISTINCT ON (ticker)
    ticker,
    analysis_type,
    median_annualized_nav_change_pct,
    probability_erosion_gt_5pct,
    probability_erosion_gt_10pct,
    sustainability_penalty,
    analysis_date,
    valid_until,
    CURRENT_DATE <= valid_until AS is_valid
FROM nav_erosion_analysis_cache
ORDER BY ticker, analysis_date DESC;

COMMENT ON VIEW v_latest_nav_erosion_analysis IS 'Latest NAV erosion analysis for each ticker';


-- View: Covered Call ETF Portfolio Risk
CREATE OR REPLACE VIEW v_covered_call_etf_risk_summary AS
SELECT 
    ticker,
    CASE 
        WHEN probability_erosion_gt_5pct <= 20 THEN 'minimal'
        WHEN probability_erosion_gt_5pct <= 40 THEN 'low'
        WHEN probability_erosion_gt_5pct <= 60 THEN 'moderate'
        WHEN probability_erosion_gt_5pct <= 80 THEN 'high'
        ELSE 'severe'
    END AS risk_category,
    median_annualized_nav_change_pct,
    probability_erosion_gt_5pct,
    probability_erosion_gt_10pct,
    sustainability_penalty,
    analysis_date
FROM v_latest_nav_erosion_analysis
WHERE is_valid = true;

COMMENT ON VIEW v_covered_call_etf_risk_summary IS 'Risk classification for all analyzed covered call ETFs';


-- Seed data: Sample covered call ETF metrics (for testing)
-- This would normally be populated by data collection process
INSERT INTO covered_call_etf_metrics (ticker, data_date, nav, market_price, monthly_premium_yield, 
                                       underlying_return_1m, monthly_distribution, expense_ratio)
VALUES 
    ('JEPI', CURRENT_DATE - INTERVAL '1 month', 50.0, 50.5, 0.007, 0.02, 0.36, 0.0035),
    ('JEPI', CURRENT_DATE - INTERVAL '2 months', 49.5, 49.8, 0.008, -0.01, 0.37, 0.0035),
    ('JEPI', CURRENT_DATE - INTERVAL '3 months', 50.2, 50.3, 0.006, 0.03, 0.36, 0.0035),
    ('QYLD', CURRENT_DATE - INTERVAL '1 month', 17.5, 17.6, 0.009, 0.01, 0.18, 0.0060),
    ('QYLD', CURRENT_DATE - INTERVAL '2 months', 17.3, 17.4, 0.010, -0.02, 0.19, 0.0060)
ON CONFLICT (ticker, data_date) DO NOTHING;


-- Grant permissions (adjust based on your user setup)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO income_platform_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO income_platform_app;


COMMIT;

-- Verification queries (run separately to test)
-- SELECT COUNT(*) FROM covered_call_etf_metrics;
-- SELECT * FROM v_latest_nav_erosion_analysis;
-- SELECT * FROM v_covered_call_etf_risk_summary;
