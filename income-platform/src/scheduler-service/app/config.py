import os


class Settings:
    port: int = int(os.environ.get("SERVICE_PORT", "8099"))
    jwt_secret: str = os.environ.get("JWT_SECRET", "")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")

    # ── Service URLs (container names) ──
    agent01_url: str = os.environ.get("AGENT01_URL", "http://market-data-service:8001")
    agent02_url: str = os.environ.get("AGENT02_URL", "http://agent-02-newsletter-ingestion:8002")
    agent03_url: str = os.environ.get("AGENT03_URL", "http://agent-03-income-scoring:8003")
    agent04_url: str = os.environ.get("AGENT04_URL", "http://agent-04-asset-classification:8004")
    agent07_url: str = os.environ.get("AGENT07_URL", "http://agent-07-opportunity-scanner:8007")
    agent08_url: str = os.environ.get("AGENT08_URL", "http://agent-08-rebalancing:8008")
    agent09_url: str = os.environ.get("AGENT09_URL", "http://agent-09-income-projection:8009")
    agent10_url: str = os.environ.get("AGENT10_URL", "http://agent-10-nav-monitor:8010")
    agent11_url: str = os.environ.get("AGENT11_URL", "http://agent-11-smart-alert:8011")
    agent14_url: str = os.environ.get("AGENT14_URL", "http://agent-14-data-quality:8014")

    # ── Timeouts ──
    http_timeout: int = int(os.environ.get("HTTP_TIMEOUT", "120"))


settings = Settings()
