"""Agent 04 — Health Check"""
from fastapi import APIRouter
from app.database import verify_connection
from app.config import settings

router = APIRouter()


@router.get("/health")
def health():
    db_ok = verify_connection()
    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "service": settings.service_name,
        "database": "connected" if db_ok else "disconnected",
        "port": settings.service_port,
    }
