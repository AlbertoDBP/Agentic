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
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

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
_svc      = _load("services.price_service", _DIR / "services" / "price_service.py")

settings       = _config.settings
PriceData      = _models.PriceData
HealthResponse = _models.HealthResponse
CacheManager   = _cache.CacheManager
DatabaseManager = _database.DatabaseManager
PriceRepository = _repo.PriceRepository
PriceService    = _svc.PriceService

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

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global cache_manager, db_manager, price_service

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
