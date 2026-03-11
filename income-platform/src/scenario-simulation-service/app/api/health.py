"""
Agent 06 — Scenario Simulation Service
API: Health check router.
"""
from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "healthy",
    }
