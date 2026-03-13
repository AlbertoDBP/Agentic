"""Agent 12 — Proposal Service entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.health import router as health_router
from app.api.proposals import router as proposals_router
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
        "Agent 12 — %s v%s starting on port %d",
        settings.service_name,
        settings.service_version,
        settings.port,
    )
    yield
    logger.info("Agent 12 shutting down.")


app = FastAPI(
    title="Income Fortress — Proposal Service",
    description=(
        "Agent 12: Synthesises analyst signals (Agent 02) with platform assessment "
        "(Agents 03, 04, 05) into structured proposals. Presents both lenses side by side. "
        "The platform never silently overrides an analyst."
    ),
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(proposals_router, dependencies=[Depends(verify_token)])
