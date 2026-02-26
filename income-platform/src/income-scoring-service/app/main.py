"""
Agent 03 — Income Scoring Service
FastAPI application entry point.

Scores income-generating assets (dividend stocks, covered call ETFs, bonds)
using a quality gate + weighted scoring engine. Capital preservation first.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import check_database_connection, engine
from app.models import Base
from app.api import health, scores, quality_gate

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {settings.service_name} on port {settings.service_port}")

    # Create tables if they don't exist (idempotent)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    yield

    logger.info(f"Shutting down {settings.service_name}")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Income Scoring Service",
    description=(
        "Agent 03 — Scores income-generating assets using quality gates "
        "and weighted scoring across dividend stocks, covered call ETFs, and bonds."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": str(request.url)},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router, tags=["Health"])
app.include_router(scores.router, prefix="/scores", tags=["Scores"])
app.include_router(quality_gate.router, prefix="/quality-gate", tags=["Quality Gate"])


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
