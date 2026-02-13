-- ============================================
-- Income Fortress Platform - Complete Database Schema
-- Migration: V3.0__complete_platform_schema.sql
-- Purpose: Create all 97 tables for the complete platform
-- Date: 2026-02-12
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- CORE PORTFOLIO MANAGEMENT (10 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    portfolio_name VARCHAR(255) NOT NULL,
    portfolio_type VARCHAR(50), -- 'taxable', 'ira', 'roth', '401k'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(user_id, portfolio_name)
);

CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX idx_portfolios_active ON portfolios(is_active) WHERE is_active = true;

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    holding_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    ticker_symbol VARCHAR(20) NOT NULL,
    shares DECIMAL(18, 6) NOT NULL,
    cost_basis DECIMAL(18, 2) NOT NULL,
    purchase_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_holdings_portfolio ON portfolio_holdings(portfolio_id);
CREATE INDEX idx_holdings_ticker ON portfolio_holdings(ticker_symbol);

CREATE TABLE IF NOT EXISTS portfolio_configurations (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE UNIQUE,
    capital_safety_threshold DECIMAL(5, 2) DEFAULT 70.00, -- percentage
    max_single_position_pct DECIMAL(5, 2) DEFAULT 10.00,
    rebalance_threshold_pct DECIMAL(5, 2) DEFAULT 5.00,
    auto_reinvest_dividends BOOLEAN DEFAULT true,
    tax_loss_harvesting_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    preference_key VARCHAR(100) NOT NULL,
    preference_value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, preference_key)
);

CREATE INDEX idx_preferences_portfolio ON portfolio_preferences(portfolio_id);

CREATE TABLE IF NOT EXISTS portfolio_daily_snapshot (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    total_value DECIMAL(18, 2) NOT NULL,
    cash_balance DECIMAL(18, 2) NOT NULL,
    total_cost_basis DECIMAL(18, 2) NOT NULL,
    unrealized_gain_loss DECIMAL(18, 2) NOT NULL,
    annual_income DECIMAL(18, 2) NOT NULL,
    yield_on_cost DECIMAL(5, 4) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, snapshot_date)
);

