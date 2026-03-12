"""
Agent 05 — Tax Optimization Service
FastAPI application entry point
Port: 8005
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import router, health_router
from app.auth import verify_token

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Agent %d — %s v%s starting on port %d",
        settings.agent_id,
        settings.service_name,
        settings.version,
        settings.port,
    )
    yield
    logger.info("Agent %d shutting down.", settings.agent_id)


app = FastAPI(
    title="Income Fortress — Tax Optimization Service",
    description=(
        "Agent 05: Provides tax treatment profiling, after-tax yield calculation, "
        "account placement optimization, and tax-loss harvesting identification "
        "for income-generating investments."
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

app.include_router(health_router, prefix="")
app.include_router(router, prefix="", dependencies=[Depends(verify_token)])
