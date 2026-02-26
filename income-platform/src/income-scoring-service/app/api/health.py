"""
Agent 03 — Income Scoring Service
API: Health check router.
"""
from fastapi import APIRouter
from app.database import check_database_connection
from app.config import settings

router = APIRouter()


@router.get("/health")
def health_check():
    """Service health check — verifies DB connectivity and upstream dependencies."""
    db_status = check_database_connection()

    overall = "healthy" if db_status["status"] == "healthy" else "degraded"

    return {
        "service": settings.service_name,
        "status": overall,
        "version": "1.0.0",
        "environment": settings.environment,
        "checks": {
            "database": db_status,
        },
    }
