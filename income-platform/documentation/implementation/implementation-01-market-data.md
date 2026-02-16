# Market Data Service - Implementation Specification

**Version:** 1.0  
**Status:** Ready to Code  
**Estimated Effort:** 12-16 hours  
**Priority:** P0 (Foundational)

## Technical Design

### Architecture Overview

```
┌─────────────┐
│   FastAPI   │  ← REST API Layer
│  Application│
└──────┬──────┘
       │
┌──────┴──────────────────────────┐
│                                 │
│  ┌─────────┐     ┌───────────┐ │
│  │Fetchers │────→│Normalizer │ │  ← Business Logic
│  └─────────┘     └───────────┘ │
│       │                │        │
└───────┼────────────────┼────────┘
        │                │
┌───────┴────┐    ┌──────┴──────┐
│  External  │    │   Cache     │  ← Data Layer
│    APIs    │    │  Manager    │
└────────────┘    └──────┬──────┘
                         │
                  ┌──────┴──────┐
                  │  PostgreSQL │
                  └─────────────┘
```

### Module Structure

```
src/market-data-service/
├── __init__.py
├── main.py                  # FastAPI application entry point
├── config.py                # Configuration and environment variables
├── models.py                # Pydantic models for validation
├── database.py              # SQLAlchemy models and connection
├── cache.py                 # Redis cache manager
├── fetchers/
│   ├── __init__.py
│   ├── base.py              # Abstract base fetcher
│   ├── alpha_vantage.py     # Alpha Vantage client
│   ├── polygon.py           # Polygon.io client (future)
│   └── yahoo_finance.py     # Yahoo Finance client (future)
├── services/
│   ├── __init__.py
│   ├── price_service.py     # Price data business logic
│   ├── dividend_service.py  # Dividend data business logic
│   └── sync_service.py      # Background sync orchestration
└── utils/
    ├── __init__.py
    ├── normalizer.py        # Data normalization
    └── rate_limiter.py      # Rate limiting logic
```

## API/Interface Details

### FastAPI Application (main.py)

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(
    title="Market Data Service",
    version="1.0.0",
    description="Real-time and historical market data API"
)

