"""Health endpoint — Agent 12."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings
from app.database import check_db_health

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = check_db_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "agent_id": 12,
        "service": settings.service_name,
        "version": settings.service_version,
        "database": {"status": "ok" if db_ok else "unreachable"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
