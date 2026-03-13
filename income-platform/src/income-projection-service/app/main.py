"""Agent 09 — Income Projection Service entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.projection import router as projection_router
from app.config import settings
from app.projector import portfolio_reader

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await portfolio_reader.init_pool()
    logger.info(
        "Agent 09 — %s v%s starting on port %d",
        settings.service_name,
        settings.service_version,
        settings.port,
    )
    yield
    await portfolio_reader.close_pool()
    logger.info("Agent 09 shutting down.")


app = FastAPI(
    title="Income Fortress — Income Projection Service",
    description=(
        "Agent 09: Produces a position-level 12-month forward income forecast "
        "for a portfolio, enriched with yield and dividend-growth data from "
        "features_historical. NEVER modifies positions."
    ),
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(projection_router)
