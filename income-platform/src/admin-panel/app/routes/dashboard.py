"""Dashboard — overview grid with health, key metrics, next jobs."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.client import check_all_health, agent_get
from app.database import engine

logger = logging.getLogger("admin.dashboard")
router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Parallel health checks
    health = await check_all_health()
    healthy_count = sum(1 for s in health if s["healthy"])
    total_count = len(health)

    # DB metrics
    metrics = {"positions": 0, "articles": 0, "alerts": 0, "proposals": 0}
    try:
        with engine.connect() as conn:
            for table, key in [
                ("positions", "positions"),
                ("articles", "articles"),
                ("alerts", "alerts"),
                ("proposals", "proposals"),
            ]:
                try:
                    row = conn.execute(
                        text(f"SELECT COUNT(*) FROM platform_shared.{table}")
                    ).scalar()
                    metrics[key] = row or 0
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"DB metrics error: {e}")

    # Scheduler jobs
    jobs = await agent_get("99", "/jobs")
    job_list = jobs.get("jobs", []) if jobs else []

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "page": "dashboard",
        "health": health,
        "healthy_count": healthy_count,
        "total_count": total_count,
        "metrics": metrics,
        "jobs": job_list[:5],
    })
