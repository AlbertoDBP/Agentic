"""Broker Service — configuration."""
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "broker-service"
    version: str = "1.0.0"
    port: int = 8013

    database_url: str = ""
    jwt_secret: str = ""
    log_level: str = "INFO"

    # ── Alpaca ──
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ── Future brokers can be added here ──
    # schwab_client_id: str = ""
    # schwab_client_secret: str = ""

    # ── Downstream services ──
    scoring_service_url: str = "http://agent-03-income-scoring:8003"
    classification_url: str = "http://agent-04-asset-classification:8004"
    scanner_url: str = "http://agent-07-opportunity-scanner:8007"
    service_token: str = ""          # read from SERVICE_TOKEN env var

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
