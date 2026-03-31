# src/agent-14-data-quality/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import check_database_connection

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.service_name} on port {settings.service_port}")
    health = check_database_connection()
    if health["status"] != "healthy":
        logger.error(f"Database connection failed: {health}")
    else:
        logger.info(f"Database healthy — schema: {health.get('schema_exists')}")
    yield
    logger.info(f"Shutting down {settings.service_name}")


app = FastAPI(
    title="Data Quality Engine",
    description="Completeness scanning, self-healing, and quality gating for market data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.health import router as health_router
from app.api.routes import router as dq_router

app.include_router(health_router)
app.include_router(dq_router, prefix="/data-quality")
