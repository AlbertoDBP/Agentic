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
    market_data_api_key: str
    
    # Sync
    sync_interval: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
