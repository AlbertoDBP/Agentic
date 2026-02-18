"""
Market Data Service - FastAPI Application
Main entry point for the service
"""
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime

from .config import settings
from .models import PriceData, HealthResponse
from .cache import CacheManager
from .database import DatabaseManager
from .fetchers.alpha_vantage import AlphaVantageClient

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
cache_manager: CacheManager = None
db_manager: DatabaseManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    global cache_manager, db_manager

    logger.info(f"🚀 Starting {settings.service_name}...")

    # Initialize cache
    cache_manager = CacheManager(settings.redis_url)
    await cache_manager.connect()

    # Initialize database
    db_manager = DatabaseManager(settings.database_url)
    await db_manager.connect()

    logger.info(f"✅ {settings.service_name} started on port {settings.service_port}")

    yield

    # Shutdown
    logger.info(f"🛑 Shutting down {settings.service_name}...")
    if cache_manager:
        await cache_manager.disconnect()
    if db_manager:
        await db_manager.disconnect()
    
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Market Data Service",
    description="Real-time and historical market data API for Income Fortress Platform",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    
    # Check cache
    cache_connected = await cache_manager.is_connected() if cache_manager else False
    
    # TODO: Check database
    db_status = "not_implemented"
    
    return HealthResponse(
        status="healthy" if cache_connected else "degraded",
        database=db_status,
        cache="connected" if cache_connected else "disconnected"
    )


@app.get("/api/v1/price/{ticker}", response_model=PriceData)
async def get_current_price(ticker: str):
    """
    Get current price for a ticker
    
    - Checks cache first
    - Falls back to Alpha Vantage API
    - Caches result for 5 minutes
    """
    ticker = ticker.upper()
    cache_key = f"price:current:{ticker}"
    
    # Try cache first
    if cache_manager:
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            logger.info(f"✅ Cache hit for {ticker}")
            return PriceData(**cached_data, cached=True)
    
    # Fetch from API
    logger.info(f"📡 Fetching {ticker} from Alpha Vantage...")
    
    try:
        async with AlphaVantageClient(
            api_key=settings.market_data_api_key,
            calls_per_minute=5
        ) as client:
            prices = await client.get_daily_prices(ticker, outputsize="compact")
            
            if not prices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for ticker {ticker}"
                )
            
            # Get most recent price
            latest = prices[0]
            
            # Calculate change from previous day
            change = 0.0
            change_percent = 0.0
            if len(prices) > 1:
                prev_close = prices[1]["close"]
                change = latest["close"] - prev_close
                change_percent = (change / prev_close) * 100
            
            # Create response
            price_data = PriceData(
                ticker=ticker,
                price=latest["close"],
                change=round(change, 2),
                change_percent=round(change_percent, 2),
                volume=latest["volume"],
                timestamp=datetime.now(),
                source="alpha_vantage",
                cached=False
            )
            
            # Cache for 5 minutes
            if cache_manager:
                await cache_manager.set(
                    cache_key,
                    price_data.dict(),
                    ttl=settings.cache_ttl_current_price
                )
            
            logger.info(f"✅ Fetched {ticker}: ${price_data.price}")
            return price_data
    
    except ValueError as e:
        logger.error(f"❌ API error for {ticker}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Unexpected error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    if not cache_manager:
        return {"error": "Cache not initialized"}
    
    return await cache_manager.get_stats()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
