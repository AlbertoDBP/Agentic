"""Health check endpoint."""
from fastapi import APIRouter
from app.database import check_db_health

router = APIRouter()


@router.get("/health")
def health() -> dict:
    db_ok = check_db_health()
    return {
        "status": "healthy",
        "service": "rebalancing-service",
        "version": "1.0.0",
        "agent_id": 8,
        "database": "connected" if db_ok else "unavailable",
    }
