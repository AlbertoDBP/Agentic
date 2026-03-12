"""
Agent 06 — Scenario Simulation Service
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.config import settings
from app.api import health, scenarios
from app.auth import verify_token
from app.simulation import portfolio_reader

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await portfolio_reader.init_pool()
    logger.info(
        "Starting %s v%s on port %d",
        settings.service_name,
        settings.service_version,
        settings.port,
    )
    yield
    await portfolio_reader.close_pool()


app = FastAPI(
    title="Scenario Simulation Service",
    description="Agent 06 — Stress testing and income projection for income portfolios.",
    version=settings.service_version,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(scenarios.router, dependencies=[Depends(verify_token)])
