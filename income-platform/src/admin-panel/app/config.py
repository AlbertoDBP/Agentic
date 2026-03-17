import os


class Settings:
    port: int = int(os.environ.get("SERVICE_PORT", "8100"))
    jwt_secret: str = os.environ.get("JWT_SECRET", "")
    database_url: str = os.environ.get("DATABASE_URL", "")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")

    # ── Service URLs (container names) ──
    agent01_url: str = os.environ.get("AGENT01_URL", "http://market-data-service:8001")
    agent02_url: str = os.environ.get("AGENT02_URL", "http://agent-02-newsletter-ingestion:8002")
    agent03_url: str = os.environ.get("AGENT03_URL", "http://agent-03-income-scoring:8003")
    agent04_url: str = os.environ.get("AGENT04_URL", "http://agent-04-asset-classification:8004")
    agent05_url: str = os.environ.get("AGENT05_URL", "http://tax-optimization-service:8005")
    agent06_url: str = os.environ.get("AGENT06_URL", "http://agent-06-scenario-simulation:8006")
    agent07_url: str = os.environ.get("AGENT07_URL", "http://agent-07-opportunity-scanner:8007")
    agent08_url: str = os.environ.get("AGENT08_URL", "http://agent-08-rebalancing:8008")
    agent09_url: str = os.environ.get("AGENT09_URL", "http://agent-09-income-projection:8009")
    agent10_url: str = os.environ.get("AGENT10_URL", "http://agent-10-nav-monitor:8010")
    agent11_url: str = os.environ.get("AGENT11_URL", "http://agent-11-smart-alert:8011")
    agent12_url: str = os.environ.get("AGENT12_URL", "http://agent-12-proposal:8012")
    broker_url: str = os.environ.get("BROKER_URL", "http://broker-service:8013")
    scheduler_url: str = os.environ.get("SCHEDULER_URL", "http://scheduler:8099")

    # ── Timeouts ──
    http_timeout: int = int(os.environ.get("HTTP_TIMEOUT", "10"))

    # ── Service Registry ──
    services: list[dict] = [
        {"num": "01", "port": 8001, "container": "market-data-service", "label": "Market Data"},
        {"num": "02", "port": 8002, "container": "agent-02-newsletter-ingestion", "label": "Newsletter"},
        {"num": "03", "port": 8003, "container": "agent-03-income-scoring", "label": "Income Scoring"},
        {"num": "04", "port": 8004, "container": "agent-04-asset-classification", "label": "Classification"},
        {"num": "05", "port": 8005, "container": "tax-optimization-service", "label": "Tax Optimization"},
        {"num": "06", "port": 8006, "container": "agent-06-scenario-simulation", "label": "Simulation"},
        {"num": "07", "port": 8007, "container": "agent-07-opportunity-scanner", "label": "Scanner"},
        {"num": "08", "port": 8008, "container": "agent-08-rebalancing", "label": "Rebalancing"},
        {"num": "09", "port": 8009, "container": "agent-09-income-projection", "label": "Projection"},
        {"num": "10", "port": 8010, "container": "agent-10-nav-monitor", "label": "NAV Monitor"},
        {"num": "11", "port": 8011, "container": "agent-11-smart-alert", "label": "Smart Alert"},
        {"num": "12", "port": 8012, "container": "agent-12-proposal", "label": "Proposal"},
        {"num": "13", "port": 8013, "container": "broker-service", "label": "Broker"},
        {"num": "99", "port": 8099, "container": "scheduler", "label": "Scheduler"},
    ]


settings = Settings()


def get_service_url(num: str) -> str:
    """Return the base URL for a service by its number."""
    url_map = {
        "01": settings.agent01_url,
        "02": settings.agent02_url,
        "03": settings.agent03_url,
        "04": settings.agent04_url,
        "05": settings.agent05_url,
        "06": settings.agent06_url,
        "07": settings.agent07_url,
        "08": settings.agent08_url,
        "09": settings.agent09_url,
        "10": settings.agent10_url,
        "11": settings.agent11_url,
        "12": settings.agent12_url,
        "99": settings.scheduler_url,
    }
    return url_map.get(num, "")
