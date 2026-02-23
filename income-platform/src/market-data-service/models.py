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


# ---------------------------------------------------------------------------
# Stock history endpoints — /api/market-data/stocks/{symbol}/history/...
# ---------------------------------------------------------------------------

class StockHistoryResponse(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    count: int
    prices: List[HistoricalPrice]
    source: str


class StockHistoryStatsResponse(BaseModel):
    symbol: str
    period_days: int
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_price: Optional[float] = None
    volatility: Optional[float] = None
    price_change_pct: Optional[float] = None


class RefreshRequest(BaseModel):
    full_history: bool = False


class StockHistoryRefreshResponse(BaseModel):
    symbol: str
    records_saved: int
    source: str
    message: str
