"""Agent 08 — Rebalancing Service configuration."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=("../../.env", ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "rebalancing-service"
    service_version: str = "1.0.0"
    port: int = 8008
    log_level: str = "INFO"

    database_url: str
    jwt_secret: str

    income_scoring_url: str = "http://income-scoring-service:8003"
    income_scoring_timeout: float = 30.0
    tax_optimization_url: str = "http://tax-optimization-service:8005"
    tax_optimization_timeout: float = 30.0

    rebalance_concurrency: int = 10
    quality_gate_threshold: float = 70.0


settings = Settings()
