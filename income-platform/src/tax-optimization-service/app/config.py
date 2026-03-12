"""
Agent 05 — Tax Optimization Service
Configuration via environment variables
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    # Service identity
    service_name: str = "tax-optimization-service"
    agent_id: int = 5
    version: str = "1.0.0"
    port: int = 8005
    debug: bool = False

    # Database — read-only access to platform DB
    database_url: str = "postgresql://income_platform_user:password@db:5432/income_platform"
    db_pool_size: int = 3
    db_max_overflow: int = 5
    db_echo: bool = False

    # Agent 04 base URL (for asset class fallback)
    asset_classification_url: str = "http://asset-classification-service:8004"
    agent04_timeout_seconds: float = 3.0

    # Tax data — no external API keys required (rule-based engine)

    # Auth
    jwt_secret: str

    # Logging
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
