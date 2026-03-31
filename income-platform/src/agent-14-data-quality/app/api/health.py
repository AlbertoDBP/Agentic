# src/agent-14-data-quality/app/api/health.py
from fastapi import APIRouter
from app.database import check_database_connection

router = APIRouter()


@router.get("/health")
def health():
    db = check_database_connection()
    return {
        "service": "agent-14-data-quality",
        "status": "healthy" if db["status"] == "healthy" else "degraded",
        "database": db,
    }
