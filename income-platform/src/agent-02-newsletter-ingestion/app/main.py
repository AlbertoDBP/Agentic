"""
Agent 02 — Newsletter Ingestion Service (The Dividend Detective)
Entry Point: FastAPI application

Service: agent-02-newsletter-ingestion
Port:    8002
Schema:  platform_shared

Endpoints registered here — implementations built phase by phase:
  Phase 1 (current): /health
  Phase 2: article ingestion (internal — triggered by Prefect)
  Phase 3: intelligence endpoints (internal)
  Phase 4: /analysts, /recommendations, /consensus, /signal
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.health import router as health_router

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: validate database connection and required extensions.
    Shutdown: release any held resources.
    """
    logger.info(f"Starting {settings.service_name} on port {settings.service_port}")

    from app.database import check_database_connection
    health = check_database_connection()

    if health["status"] != "healthy":
        logger.error(f"Database connection failed on startup: {health}")
        # Log and continue — let health endpoint surface the issue
        # rather than crashing the pod (allows graceful degradation)
    else:
        logger.info(
            f"Database healthy | pgvector: {health.get('pgvector_installed')} "
            f"| schema: {health.get('schema_exists')}"
        )

    yield

    logger.info(f"Shutting down {settings.service_name}")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agent 02 — Newsletter Ingestion Service",
    description=(
        "The Dividend Detective: ingests Seeking Alpha analyst content, "
        "extracts income investment signals, maintains analyst accuracy profiles, "
        "and produces AnalystSignal objects for the Proposal Agent (Agent 12)."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [
        "https://legatoinvest.com",
        "https://app.legatoinvest.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

# Phase 1 — Foundation
app.include_router(health_router)

# Phase 2 — Harvester Flow API
from app.api.flows import router as flows_router
app.include_router(flows_router)

# Phase 4 — Full API layer
from app.api.analysts import router as analysts_router
from app.api.recommendations import router as recommendations_router
from app.api.consensus import router as consensus_router
from app.api.signal import router as signal_router
app.include_router(analysts_router, prefix="/analysts", tags=["Analysts"])
app.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(consensus_router, prefix="/consensus", tags=["Consensus"])
app.include_router(signal_router, prefix="/signal", tags=["Signal"])
# from app.api.intelligence import router as intelligence_router
# app.include_router(intelligence_router, prefix="/intelligence", tags=["Intelligence"])

# Phase 4 — Full API layer (added in Phase 4)
# from app.api.analysts import router as analysts_router
# from app.api.recommendations import router as recommendations_router
# from app.api.consensus import router as consensus_router
# from app.api.signal import router as signal_router
# app.include_router(analysts_router, prefix="/analysts", tags=["Analysts"])
# app.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"])
# app.include_router(consensus_router, prefix="/consensus", tags=["Consensus"])
# app.include_router(signal_router, prefix="/signal", tags=["Signal"])


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.service_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


# ── Dev server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=(settings.environment == "development"),
        log_level=settings.log_level.lower(),
    )
