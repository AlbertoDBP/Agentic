"""Agent 10 — NAV Erosion Monitor entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.health import router as health_router
from app.api.monitor import router as monitor_router
from app.auth import verify_token
from app.config import settings
from app.monitor import snapshot_reader

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await snapshot_reader.init_pool()
    logger.info(
        "Agent 10 — %s v%s starting", settings.service_name, settings.service_version
    )
    yield
    await snapshot_reader.close_pool()
    logger.info("Agent 10 shutting down.")


app = FastAPI(
    title="Income Fortress — NAV Erosion Monitor",
    description=(
        "Agent 10: Monitors ETF/CEF/BDC NAV erosion over time by comparing "
        "nav_snapshots data against Agent 03 income scores. Detects premium/discount "
        "drift and NAV erosion, produces alerts for Agent 11."
    ),
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(monitor_router, dependencies=[Depends(verify_token)])
