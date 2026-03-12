"""Agent 07 — Health endpoint."""
from fastapi import APIRouter
from app.database import check_db_health

router = APIRouter()


@router.get("/health")
def health():
    db_ok = check_db_health()
    return {
        "status": "healthy",
        "service": "opportunity-scanner-service",
        "version": "1.0.0",
        "agent_id": 7,
        "database": "connected" if db_ok else "unavailable",
    }
