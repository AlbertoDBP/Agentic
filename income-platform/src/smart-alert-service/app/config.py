"""Agent 11 — Smart Alert Service configuration."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=("../../.env", ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "smart-alert-service"
    service_version: str = "1.0.0"
    port: int = 8011
    log_level: str = "INFO"

    database_url: str
    jwt_secret: str

    # Alert confirmation gate: number of consecutive detections before CONFIRMED
    confirmation_days: int = 2

    # Score deterioration thresholds
    score_delta_warning: float = 15.0
    score_delta_critical: float = 25.0


settings = Settings()
