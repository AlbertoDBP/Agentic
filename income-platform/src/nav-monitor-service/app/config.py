"""Agent 10 — NAV Erosion Monitor configuration."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=("../../.env", ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "nav-monitor-service"
    service_version: str = "1.0.0"
    port: int = 8010
    log_level: str = "INFO"

    database_url: str
    jwt_secret: str

    # NAV_EROSION thresholds (positive values; applied as negatives in detector)
    nav_erosion_30d_threshold: float = 0.05   # 5% — -5% triggers WARNING
    nav_erosion_90d_threshold: float = 0.10   # 10% — -10% triggers WARNING

    # PREMIUM_DISCOUNT_DRIFT thresholds
    premium_discount_warning_pct: float = 0.08   # below -8% triggers alert
    premium_discount_cap_pct: float = 0.15        # above +15% triggers alert
    premium_discount_critical_abs: float = 0.15   # abs > 15% → CRITICAL

    # SCORE_DIVERGENCE thresholds
    score_divergence_penalty_threshold: float = 10.0
    score_divergence_score_threshold: float = 55.0
    score_divergence_critical_score: float = 40.0

    # Scan window
    snapshot_lookback_days: int = 90


settings = Settings()
