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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
