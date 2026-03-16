"""
Agent 07 — Opportunity Scanner Service
FastAPI application entry point
Port: 8007
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.cache import router as cache_router
from app.api.health import router as health_router
from app.api.scanner import router as scanner_router
from app.auth import verify_token
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Agent 07 — %s v%s starting on port %d",
        settings.service_name,
        settings.service_version,
        settings.port,
    )
    yield
    logger.info("Agent 07 shutting down.")


app = FastAPI(
    title="Income Fortress — Opportunity Scanner Service",
    description=(
        "Agent 07: Scans a universe of income tickers, scores them via Agent 03, "
        "applies yield/quality filters, and returns a ranked candidate list. "
        "VETO gate enforced: tickers with score < 70 are flagged."
    ),
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(scanner_router, dependencies=[Depends(verify_token)])
app.include_router(cache_router)
