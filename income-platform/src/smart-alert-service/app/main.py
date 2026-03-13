"""Agent 11 — Smart Alert Service entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.alerts import router as alerts_router
from app.api.health import router as health_router
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
        "Agent 11 — %s v%s starting on port %d",
        settings.service_name,
        settings.service_version,
        settings.port,
    )
    yield
    logger.info("Agent 11 shutting down.")


app = FastAPI(
    title="Income Fortress — Smart Alert Service",
    description=(
        "Agent 11: Aggregates signals from Agents 07–10 and runs circuit-breaker "
        "detection on income scores and feature data. Routes alerts through a "
        "confirmation gate before surfacing as CONFIRMED."
    ),
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(alerts_router)