@app.on_event("startup")
async def startup_event():
    """Initialize database, cache, and start background sync"""
    await init_database()
    await init_cache()
    await start_sync_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources"""
    await close_database()
    await close_cache()

@app.get("/health")
async def health_check():
    """Health check with provider status"""
    return {
        "status": "healthy",
        "database": await check_database(),
        "cache": await check_cache(),
        "providers": await check_providers()
    }

@app.get("/api/v1/price/{ticker}")
async def get_current_price(ticker: str):
    """Get current price (cached if available)"""
    service = PriceService()
    return await service.get_current_price(ticker)

@app.get("/api/v1/price/{ticker}/history")
async def get_historical_prices(
    ticker: str,
    start_date: str,
    end_date: str
):
    """Get historical price data"""
    service = PriceService()
    return await service.get_historical_prices(ticker, start_date, end_date)

@app.get("/api/v1/dividends/{ticker}")
async def get_dividends(ticker: str):
    """Get dividend calendar"""
    service = DividendService()
    return await service.get_dividends(ticker)

@app.post("/api/v1/sync/trigger")
async def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks
):
    """Manually trigger sync for specific tickers"""
    background_tasks.add_task(sync_tickers, request.tickers)
    return {"status": "queued", "tickers": len(request.tickers)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Pydantic Models (models.py)

```python
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

class HistoricalPrice(BaseModel):
    date: date
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    adjusted_close: Optional[float] = None

class HistoricalPriceResponse(BaseModel):
    ticker: str
    data: List[HistoricalPrice]
    count: int

class Dividend(BaseModel):
    ex_dividend_date: date
    payment_date: Optional[date]
    amount: float = Field(..., gt=0)
    frequency: str
    dividend_type: Optional[str] = "qualified"

class DividendResponse(BaseModel):
    ticker: str
    dividends: List[Dividend]

class SyncRequest(BaseModel):
    tickers: List[str] = Field(..., min_items=1, max_items=100)

class ProviderStatus(BaseModel):
    name: str
    operational: bool
    last_success: Optional[datetime]
    error_count: int = 0
```

### Alpha Vantage Client (fetchers/alpha_vantage.py)

```python
import aiohttp
import logging
from typing import Dict, List, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)

class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_count = 0
        self.last_request_time = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_daily_prices(
        self, 
        ticker: str,
        outputsize: str = "compact"  # compact=100 days, full=20+ years
    ) -> List[Dict]:
        """Fetch daily price data"""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": self.api_key,
            "outputsize": outputsize,
            "datatype": "json"
        }
        
        try:
            data = await self._make_request(params)
            time_series = data.get("Time Series (Daily)", {})
            
            results = []
            for date_str, values in time_series.items():
                results.append({
                    "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "adjusted_close": float(values["5. adjusted close"]),
                    "volume": int(values["6. volume"])
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Failed to fetch prices for {ticker}: {e}")
            raise
    
    async def get_dividends(self, ticker: str) -> List[Dict]:
        """Fetch dividend data"""
        # Alpha Vantage doesn't have dedicated dividend endpoint
        # Extract from adjusted price data
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": self.api_key,
            "outputsize": "full"
        }
        
        try:
            data = await self._make_request(params)
            time_series = data.get("Time Series (Daily)", {})
            
            # Detect dividends by comparing close vs adjusted close
            dividends = []
            prev_close = None
            prev_adj = None
            
            for date_str, values in sorted(time_series.items()):
                close = float(values["4. close"])
                adj_close = float(values["5. adjusted close"])
                
                if prev_adj and prev_close:
                    # Dividend detected if adjustment ratio changed
                    ratio = adj_close / close
                    prev_ratio = prev_adj / prev_close
                    
                    if abs(ratio - prev_ratio) > 0.001:  # 0.1% threshold
                        div_amount = prev_close * (1 - ratio)
                        if div_amount > 0:
                            dividends.append({
                                "ex_dividend_date": datetime.strptime(
                                    date_str, "%Y-%m-%d"
                                ).date(),
                                "amount": round(div_amount, 2),
                                "frequency": "quarterly"  # Assume quarterly
                            })
                
                prev_close = close
                prev_adj = adj_close
            
            return dividends
        
        except Exception as e:
            logger.error(f"Failed to fetch dividends for {ticker}: {e}")
            return []
    
    async def _make_request(self, params: Dict) -> Dict:
        """Make HTTP request with rate limiting"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Rate limiting: max 5 requests/minute
        await self._rate_limit()
        
        async with self.session.get(self.BASE_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            
            # Check for API errors
            if "Error Message" in data:
                raise ValueError(f"API Error: {data['Error Message']}")
            
            if "Note" in data:  # Rate limit message
                raise RuntimeError(f"Rate limited: {data['Note']}")
            
            self.request_count += 1
            self.last_request_time = datetime.now()
            
            return data
    
    async def _rate_limit(self):
        """Implement rate limiting (5 calls/minute)"""
        import asyncio
        
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < 12:  # 60s / 5 calls = 12s between calls
                wait_time = 12 - elapsed
                logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
```

### Cache Manager (cache.py)

```python
import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection"""
        self.client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Connected to Redis cache")
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300  # 5 minutes default
    ):
        """Set cached value with TTL"""
        if not self.client:
            return
        
        try:
            await self.client.setex(
                key,
                timedelta(seconds=ttl),
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def delete(self, key: str):
        """Delete cached value"""
        if not self.client:
            return
        
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    async def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.client:
            return {"connected": False}
        
        try:
            info = await self.client.info("stats")
            return {
                "connected": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {"connected": False}
    
    def _calculate_hit_rate(self, info: dict) -> float:
        """Calculate cache hit rate percentage"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
```

### Price Service (services/price_service.py)

```python
import logging
from typing import List, Optional
from datetime import date, datetime
from .cache import CacheManager
from .database import SessionLocal
from .models import PriceData, HistoricalPrice
from .fetchers.alpha_vantage import AlphaVantageClient

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self, cache: CacheManager, api_key: str):
        self.cache = cache
        self.api_key = api_key
    
    async def get_current_price(self, ticker: str) -> PriceData:
        """Get current price with caching"""
        cache_key = f"price:current:{ticker}"
        
        # Try cache first
        cached = await self.cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for {ticker}")
            return PriceData(**cached, cached=True)
        
        # Fetch from API
        async with AlphaVantageClient(self.api_key) as client:
            prices = await client.get_daily_prices(ticker, outputsize="compact")
            
            if not prices:
                raise ValueError(f"No data for {ticker}")
            
            # Get most recent price
            latest = prices[0]
            
            # Calculate change
            if len(prices) > 1:
                prev_close = prices[1]["close"]
                change = latest["close"] - prev_close
                change_percent = (change / prev_close) * 100
            else:
                change = 0.0
                change_percent = 0.0
            
            price_data = PriceData(
                ticker=ticker,
                price=latest["close"],
                change=change,
                change_percent=change_percent,
                volume=latest["volume"],
                timestamp=datetime.now(),
                source="alpha_vantage",
                cached=False
            )
            
            # Cache for 5 minutes
            await self.cache.set(cache_key, price_data.dict(), ttl=300)
            
            # Store in database
            await self._store_price(ticker, latest)
            
            return price_data
    
    async def get_historical_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> List[HistoricalPrice]:
        """Get historical prices (database first, API fallback)"""
        # TODO: Query database first
        # For now, fetch from API
        
        async with AlphaVantageClient(self.api_key) as client:
            prices = await client.get_daily_prices(ticker, outputsize="full")
            
            # Filter by date range
            filtered = [
                HistoricalPrice(**p)
                for p in prices
                if start_date <= p["date"] <= end_date
            ]
            
            return filtered
    
    async def _store_price(self, ticker: str, price_data: dict):
        """Store price in database"""
        # TODO: Implement database storage
        pass
