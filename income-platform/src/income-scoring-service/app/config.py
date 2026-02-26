"""
Agent 03 — Income Scoring Service
Configuration: Loads environment variables and provides settings.

Matches income-platform service configuration pattern from Agent 01 & 02.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All sensitive values must be set via .env or environment — never hardcoded.
    """

    # ── Service Identity ──────────────────────────────────────────────────────
    service_name: str = "agent-03-income-scoring"
    service_port: int = 8003
    log_level: str = "INFO"
    environment: str = "production"  # production | staging | development

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str                          # postgresql+psycopg2://...
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_schema: str = "platform_shared"         # shared schema across agents

    # ── Cache (Redis / Valkey) ────────────────────────────────────────────────
    redis_url: str
    cache_ttl_score: int = 3600                # 1 hour — score freshness
    cache_ttl_quality_gate: int = 86400        # 24 hours — gate results stable
    cache_ttl_batch: int = 1800                # 30 min — batch score results

    # ── Market Data (Agent 01 dependency) ────────────────────────────────────
    market_data_service_url: str = "http://localhost:8001"
    market_data_timeout: int = 30

    # ── Newsletter (Agent 02 dependency — optional signals) ──────────────────
    newsletter_service_url: str = "http://localhost:8002"
    newsletter_service_enabled: bool = True
    newsletter_timeout: int = 10

    # ── Financial Modeling Prep (income-focused fundamentals) ────────────────
    fmp_api_key: str
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_request_timeout: int = 30
    fmp_calls_per_minute: int = 30

    # ── Scoring Engine Config ────────────────────────────────────────────────
    # Quality gate thresholds
    min_credit_rating: str = "BBB-"            # investment grade floor
    min_consecutive_fcf_years: int = 3         # positive FCF required
    min_dividend_history_years: int = 10       # dividend track record
    min_etf_aum_millions: float = 500.0        # ETF AUM floor ($M)
    min_etf_track_record_years: int = 3        # ETF history requirement
    min_reit_coverage_ratio: float = 1.0       # REIT interest coverage floor

    # Scoring weights (must sum to 100)
    weight_valuation_yield: int = 40
    weight_financial_durability: int = 40
    weight_technical_entry: int = 20

    # Score tier thresholds
    score_aggressive_buy: int = 85             # 85-100 → Aggressive Buy
    score_accumulate: int = 70                 # 70-84  → Accumulate (DCA)
    # below score_accumulate               →   Watch only

    # Scoring engine simulation / history config
    nav_erosion_simulations: int = 10000       # Monte Carlo paths for NAV erosion
    score_history_days: int = 90               # days of price history for technical scoring

    # NAV erosion penalty config (covered call ETFs)
    nav_erosion_penalty_max: int = 30          # max points deducted
    nav_erosion_prob_threshold_low: float = 0.30
    nav_erosion_prob_threshold_med: float = 0.50
    nav_erosion_prob_threshold_high: float = 0.70

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    max_batch_size: int = 50                   # max tickers per batch request
    scoring_timeout_seconds: int = 60          # per-ticker timeout

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance — import this throughout the service
settings = Settings()
