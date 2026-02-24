"""
Agent 02 — Newsletter Ingestion Service
API: Health endpoint

Returns service status, database connectivity, cache status,
and Prefect flow run metadata.
"""
import time
import logging
from datetime import datetime, timezone
from fastapi import APIRouter

from app.database import check_database_connection
from app.config import settings
from app.models.schemas import HealthResponse, FlowStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# Service start time for uptime calculation
_start_time = time.time()


def _check_cache() -> dict:
    """Verify Redis/Valkey connectivity."""
    try:
        import redis
        client = redis.from_url(settings.redis_url, socket_timeout=2)
        client.ping()
        info = client.info("server")
        return {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def _get_flow_status(flow_name: str) -> FlowStatus:
    """
    Retrieve last flow run metadata from the database.
    Gracefully returns empty status if flow has never run.
    """
    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    last_run_at,
                    last_run_status,
                    next_scheduled_at,
                    articles_processed
                FROM platform_shared.flow_run_log
                WHERE flow_name = :name
                ORDER BY last_run_at DESC
                LIMIT 1
            """), {"name": flow_name}).fetchone()

        if result:
            return FlowStatus(
                last_run=result[0],
                last_run_status=result[1],
                next_scheduled=result[2],
                articles_processed_last_run=result[3],
            )
    except Exception:
        pass  # flow_run_log may not exist yet on first deployment

    return FlowStatus(
        last_run=None,
        last_run_status=None,
        next_scheduled=None,
        articles_processed_last_run=None,
    )


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """
    Service health check.
    Returns overall status, component checks, and flow run metadata.
    Status: healthy | degraded | unhealthy
    """
    db_health   = check_database_connection()
    cache_health = _check_cache()

    # Determine overall status
    if db_health["status"] == "unhealthy":
        overall = "unhealthy"
    elif cache_health["status"] == "unhealthy":
        overall = "degraded"   # service runs without cache but at reduced performance
    else:
        overall = "healthy"

    return HealthResponse(
        status=overall,
        service=settings.service_name,
        version="0.1.0",
        environment=settings.environment,
        database=db_health,
        cache=cache_health,
        harvester_flow=_get_flow_status("harvester_flow"),
        intelligence_flow=_get_flow_status("intelligence_flow"),
        uptime_seconds=round(time.time() - _start_time, 1),
        timestamp=datetime.now(timezone.utc),
    )
