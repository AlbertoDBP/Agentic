"""Agent 04 — Asset Classification Service"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import verify_connection
from app.api import health, classify, rules

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.service_name}...")
    if verify_connection():
        logger.info("✅ Database connected")
    else:
        logger.error("❌ Database connection failed — service degraded")
    logger.info(f"✅ {settings.service_name} started on port {settings.service_port}")
    yield
    logger.info(f"Application shutdown complete.")


app = FastAPI(
    title="Agent 04 — Asset Classification Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


app.include_router(health.router, tags=["health"])
app.include_router(classify.router, tags=["classification"])
app.include_router(rules.router, tags=["rules"])
