"""
Agent 02 — Newsletter Ingestion Service (The Dividend Detective)
Configuration: Loads environment variables and provides settings

Matches income-platform service configuration pattern from Agent 01.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All sensitive values (API keys, DB URLs) must be set via .env or
    environment — never hardcoded.
    """

    # ── Service Identity ──────────────────────────────────────────────────────
    service_name: str = "agent-02-newsletter-ingestion"
    service_port: int = 8002
    log_level: str = "INFO"
    environment: str = "production"  # production | staging | development

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str                          # postgresql+psycopg2://...
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_schema: str = "platform_shared"         # all tables live here

    # ── Cache (Redis / Valkey) ─────────────────────────────────────────────────
    redis_url: str
    cache_ttl_analyst_signal: int = 3600       # 1 hour — signal freshness
    cache_ttl_consensus: int = 1800            # 30 min — consensus scores
    cache_ttl_articles: int = 86400            # 24 hours — raw article cache

    # ── APIDojo / Seeking Alpha ────────────────────────────────────────────────
    apidojo_sa_api_key: str                    # RapidAPI key for SA endpoints
    apidojo_sa_host: str = "seeking-alpha.p.rapidapi.com"
    sa_fetch_limit_per_analyst: int = 10       # max articles per analyst per run
    sa_request_timeout: int = 30               # seconds

    # ── Anthropic (Claude) ────────────────────────────────────────────────────
    anthropic_api_key: str
    extraction_model: str = "claude-haiku-20250310"   # bulk extraction (cost)
    philosophy_model: str = "claude-sonnet-4-20250514" # philosophy synthesis (quality)
    extraction_max_tokens: int = 1500
    philosophy_max_tokens: int = 800

    # ── OpenAI (Embeddings) ───────────────────────────────────────────────────
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # ── FMP (Financial Modeling Prep — Market Truth) ──────────────────────────
    fmp_api_key: str
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_request_timeout: int = 30

    # ── Harvester Flow Config (defaults, overridden by user_preferences) ──────
    default_aging_days: int = 365              # recommendation expiry window
    default_aging_halflife_days: int = 180     # S-curve inflection point
    default_min_decay_weight: float = 0.1      # hard floor for consensus
    default_min_accuracy_threshold: float = 0.5
    default_kmeans_min_articles: int = 20      # articles before K-Means promotion
    default_kmeans_k: int = 5                  # number of philosophy clusters
    harvester_cron: str = "0 7 * * 2,5"        # Tue + Fri 7AM ET
    intelligence_cron: str = "0 6 * * 1"       # Monday 6AM ET

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    sa_calls_per_minute: int = 10
    fmp_calls_per_minute: int = 30
    anthropic_calls_per_minute: int = 50
    openai_calls_per_minute: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance — import this throughout the service
settings = Settings()
