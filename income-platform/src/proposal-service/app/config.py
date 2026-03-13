"""Agent 12 — Proposal Service configuration."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=("../../.env", ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "proposal-service"
    service_version: str = "1.0.0"
    port: int = 8012
    log_level: str = "INFO"

    database_url: str
    jwt_secret: str

    # Downstream agent URLs
    agent02_url: str = "http://agent-02-newsletter-ingestion:8002"
    agent02_timeout: float = 10.0

    agent03_url: str = "http://income-scoring-service:8003"
    agent03_timeout: float = 10.0

    agent04_url: str = "http://asset-classification-service:8004"
    agent04_timeout: float = 10.0

    agent05_url: str = "http://tax-optimization-service:8005"
    agent05_timeout: float = 10.0

    # Business rules
    proposal_expiry_days: int = 14
    min_override_rationale_len: int = 20


settings = Settings()
