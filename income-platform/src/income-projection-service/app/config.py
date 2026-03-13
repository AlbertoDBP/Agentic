"""Agent 09 — Income Projection Service configuration."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=("../../.env", ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "income-projection-service"
    service_version: str = "1.0.0"
    port: int = 8009
    log_level: str = "INFO"

    database_url: str
    jwt_secret: str

    projection_max_horizon_months: int = 60


settings = Settings()
