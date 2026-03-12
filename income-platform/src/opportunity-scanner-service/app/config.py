"""
Agent 07 — Opportunity Scanner Service
Configuration via environment variables.
"""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=("../../.env", ".env"), case_sensitive=False, extra="ignore")

    service_name: str = "opportunity-scanner-service"
    service_version: str = "1.0.0"
    port: int = 8007
    log_level: str = "INFO"

    # Database
    database_url: str

    # Auth
    jwt_secret: str

    # Upstream service URLs
    income_scoring_url: str = "http://income-scoring-service:8003"
    income_scoring_timeout: float = 30.0

    # Scanner config
    scan_concurrency: int = 10       # max concurrent Agent 03 calls
    quality_gate_threshold: float = 70.0   # VETO gate score floor
    max_tickers_per_scan: int = 200


settings = Settings()