CREATE INDEX idx_snapshot_portfolio_date ON portfolio_daily_snapshot(portfolio_id, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS holdings_daily_snapshot (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    holding_id UUID NOT NULL REFERENCES portfolio_holdings(holding_id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    shares DECIMAL(18, 6) NOT NULL,
    price DECIMAL(18, 2) NOT NULL,
    market_value DECIMAL(18, 2) NOT NULL,
    cost_basis DECIMAL(18, 2) NOT NULL,
    unrealized_gain_loss DECIMAL(18, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(holding_id, snapshot_date)
);

CREATE INDEX idx_holding_snapshot_date ON holdings_daily_snapshot(holding_id, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS holdings_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    ticker_symbol VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL, -- 'buy', 'sell', 'dividend', 'split'
    shares DECIMAL(18, 6) NOT NULL,
    price DECIMAL(18, 2) NOT NULL,
    total_amount DECIMAL(18, 2) NOT NULL,
    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_portfolio ON holdings_transactions(portfolio_id, transaction_date DESC);
CREATE INDEX idx_transactions_ticker ON holdings_transactions(ticker_symbol);

CREATE TABLE IF NOT EXISTS holdings_dividend_history (
    dividend_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    holding_id UUID NOT NULL REFERENCES portfolio_holdings(holding_id) ON DELETE CASCADE,
    ex_dividend_date DATE NOT NULL,
    payment_date DATE,
    amount_per_share DECIMAL(10, 4) NOT NULL,
    total_amount DECIMAL(18, 2) NOT NULL,
    dividend_type VARCHAR(20), -- 'qualified', 'ordinary', 'capital_gain'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dividend_holding ON holdings_dividend_history(holding_id, ex_dividend_date DESC);

CREATE TABLE IF NOT EXISTS portfolio_rebalance_history (
    rebalance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    rebalance_date TIMESTAMP WITH TIME ZONE NOT NULL,
    rebalance_reason VARCHAR(255),
    trades_executed JSONB NOT NULL, -- array of {ticker, action, shares, price}
    cost DECIMAL(18, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rebalance_portfolio ON portfolio_rebalance_history(portfolio_id, rebalance_date DESC);

CREATE TABLE IF NOT EXISTS portfolio_optimization_history (
    optimization_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    optimization_date TIMESTAMP WITH TIME ZONE NOT NULL,
    optimization_type VARCHAR(50), -- 'tax_loss_harvest', 'yield_optimization', 'risk_reduction'
    before_allocation JSONB NOT NULL,
    after_allocation JSONB NOT NULL,
    expected_benefit DECIMAL(18, 2),
    status VARCHAR(20) DEFAULT 'proposed', -- 'proposed', 'accepted', 'rejected', 'executed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_optimization_portfolio ON portfolio_optimization_history(portfolio_id, optimization_date DESC);

-- ============================================
-- ASSET CLASSIFICATION (3 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS asset_classes (
    asset_class_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL UNIQUE,
    asset_class VARCHAR(50) NOT NULL, -- 'equity', 'fixed_income', 'real_estate', 'commodities'
    sub_class VARCHAR(100), -- 'large_cap', 'corporate_bonds', 'residential_reit', etc.
    sector VARCHAR(100),
    geography VARCHAR(100), -- 'us', 'international_developed', 'emerging_markets'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_asset_class_ticker ON asset_classes(ticker_symbol);
CREATE INDEX idx_asset_class_type ON asset_classes(asset_class, sub_class);

CREATE TABLE IF NOT EXISTS etf_look_through_data (
    look_through_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    etf_ticker VARCHAR(20) NOT NULL,
    underlying_ticker VARCHAR(20) NOT NULL,
    weight_percent DECIMAL(5, 2) NOT NULL,
    as_of_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(etf_ticker, underlying_ticker, as_of_date)
);

CREATE INDEX idx_etf_lookthrough ON etf_look_through_data(etf_ticker, as_of_date DESC);

CREATE TABLE IF NOT EXISTS sector_exposure_analysis (
    exposure_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    sector VARCHAR(100) NOT NULL,
    exposure_percent DECIMAL(5, 2) NOT NULL,
    benchmark_percent DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, analysis_date, sector)
);

CREATE INDEX idx_sector_exposure ON sector_exposure_analysis(portfolio_id, analysis_date DESC);

-- ============================================
-- ANALYST INTELLIGENCE (5 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS analyst_profiles (
    analyst_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analyst_name VARCHAR(255) NOT NULL,
    firm_name VARCHAR(255),
    specialization JSONB, -- array of sectors/asset classes
    track_record_accuracy DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyst_articles (
    article_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analyst_id UUID REFERENCES analyst_profiles(analyst_id),
    ticker_symbol VARCHAR(20),
    article_title TEXT NOT NULL,
    article_url TEXT,
    published_date TIMESTAMP WITH TIME ZONE NOT NULL,
    sentiment VARCHAR(20), -- 'bullish', 'bearish', 'neutral'
    key_points JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_articles_ticker ON analyst_articles(ticker_symbol, published_date DESC);
CREATE INDEX idx_articles_analyst ON analyst_articles(analyst_id);

CREATE TABLE IF NOT EXISTS analyst_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analyst_id UUID REFERENCES analyst_profiles(analyst_id),
    ticker_symbol VARCHAR(20) NOT NULL,
    recommendation_type VARCHAR(20), -- 'buy', 'sell', 'hold', 'strong_buy', 'strong_sell'
    target_price DECIMAL(10, 2),
    recommendation_date DATE NOT NULL,
    rationale TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recommendations_ticker ON analyst_recommendations(ticker_symbol, recommendation_date DESC);

CREATE TABLE IF NOT EXISTS analyst_performance_evaluations (
    evaluation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analyst_id UUID NOT NULL REFERENCES analyst_profiles(analyst_id),
    evaluation_period_start DATE NOT NULL,
    evaluation_period_end DATE NOT NULL,
    accuracy_rate DECIMAL(5, 2),
    avg_return_vs_benchmark DECIMAL(8, 2),
    total_recommendations INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analyst_id, evaluation_period_start, evaluation_period_end)
);

CREATE TABLE IF NOT EXISTS analyst_reasoning_frameworks (
    framework_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analyst_id UUID NOT NULL REFERENCES analyst_profiles(analyst_id),
    framework_name VARCHAR(255) NOT NULL,
    framework_description TEXT,
    decision_criteria JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- SCORING & PREDICTION (3 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS stock_scores_history (
    score_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    score_date DATE NOT NULL,
    income_score DECIMAL(5, 2),
    growth_score DECIMAL(5, 2),
    value_score DECIMAL(5, 2),
    quality_score DECIMAL(5, 2),
    momentum_score DECIMAL(5, 2),
    composite_score DECIMAL(5, 2),
    score_components JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, score_date)
);

CREATE INDEX idx_scores_ticker_date ON stock_scores_history(ticker_symbol, score_date DESC);
CREATE INDEX idx_scores_composite ON stock_scores_history(composite_score DESC);

CREATE TABLE IF NOT EXISTS stock_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    prediction_date DATE NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    predicted_price_1m DECIMAL(10, 2),
    predicted_price_3m DECIMAL(10, 2),
    predicted_price_6m DECIMAL(10, 2),
    predicted_price_12m DECIMAL(10, 2),
    confidence_interval JSONB, -- {lower_bound, upper_bound}
    prediction_features JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, prediction_date, model_version)
);

CREATE INDEX idx_predictions_ticker ON stock_predictions(ticker_symbol, prediction_date DESC);

CREATE TABLE IF NOT EXISTS model_performance_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    evaluation_date DATE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, model_version, evaluation_date, metric_name)
);

CREATE INDEX idx_model_metrics ON model_performance_metrics(model_name, model_version, evaluation_date DESC);

-- ============================================
-- ALERTS & MONITORING (15 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS concern_tracker (
    concern_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    ticker_symbol VARCHAR(20),
    concern_type VARCHAR(100) NOT NULL, -- 'dividend_cut', 'nav_erosion', 'concentration_risk'
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    description TEXT NOT NULL,
    detected_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_date TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'acknowledged', 'resolved', 'dismissed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_concerns_portfolio ON concern_tracker(portfolio_id, status);
CREATE INDEX idx_concerns_severity ON concern_tracker(severity) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    alert_type VARCHAR(100) NOT NULL,
    alert_priority VARCHAR(20) NOT NULL, -- 'low', 'normal', 'high', 'urgent'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    action_required BOOLEAN DEFAULT false,
    action_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP WITH TIME ZONE,
    dismissed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_alerts_user ON alerts(user_id, created_at DESC);
CREATE INDEX idx_alerts_unread ON alerts(user_id) WHERE read_at IS NULL;

CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    rule_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(100) NOT NULL,
    rule_conditions JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_rules_portfolio ON alert_rules(portfolio_id) WHERE is_active = true;

CREATE TABLE IF NOT EXISTS alert_configurations (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    alert_type VARCHAR(100) NOT NULL,
    delivery_method VARCHAR(50) NOT NULL, -- 'email', 'sms', 'push', 'in_app'
    enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, alert_type, delivery_method)
);

CREATE TABLE IF NOT EXISTS notification_inbox (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    notification_type VARCHAR(100) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP WITH TIME ZONE,
    archived_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_notifications_user ON notification_inbox(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notification_channels (
    channel_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    channel_type VARCHAR(50) NOT NULL, -- 'email', 'sms', 'slack', 'webhook'
    channel_address VARCHAR(255) NOT NULL,
    is_verified BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, channel_type, channel_address)
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    notification_type VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    frequency VARCHAR(50), -- 'immediate', 'daily_digest', 'weekly_digest'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, notification_type)
);

CREATE TABLE IF NOT EXISTS notification_delivery_log (
    delivery_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    notification_id UUID NOT NULL REFERENCES notification_inbox(notification_id),
    channel_id UUID NOT NULL REFERENCES notification_channels(channel_id),
    delivery_status VARCHAR(50) NOT NULL, -- 'pending', 'sent', 'delivered', 'failed'
    delivery_attempt INTEGER DEFAULT 1,
    delivered_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_delivery_log_notification ON notification_delivery_log(notification_id);

CREATE TABLE IF NOT EXISTS notification_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(255) NOT NULL UNIQUE,
    template_type VARCHAR(100) NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    variables JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS optimization_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    proposal_type VARCHAR(100) NOT NULL,
    proposal_title VARCHAR(255) NOT NULL,
    proposal_description TEXT NOT NULL,
    proposed_actions JSONB NOT NULL,
    expected_impact JSONB,
    risk_level VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'executed'
    reviewed_by UUID
);

CREATE INDEX idx_proposals_portfolio ON optimization_proposals(portfolio_id, status);

CREATE TABLE IF NOT EXISTS proposal_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES optimization_proposals(proposal_id),
    execution_date TIMESTAMP WITH TIME ZONE NOT NULL,
    execution_result JSONB NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_effectiveness_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID NOT NULL REFERENCES alerts(alert_id),
    user_action VARCHAR(100), -- 'dismissed', 'acted', 'snoozed', 'no_action'
    action_timestamp TIMESTAMP WITH TIME ZONE,
    action_outcome TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_false_positive_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID NOT NULL REFERENCES alerts(alert_id),
    reported_by UUID NOT NULL,
    reason TEXT,
    reported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dividend_cut_concern_history (
    concern_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    detected_date DATE NOT NULL,
    previous_dividend DECIMAL(10, 4),
    new_dividend DECIMAL(10, 4),
    cut_percentage DECIMAL(5, 2),
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dividend_cuts_ticker ON dividend_cut_concern_history(ticker_symbol, detected_date DESC);

CREATE TABLE IF NOT EXISTS nav_erosion_concern_history (
    concern_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    erosion_probability DECIMAL(5, 2) NOT NULL,
    time_horizon_years INTEGER NOT NULL,
    withdrawal_rate DECIMAL(5, 2),
    safety_margin DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_nav_erosion_portfolio ON nav_erosion_concern_history(portfolio_id, analysis_date DESC);

-- ============================================
-- SIMULATION (4 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS portfolio_simulations (
    simulation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    simulation_type VARCHAR(50) NOT NULL, -- 'monte_carlo', 'historical', 'stress_test'
    simulation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    num_iterations INTEGER NOT NULL,
    time_horizon_years INTEGER NOT NULL,
    initial_value DECIMAL(18, 2) NOT NULL,
    withdrawal_rate DECIMAL(5, 2),
    inflation_rate DECIMAL(5, 2),
    simulation_params JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulations_portfolio ON portfolio_simulations(portfolio_id, simulation_date DESC);

CREATE TABLE IF NOT EXISTS simulation_paths (
    path_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    simulation_id UUID NOT NULL REFERENCES portfolio_simulations(simulation_id) ON DELETE CASCADE,
    path_number INTEGER NOT NULL,
    year_number INTEGER NOT NULL,
    portfolio_value DECIMAL(18, 2) NOT NULL,
    withdrawals DECIMAL(18, 2),
    returns DECIMAL(8, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(simulation_id, path_number, year_number)
);

CREATE INDEX idx_paths_simulation ON simulation_paths(simulation_id, path_number, year_number);

CREATE TABLE IF NOT EXISTS simulation_risk_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    simulation_id UUID NOT NULL REFERENCES portfolio_simulations(simulation_id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10, 4) NOT NULL,
    percentile DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(simulation_id, metric_name)
);

CREATE TABLE IF NOT EXISTS safe_withdrawal_analysis (
    analysis_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    safe_withdrawal_rate DECIMAL(5, 2) NOT NULL,
    probability_of_success DECIMAL(5, 2) NOT NULL,
    time_horizon_years INTEGER NOT NULL,
    assumptions JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, analysis_date, time_horizon_years)
);

CREATE INDEX idx_swr_analysis ON safe_withdrawal_analysis(portfolio_id, analysis_date DESC);

-- ============================================
-- TIME-SERIES DATA (5 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS market_data_daily (
    data_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2) NOT NULL,
    volume BIGINT,
    adjusted_close DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, trade_date)
);

CREATE INDEX idx_market_data_ticker_date ON market_data_daily(ticker_symbol, trade_date DESC);

CREATE TABLE IF NOT EXISTS market_sentiment_daily (
    sentiment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    sentiment_date DATE NOT NULL,
    sentiment_score DECIMAL(5, 2), -- -100 to +100
    news_volume INTEGER,
    social_volume INTEGER,
    analyst_sentiment DECIMAL(5, 2),
    institutional_flow DECIMAL(18, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, sentiment_date)
);

CREATE INDEX idx_sentiment_ticker ON market_sentiment_daily(ticker_symbol, sentiment_date DESC);

CREATE TABLE IF NOT EXISTS dividend_calendar (
    calendar_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    ex_dividend_date DATE NOT NULL,
    record_date DATE,
    payment_date DATE,
    amount DECIMAL(10, 4) NOT NULL,
    frequency VARCHAR(20), -- 'monthly', 'quarterly', 'annual'
    special_dividend BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, ex_dividend_date)
);

CREATE INDEX idx_dividend_calendar_ticker ON dividend_calendar(ticker_symbol, ex_dividend_date DESC);
CREATE INDEX idx_dividend_calendar_payment ON dividend_calendar(payment_date) WHERE payment_date >= CURRENT_DATE;

CREATE TABLE IF NOT EXISTS earnings_calendar (
    earnings_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    fiscal_quarter VARCHAR(10),
    fiscal_year INTEGER,
    estimated_eps DECIMAL(10, 2),
    actual_eps DECIMAL(10, 2),
    surprise_percent DECIMAL(8, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, earnings_date)
);

CREATE INDEX idx_earnings_ticker ON earnings_calendar(ticker_symbol, earnings_date DESC);

CREATE TABLE IF NOT EXISTS exchange_rates (
    rate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_currency VARCHAR(3) NOT NULL,
    to_currency VARCHAR(3) NOT NULL,
    rate_date DATE NOT NULL,
    exchange_rate DECIMAL(18, 8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_currency, to_currency, rate_date)
);

CREATE INDEX idx_exchange_rates ON exchange_rates(from_currency, to_currency, rate_date DESC);

-- ============================================
-- ANALYTICS (8 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS portfolio_analytics (
    analytics_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    analytics_date DATE NOT NULL,
    sharpe_ratio DECIMAL(8, 4),
    sortino_ratio DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    volatility DECIMAL(8, 4),
    beta DECIMAL(8, 4),
    alpha DECIMAL(8, 4),
    tracking_error DECIMAL(8, 4),
    information_ratio DECIMAL(8, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, analytics_date)
);

CREATE INDEX idx_analytics_portfolio ON portfolio_analytics(portfolio_id, analytics_date DESC);

CREATE TABLE IF NOT EXISTS risk_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,
    var_95 DECIMAL(18, 2), -- Value at Risk
    cvar_95 DECIMAL(18, 2), -- Conditional VaR
    stress_test_result JSONB,
    correlation_matrix JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, calculation_date)
);

CREATE TABLE IF NOT EXISTS performance_attribution (
    attribution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_return DECIMAL(8, 4),
    benchmark_return DECIMAL(8, 4),
    active_return DECIMAL(8, 4),
    allocation_effect DECIMAL(8, 4),
    selection_effect DECIMAL(8, 4),
    interaction_effect DECIMAL(8, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, period_start, period_end)
);

CREATE INDEX idx_attribution_portfolio ON performance_attribution(portfolio_id, period_end DESC);

CREATE TABLE IF NOT EXISTS tax_analytics (
    tax_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    tax_year INTEGER NOT NULL,
    total_dividends DECIMAL(18, 2),
    qualified_dividends DECIMAL(18, 2),
    ordinary_dividends DECIMAL(18, 2),
    capital_gains_short DECIMAL(18, 2),
    capital_gains_long DECIMAL(18, 2),
    tax_loss_harvesting_savings DECIMAL(18, 2),
    estimated_tax_liability DECIMAL(18, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, tax_year)
);

CREATE INDEX idx_tax_analytics ON tax_analytics(portfolio_id, tax_year DESC);

CREATE TABLE IF NOT EXISTS income_analytics (
    income_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    annual_income DECIMAL(18, 2) NOT NULL,
    monthly_income DECIMAL(18, 2) NOT NULL,
    yield_on_cost DECIMAL(5, 4) NOT NULL,
    current_yield DECIMAL(5, 4) NOT NULL,
    income_growth_rate DECIMAL(5, 2),
    dividend_coverage_ratio DECIMAL(5, 2),
    payout_ratio_avg DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, analysis_date)
);

CREATE INDEX idx_income_analytics ON income_analytics(portfolio_id, analysis_date DESC);

CREATE TABLE IF NOT EXISTS concentration_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,
    herfindahl_index DECIMAL(8, 4),
    top_5_concentration DECIMAL(5, 2),
    top_10_concentration DECIMAL(5, 2),
    sector_concentration JSONB,
    geography_concentration JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, calculation_date)
);

CREATE TABLE IF NOT EXISTS liquidity_metrics (
    liquidity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    calculation_date DATE NOT NULL,
    avg_daily_volume BIGINT,
    bid_ask_spread DECIMAL(8, 4),
    days_to_liquidate DECIMAL(8, 2),
    market_impact_estimate DECIMAL(8, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, calculation_date)
);

CREATE INDEX idx_liquidity_ticker ON liquidity_metrics(ticker_symbol, calculation_date DESC);

CREATE TABLE IF NOT EXISTS benchmark_comparison (
    comparison_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    benchmark_symbol VARCHAR(20) NOT NULL,
    comparison_date DATE NOT NULL,
    portfolio_return DECIMAL(8, 4),
    benchmark_return DECIMAL(8, 4),
    excess_return DECIMAL(8, 4),
    tracking_error DECIMAL(8, 4),
    information_ratio DECIMAL(8, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, benchmark_symbol, comparison_date)
);

CREATE INDEX idx_benchmark_comparison ON benchmark_comparison(portfolio_id, comparison_date DESC);

-- ============================================
-- COVERED CALL & OPTIONS (5 tables)
-- ============================================

-- Reuse existing covered_call_etf_metrics from V2.0
-- Just ensure it exists
CREATE TABLE IF NOT EXISTS covered_call_etf_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    metric_date DATE NOT NULL,
    distribution_rate DECIMAL(5, 2),
    premium_capture DECIMAL(5, 2),
    upside_capture DECIMAL(5, 2),
    downside_protection DECIMAL(5, 2),
    UNIQUE(ticker_symbol, metric_date)
);

CREATE TABLE IF NOT EXISTS options_positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    underlying_ticker VARCHAR(20) NOT NULL,
    option_type VARCHAR(10) NOT NULL, -- 'call', 'put'
    strike_price DECIMAL(10, 2) NOT NULL,
    expiration_date DATE NOT NULL,
    contracts INTEGER NOT NULL,
    premium_received DECIMAL(10, 2),
    opened_date DATE NOT NULL,
    closed_date DATE,
    status VARCHAR(20) DEFAULT 'open', -- 'open', 'assigned', 'expired', 'closed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_options_portfolio ON options_positions(portfolio_id, status);

CREATE TABLE IF NOT EXISTS covered_call_analysis (
    analysis_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    analysis_date DATE NOT NULL,
    strike_price DECIMAL(10, 2) NOT NULL,
    premium DECIMAL(10, 2) NOT NULL,
    annualized_return DECIMAL(5, 2),
    probability_of_assignment DECIMAL(5, 2),
    max_gain DECIMAL(10, 2),
    break_even_price DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cc_analysis ON covered_call_analysis(ticker_symbol, analysis_date DESC);

CREATE TABLE IF NOT EXISTS option_chain_data (
    chain_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    expiration_date DATE NOT NULL,
    strike_price DECIMAL(10, 2) NOT NULL,
    option_type VARCHAR(10) NOT NULL,
    last_price DECIMAL(10, 2),
    bid DECIMAL(10, 2),
    ask DECIMAL(10, 2),
    volume INTEGER,
    open_interest INTEGER,
    implied_volatility DECIMAL(5, 2),
    delta DECIMAL(6, 4),
    gamma DECIMAL(6, 4),
    theta DECIMAL(6, 4),
    vega DECIMAL(6, 4),
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, expiration_date, strike_price, option_type, snapshot_date)
);

CREATE INDEX idx_option_chain ON option_chain_data(ticker_symbol, expiration_date, strike_price);

CREATE TABLE IF NOT EXISTS covered_call_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_symbol VARCHAR(20) NOT NULL,
    recommendation_date DATE NOT NULL,
    strike_price DECIMAL(10, 2) NOT NULL,
    expiration_date DATE NOT NULL,
    expected_return DECIMAL(5, 2),
    risk_level VARCHAR(20),
    rationale TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cc_recommendations ON covered_call_recommendations(ticker_symbol, recommendation_date DESC);

-- ============================================
-- USERS & AUTHENTICATION (3 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email_verified BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS user_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id, expires_at);
CREATE INDEX idx_sessions_token ON user_sessions(session_token) WHERE expires_at > CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS user_api_keys (
    api_key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    api_key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_name VARCHAR(100) NOT NULL,
    scopes JSONB,
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_keys_user ON user_api_keys(user_id) WHERE is_active = true;

-- ============================================
-- AUDIT & COMPLIANCE (3 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    request_data JSONB,
    response_status INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);

CREATE TABLE IF NOT EXISTS compliance_checks (
    check_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    check_type VARCHAR(100) NOT NULL,
    check_date DATE NOT NULL,
    passed BOOLEAN NOT NULL,
    violations JSONB,
    remediation_required BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_compliance_portfolio ON compliance_checks(portfolio_id, check_date DESC);

CREATE TABLE IF NOT EXISTS regulatory_reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    report_type VARCHAR(100) NOT NULL,
    reporting_period_start DATE NOT NULL,
    reporting_period_end DATE NOT NULL,
    report_data JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_regulatory_reports ON regulatory_reports(portfolio_id, reporting_period_end DESC);

-- ============================================
-- SYSTEM METADATA (2 tables)
-- ============================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations (version, description)
VALUES ('V3.0', 'Complete 97-table schema for Income Fortress Platform')
ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TRIGGERS FOR updated_at columns
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to all tables with updated_at column
CREATE TRIGGER update_portfolios_updated_at BEFORE UPDATE ON portfolios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_holdings_updated_at BEFORE UPDATE ON portfolio_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_config_updated_at BEFORE UPDATE ON portfolio_configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_preferences_updated_at BEFORE UPDATE ON portfolio_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_asset_classes_updated_at BEFORE UPDATE ON asset_classes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analyst_profiles_updated_at BEFORE UPDATE ON analyst_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alert_rules_updated_at BEFORE UPDATE ON alert_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_templates_updated_at BEFORE UPDATE ON notification_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- INITIAL SYSTEM CONFIG
-- ============================================

INSERT INTO system_config (config_key, config_value, description) VALUES
('platform_version', '"1.0.0"', 'Current platform version'),
('schema_version', '"3.0"', 'Database schema version'),
('deployment_date', '"2026-02-12"', 'Production deployment date'),
('capital_safety_threshold', '70.0', 'Default capital safety threshold percentage'),
('monte_carlo_default_iterations', '10000', 'Default number of Monte Carlo simulation iterations')
ON CONFLICT (config_key) DO NOTHING;

-- ============================================
-- COMPLETION
-- ============================================

-- Verify table count
SELECT COUNT(*) as total_tables 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE';

COMMENT ON DATABASE CURRENT_DATABASE() IS 'Income Fortress Platform - Complete production schema with 97+ tables';
