"""Agent 04 — Asset Classification Service Configuration"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Service identity — defaults baked in, no .env needed for these
    service_name: str = "agent-04-asset-classification"
    service_port: int = 8004
    environment: str = "development"
    log_level: str = "INFO"

    # Database — from root .env
    database_url: str = "postgresql+psycopg2://localhost/income_platform"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis — from root .env
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 86400       # 24 hours

    # Upstream services — from root .env
    market_data_service_url: str = "http://localhost:8001"
    market_data_timeout: int = 10

    # Classification
    enrichment_confidence_threshold: float = 0.70
    classification_cache_ttl_hours: int = 24

    class Config:
        # Root .env first (shared credentials), local .env second (overrides)
        env_file = ("../../.env", ".env")
        extra = "ignore"


settings = Settings()