```

## Dependencies & Integrations

### External Libraries
```python
# requirements.txt additions for this service
aiohttp==3.9.1           # Async HTTP client
apscheduler==3.10.4      # Background task scheduling
python-dotenv==1.0.0     # Environment variable loading
```

### Database Integration
- Uses SQLAlchemy ORM
- Connection pooling (min=5, max=20)
- Async engine with asyncpg driver

### Cache Integration
- Redis async client (redis.asyncio)
- JSON serialization for complex objects
- TTL-based expiration

## Testing & Acceptance

### Unit Test Requirements

**Test Coverage Target: >85%**

#### Fetchers (test_alpha_vantage.py)
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_daily_prices_success():
    """Test successful price fetch"""
    # Mock API response
    mock_response = {
        "Time Series (Daily)": {
            "2026-02-13": {
                "1. open": "181.00",
                "2. high": "183.00",
                "3. low": "180.50",
                "4. close": "182.45",
                "5. adjusted close": "182.45",
                "6. volume": "45678900"
            }
        }
    }
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.json = AsyncMock(
            return_value=mock_response
        )
        
        client = AlphaVantageClient("test_key")
        async with client:
            prices = await client.get_daily_prices("AAPL")
        
        assert len(prices) == 1
        assert prices[0]["close"] == 182.45
        assert prices[0]["volume"] == 45678900

@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiter enforces delay"""
    # Test that requests are spaced 12s apart
    pass

@pytest.mark.asyncio
async def test_api_error_handling():
    """Test handling of API errors"""
    # Test Error Message response
    # Test rate limit response
    # Test network errors
    pass
```

#### Cache (test_cache.py)
```python
@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test basic cache operations"""
    cache = CacheManager("redis://localhost:6379")
    await cache.connect()
    
    await cache.set("test_key", {"value": 123})
    result = await cache.get("test_key")
    
    assert result["value"] == 123
    
    await cache.disconnect()

@pytest.mark.asyncio
async def test_cache_ttl_expiration():
    """Test TTL expiration"""
    # Set with 1 second TTL
    # Wait 2 seconds
    # Verify key expired
    pass

@pytest.mark.asyncio
async def test_cache_hit_rate_calculation():
    """Test hit rate statistics"""
    pass
```

#### Models (test_models.py)
```python
def test_price_data_validation():
    """Test Pydantic validation"""
    # Valid data
    valid = PriceData(
        ticker="AAPL",
        price=182.45,
        change=1.23,
        change_percent=0.68,
        volume=45678900,
        timestamp=datetime.now(),
        source="alpha_vantage"
    )
    assert valid.ticker == "AAPL"
    
    # Invalid data (negative price)
    with pytest.raises(ValidationError):
        PriceData(
            ticker="AAPL",
            price=-10.0,  # Invalid
            change=0,
            change_percent=0,
            volume=0,
            timestamp=datetime.now(),
            source="test"
        )
```

### Integration Test Scenarios

