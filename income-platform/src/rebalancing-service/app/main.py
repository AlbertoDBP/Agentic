"""Agent 08 — Rebalancing Service entry point."""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from app.api.health import router as health_router
from app.api.rebalance import router as rebalance_router
from app.auth import verify_token
from app.config import settings
from app.rebalancer import portfolio_reader

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await portfolio_reader.init_pool()
    logger.info("Agent 08 — %s v%s starting", settings.service_name, settings.service_version)
    yield
    await portfolio_reader.close_pool()
    logger.info("Agent 08 shutting down.")


app = FastAPI(
    title="Income Fortress — Rebalancing Service",
    description=(
        "Agent 08: Analyses portfolio positions against constraints, "
        "calls Agent 03 for scoring and Agent 05 for tax-loss harvest impact, "
        "and returns prioritised rebalancing proposals. NEVER executes trades."
    ),
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(rebalance_router, dependencies=[Depends(verify_token)])
