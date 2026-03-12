"""
Agent 06 — Scenario Simulation Service
Configuration: Loads environment variables and provides settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "scenario-simulation-service"
    service_version: str = "1.0.0"
    port: int = 8006
    database_url: str
    jwt_secret: str
    log_level: str = "INFO"

    class Config:
        env_file = ("../../.env", ".env")
        case_sensitive = False
        extra = "ignore"


settings = Settings()
