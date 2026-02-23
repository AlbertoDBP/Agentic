"""Market Data Service - Configuration"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Service
    service_name: str = "market-data-service"
    service_port: int = 8001
    log_level: str = "INFO"
    
    # Database
    database_url: str
    
    # Cache
    redis_url: str
    cache_ttl_current_price: int = 300
    
    # API Keys
    market_data_api_key: str          # Alpha Vantage (legacy / reference)
    polygon_api_key: str = ""         # Polygon.io Stocks Starter
    fmp_api_key: str = ""             # Financial Modeling Prep
    
    # Sync
    sync_interval: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()
