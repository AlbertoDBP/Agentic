# src/agent-14-data-quality/app/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = "agent-14-data-quality"
    service_port: int = 8014
    log_level: str = "INFO"
    environment: str = "production"

    # Database
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_schema: str = "platform_shared"

    # External APIs
    fmp_api_key: str
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_request_timeout: int = 30
    massive_api_key: str = Field(default="", alias="massive_key")  # env var: MASSIVE_KEY
    massive_base_url: str = "https://api.polygon.io"  # MASSIVE = rebranded Polygon.io
    massive_request_timeout: int = 30

    # Healing config
    max_heal_attempts: int = 3
    peer_divergence_sigma: float = 3.0  # PEER_DIVERGENCE threshold

    # Auth
    jwt_secret: str


settings = Settings()
