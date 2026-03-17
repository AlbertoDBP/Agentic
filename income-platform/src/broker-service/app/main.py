"""
Broker Service — FastAPI application entry point.
Port: 8013

Provides a broker-agnostic API for:
  - Account sync (positions + cash balance → platform_shared DB)
  - Order execution (routed to the correct broker provider)
  - Connection testing

Current providers: alpaca
Future providers:   schwab, fidelity, interactive_brokers
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.broker import router as broker_router
from app.api.health import router as health_router
from app.auth import verify_token
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Broker Service v%s starting on port %d", settings.version, settings.port)
    try:
        init_db()
        logger.info("Database connection initialised")
    except Exception as exc:
        logger.warning("Database init failed (service will start degraded): %s", exc)
    yield
    logger.info("Broker Service shutting down")


app = FastAPI(
    title="Income Fortress — Broker Service",
    description=(
        "Provider-agnostic broker integration: sync account positions/balance "
        "from any connected broker and execute orders. "
        "Current providers: Alpaca."
    ),
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(broker_router, dependencies=[Depends(verify_token)])