**Test with Real APIs (Sandbox/Dev Keys)**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_price_fetch():
    """Test complete flow: API → Database → Cache"""
    # 1. Fetch from Alpha Vantage
    # 2. Store in database
    # 3. Cache the result
    # 4. Verify all steps
    pass

@pytest.mark.integration
async def test_provider_fallback():
    """Test fallback when primary provider fails"""
    # 1. Mock Alpha Vantage failure
    # 2. Verify Polygon.io is attempted
    # 3. Verify data is still returned
    pass
```

### Acceptance Criteria (Testable)

**Functional Acceptance**
- [ ] GET /health returns 200 with all systems operational
- [ ] GET /api/v1/price/AAPL returns valid price data
- [ ] Historical data returns 30 days when requested
- [ ] Dividend endpoint returns at least 1 dividend for AAPL
- [ ] Manual sync queues background task successfully

**Performance Acceptance**
- [ ] Cached price request completes in <100ms (p95)
- [ ] Database query for 30 days completes in <200ms
- [ ] Can fetch 50 tickers in <60 seconds
- [ ] Cache hit rate >90% after warmup period

**Reliability Acceptance**
- [ ] Service handles Alpha Vantage rate limit gracefully
- [ ] Database connection failure doesn't crash service
- [ ] Cache failure doesn't prevent data access (degrades gracefully)
- [ ] Invalid ticker returns 404, not 500

### Known Edge Cases

1. **Market Closed**: Return last available price, indicate stale data
2. **Stock Split**: Adjusted close differs significantly from close
3. **Dividend Payment**: Price drop on ex-dividend date
4. **Invalid Ticker**: Return 404 with helpful error message
5. **Rate Limit Hit**: Exponential backoff, then fallback provider
6. **Database Duplicate**: UPSERT operation (ON CONFLICT DO UPDATE)
7. **Cache Miss During High Load**: Queue requests, deduplicate

### Performance/Reliability SLAs

**Service Level Objectives**
- Availability: 99.5% uptime (monthly)
- Response Time: p95 < 500ms, p99 < 1s
- Error Rate: <1% of requests
- Cache Hit Rate: >90% for current prices

**Monitoring Thresholds**
- Alert if error rate >5% for 5 minutes
- Alert if no successful sync in 30 minutes
- Alert if cache hit rate <80%
- Alert if p95 latency >1s

## Implementation Notes

### Gotchas
- Alpha Vantage free tier: 500 calls/day = ~20/hour max
- Rate limiting is critical - one burst can exhaust daily quota
- Adjusted close vs close: adjusted accounts for splits/dividends
- Ticker symbols: Case-insensitive, normalize to uppercase
- Market hours: Use pytz for timezone-aware datetime

### Best Practices
- Always use async/await for external API calls
- Implement circuit breaker for database failures
- Log all external API responses (for debugging)
- Use connection pooling for database
- Batch database inserts for efficiency
- Validate all input data with Pydantic

### References
- Alpha Vantage API Docs: https://www.alphavantage.co/documentation/
- FastAPI Async: https://fastapi.tiangolo.com/async/
- Redis Best Practices: https://redis.io/docs/management/optimization/

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create FastAPI application skeleton
- [ ] Set up database connection with SQLAlchemy
- [ ] Configure Redis cache connection
- [ ] Implement configuration management
- [ ] Add structured logging
- [ ] Create health check endpoint

### Phase 2: Alpha Vantage Integration
- [ ] Implement AlphaVantageClient class
- [ ] Add rate limiting logic
- [ ] Create price data fetcher
- [ ] Create dividend data fetcher
- [ ] Add error handling and retries
- [ ] Write unit tests

### Phase 3: Data Layer
- [ ] Implement CacheManager
- [ ] Create PriceService
- [ ] Implement database persistence
- [ ] Add UPSERT logic for deduplication
- [ ] Write integration tests

### Phase 4: API Endpoints
- [ ] Implement current price endpoint
- [ ] Implement historical prices endpoint
- [ ] Implement dividends endpoint
- [ ] Add request validation
- [ ] Add response models
- [ ] Write API tests

### Phase 5: Production Readiness
- [ ] Add comprehensive logging
- [ ] Implement metrics collection
- [ ] Add error tracking (Sentry)
- [ ] Load testing
- [ ] Documentation
- [ ] Deployment guide
