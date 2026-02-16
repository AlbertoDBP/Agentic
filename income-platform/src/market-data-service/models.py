"""Market Data Service - Pydantic Models"""
from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import List, Optional

class PriceData(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    price: float = Field(..., gt=0)
    change: float
    change_percent: float
    volume: int = Field(..., ge=0)
    timestamp: datetime
    source: str
    cached: bool = False
    
    @validator('ticker')
    def uppercase_ticker(cls, v):
        return v.upper().strip()

class HistoricalPrice(BaseModel):
    date: date
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    adjusted_close: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    service: str = "market-data-service"
    database: str
    cache: str
