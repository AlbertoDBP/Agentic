"""
Agent 02 — Newsletter Ingestion Service
API: Flow trigger and status endpoints

Endpoints:
  POST /flows/harvester/trigger    — trigger Harvester Flow (background)
  POST /flows/intelligence/trigger — 501 until Phase 3
  GET  /flows/status               — last run metadata for both flows
"""
import logging
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flows", tags=["Flows"])


class HarvesterTriggerRequest(BaseModel):
    analyst_ids: Optional[list[int]] = None


def _run_harvester(analyst_ids: Optional[list[int]] = None):
    """Execute Harvester Flow. Called in a background thread/task."""
    try:
        from app.flows.harvester_flow import harvester_flow
        harvester_flow(analyst_ids=analyst_ids)
    except Exception as e:
        logger.error(f"Harvester flow failed: {e}")


@router.post("/harvester/trigger")
def trigger_harvester(
    body: HarvesterTriggerRequest = HarvesterTriggerRequest(),
    background_tasks: BackgroundTasks = None,
):
    """
    Trigger the Harvester Flow asynchronously.
    Optionally scope to specific analyst DB IDs via analyst_ids.
    """
    analyst_ids = body.analyst_ids

    if background_tasks is not None:
        background_tasks.add_task(_run_harvester, analyst_ids)
    else:
        thread = threading.Thread(
            target=_run_harvester, args=(analyst_ids,), daemon=True
        )
        thread.start()

    if analyst_ids:
        message = f"Harvester triggered for analysts {analyst_ids}"
    else:
        message = "Harvester triggered for all active analysts"

    return {"triggered": True, "message": message}


@router.post("/intelligence/trigger")
def trigger_intelligence():
    """Intelligence Flow — not yet implemented (Phase 3)."""
    return JSONResponse(
        status_code=501,
        content={"detail": "Intelligence Flow not yet implemented (Phase 3)"},
    )


@router.get("/status")
def flow_status():
    """Return last run metadata for all registered flows."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT flow_name, last_run_at, last_run_status,
                       next_scheduled_at, articles_processed, duration_seconds
                FROM platform_shared.flow_run_log
                ORDER BY last_run_at DESC NULLS LAST
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning(f"flow_run_log not yet available: {e}")
        return []
