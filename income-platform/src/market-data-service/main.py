"""
Market Data Service - FastAPI Application
Main entry point for the service.

Imports are loaded by file path via importlib so this file can be run directly:
    python3 src/market-data-service/main.py
or via uvicorn:
    uvicorn main:app --host 0.0.0.0 --port 8001
"""
import importlib.util
import logging
import statistics as _stats
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query

# ---------------------------------------------------------------------------
# Load service modules by file path (no relative imports needed)
# ---------------------------------------------------------------------------

_DIR = Path(__file__).resolve().parent


def _load(module_name: str, file_path: Path):
    """Load a module from an absolute file path and register it in sys.modules."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load order: dependencies first so downstream modules find them in sys.modules
_config   = _load("config",    _DIR / "config.py")
_models   = _load("models",    _DIR / "models.py")
_cache    = _load("cache",     _DIR / "cache.py")
_orms     = _load("orm_models", _DIR / "orm_models.py")
_database = _load("database",  _DIR / "database.py")
_av       = _load("fetchers.alpha_vantage", _DIR / "fetchers" / "alpha_vantage.py")
_repo     = _load("repositories.price_repository", _DIR / "repositories" / "price_repository.py")
_ph_repo  = _load("repositories.price_history_repository", _DIR / "repositories" / "price_history_repository.py")
_svc      = _load("services.price_service", _DIR / "services" / "price_service.py")
_mds      = _load("services.market_data_service", _DIR / "services" / "market_data_service.py")

settings                  = _config.settings
PriceData                 = _models.PriceData
HealthResponse            = _models.HealthResponse
StockHistoryResponse      = _models.StockHistoryResponse
StockHistoryStatsResponse = _models.StockHistoryStatsResponse
RefreshRequest            = _models.RefreshRequest
StockHistoryRefreshResponse = _models.StockHistoryRefreshResponse
CacheManager   = _cache.CacheManager
DatabaseManager = _database.DatabaseManager
PriceRepository        = _repo.PriceRepository
PriceHistoryRepository = _ph_repo.PriceHistoryRepository
PriceService           = _svc.PriceService
MarketDataService      = _mds.MarketDataService

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------

cache_manager: CacheManager = None
db_manager: DatabaseManager = None
price_service: PriceService = None
market_data_service: MarketDataService = None

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global cache_manager, db_manager, price_service, market_data_service

    logger.info(f"🚀 Starting {settings.service_name}...")

    # Initialize cache
    cache_manager = CacheManager(settings.redis_url)
    await cache_manager.connect()

    # Initialize database
    db_manager = DatabaseManager(settings.database_url)
    await db_manager.connect()

    # Wire the price service (gracefully handles None session_factory if DB is down)
    price_repo = (
        PriceRepository(db_manager.session_factory)
        if db_manager.session_factory
        else None
    )
    price_service = PriceService(
        price_repo=price_repo,
        cache_manager=cache_manager,
        av_api_key=settings.market_data_api_key,
        cache_ttl=settings.cache_ttl_current_price,
    )

    # Wire the market data service (historical prices via price_history table)
    price_history_repo = (
        PriceHistoryRepository(db_manager.session_factory)
        if db_manager.session_factory
        else None
    )
    market_data_service = MarketDataService(
        price_history_repo=price_history_repo,
        cache_manager=cache_manager,
        av_api_key=settings.market_data_api_key,
    )

    logger.info(f"✅ {settings.service_name} started on port {settings.service_port}")

    yield

    # Shutdown
    logger.info(f"🛑 Shutting down {settings.service_name}...")
    if cache_manager:
        await cache_manager.disconnect()
    if db_manager:
        await db_manager.disconnect()

    logger.info("✅ Shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Market Data Service",
    description="Real-time and historical market data API for Income Fortress Platform",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    cache_connected = await cache_manager.is_connected() if cache_manager else False
    db_connected = await db_manager.is_connected() if db_manager else False
    healthy = cache_connected and db_connected
    return HealthResponse(
        status="healthy" if healthy else "degraded",
        database="connected" if db_connected else "disconnected",
        cache="connected" if cache_connected else "disconnected",
    )


@app.get("/api/v1/price/{ticker}", response_model=PriceData)
async def get_current_price(ticker: str):
    """
    Get current price for a ticker.

    Strategy (in order):
    1. Redis cache (5-minute TTL)
    2. Database (market_data_daily table)
    3. Alpha Vantage API → persists to DB + cache
    """
    ticker = ticker.upper()
    try:
        data = await price_service.get_current_price(ticker)
        return PriceData(**data)
    except ValueError as e:
        logger.error(f"❌ Not found for {ticker}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/price/{ticker}/history")
async def get_historical_prices(
    ticker: str,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    """
    Get historical OHLCV prices for a ticker in a date range.

    Strategy (in order):
    1. Redis cache (6-hour TTL, keyed by ticker + date range)
    2. Database (price_history table)
    3. Alpha Vantage API → persists to DB + cache
    """
    ticker = ticker.upper()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    try:
        data = await market_data_service.get_historical_prices(ticker, start_date, end_date)
        return {"ticker": ticker, "start_date": str(start_date), "end_date": str(end_date), "count": len(data), "prices": data}
    except Exception as e:
        logger.error(f"❌ History error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/price/{ticker}/refresh")
async def refresh_historical_prices(
    ticker: str,
    full_history: bool = Query(False, description="Fetch full 20-year history (slow)"),
):
    """
    Force-refresh historical prices from Alpha Vantage and upsert to the database.
    Bypasses cache — always fetches from the API.
    """
    ticker = ticker.upper()
    try:
        count = await market_data_service.refresh_historical_prices(ticker, full_history=full_history)
        return {"ticker": ticker, "rows_upserted": count, "full_history": full_history}
    except Exception as e:
        logger.error(f"❌ Refresh error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/price/{ticker}/statistics")
async def get_price_statistics(
    ticker: str,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    """
    Calculate price statistics (min, max, avg, volatility) from stored historical data.
    Reads from the database only — call /refresh first if no data is present.
    """
    ticker = ticker.upper()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    try:
        stats = await market_data_service.get_price_statistics(ticker, start_date, end_date)
        return stats
    except Exception as e:
        logger.error(f"❌ Statistics error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/stocks/{symbol}/history",
    response_model=StockHistoryResponse,
)
async def get_stock_history(
    symbol: str,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    limit: int = Query(90, ge=1, le=365, description="Maximum number of records to return"),
):
    """
    Get historical OHLCV prices for a stock symbol in a date range.

    Returns at most `limit` records (default 90, max 365), oldest-first.
    Strategy: Redis cache (6 h) → price_history DB → Alpha Vantage API.
    """
    symbol = symbol.upper()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    try:
        prices = await market_data_service.get_historical_prices(symbol, start_date, end_date)
        limited = prices[:limit]
        return StockHistoryResponse(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            count=len(limited),
            prices=limited,
            source="alpha_vantage",
        )
    except ValueError as e:
        logger.error(f"❌ Stock history not found for {symbol}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Stock history error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/stocks/{symbol}/history/stats",
    response_model=StockHistoryStatsResponse,
)
async def get_stock_history_stats(
    symbol: str,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    """
    Calculate price statistics for a stock over a date range.

    Derives min, max, avg, volatility (std dev of daily closes), and
    price_change_pct ((last_close - first_close) / first_close * 100)
    from the stored price_history data, fetching from Alpha Vantage if needed.
    """
    symbol = symbol.upper()
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    try:
        prices = await market_data_service.get_historical_prices(symbol, start_date, end_date)
        period_days = (end_date - start_date).days

        if not prices:
            return StockHistoryStatsResponse(symbol=symbol, period_days=period_days)

        closes = [p["close"] for p in prices if p.get("close") is not None]
        if not closes:
            return StockHistoryStatsResponse(symbol=symbol, period_days=period_days)

        n = len(closes)
        price_change_pct = (
            round(((closes[-1] - closes[0]) / closes[0]) * 100, 4) if n > 1 else 0.0
        )
        return StockHistoryStatsResponse(
            symbol=symbol,
            period_days=period_days,
            min_price=round(min(closes), 4),
            max_price=round(max(closes), 4),
            avg_price=round(sum(closes) / n, 4),
            volatility=round(_stats.stdev(closes), 4) if n > 1 else 0.0,
            price_change_pct=price_change_pct,
        )
    except ValueError as e:
        logger.error(f"❌ Stock stats not found for {symbol}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Stock stats error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/stocks/{symbol}/history/refresh",
    response_model=StockHistoryRefreshResponse,
)
async def refresh_stock_history(
    symbol: str,
    body: RefreshRequest = Body(default_factory=RefreshRequest),
):
    """
    Force-fetch historical prices from Alpha Vantage and upsert to the database.

    Bypasses cache and DB read — always calls the API directly.
    Use full_history=true to request up to 20 years of data (slower, counts against API quota).
    """
    symbol = symbol.upper()
    try:
        count = await market_data_service.refresh_historical_prices(
            symbol, full_history=body.full_history
        )
        history_type = "full history" if body.full_history else "recent 100 days"
        return StockHistoryRefreshResponse(
            symbol=symbol,
            records_saved=count,
            source="alpha_vantage",
            message=f"Refreshed {history_type} for {symbol}: {count} records saved",
        )
    except ValueError as e:
        logger.warning(f"⚠️ Refresh API error for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Stock history refresh error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    if not cache_manager:
        return {"error": "Cache not initialized"}
    return await cache_manager.get_stats()


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.service_port,
        log_level=settings.log_level.lower(),
    )
