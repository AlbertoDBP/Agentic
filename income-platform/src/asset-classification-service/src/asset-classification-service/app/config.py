"""Agent 04 — Asset Classification Service Configuration"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Service
    service_name: str = "agent-04-asset-classification"
    service_port: int = 8004
    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+psycopg2://localhost/income_platform"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 86400       # 24 hours

    # Upstream services
    market_data_service_url: str = "http://localhost:8001"
    market_data_timeout: int = 10

    # Classification
    enrichment_confidence_threshold: float = 0.70   # below this → call Agent 01
    classification_cache_ttl_hours: int = 24

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
