"""
Agent 06 — Scenario Simulation Service
FastAPI application entry point.
"""
import logging

from fastapi import FastAPI

from app.config import settings
from app.api import health, scenarios

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Scenario Simulation Service",
    description="Agent 06 — Stress testing and income projection for income portfolios.",
    version=settings.service_version,
)


@app.on_event("startup")
async def startup():
    logger.info(
        "Starting %s v%s on port %d",
        settings.service_name,
        settings.service_version,
        settings.port,
    )


app.include_router(health.router)
app.include_router(scenarios.router)
