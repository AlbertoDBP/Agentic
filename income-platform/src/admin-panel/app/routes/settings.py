"""Settings — platform parameters including schedule management."""
import logging
from typing import List

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import agent_get, agent_post
from app.config import settings

logger = logging.getLogger("admin.settings")
router = APIRouter(prefix="/settings", tags=["Settings"])
templates = Jinja2Templates(directory="app/templates")

_ALL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_active_days(day_of_week: str | None) -> list[str]:
    """Expand 'mon-fri' / 'mon,wed,fri' into a list of day abbreviations."""
    if not day_of_week:
        return []
    active: set[str] = set()
    for part in str(day_of_week).split(","):
        part = part.strip().lower()
        if "-" in part:
            start, end = part.split("-", 1)
            try:
                s, e = _ALL_DAYS.index(start), _ALL_DAYS.index(end)
                active.update(_ALL_DAYS[s: e + 1])
            except ValueError:
                pass
        elif part in _ALL_DAYS:
            active.add(part)
    return [d for d in _ALL_DAYS if d in active]


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request):
    jobs_data = await agent_get("99", "/jobs")
    jobs = jobs_data.get("jobs", []) if jobs_data else []
    for job in jobs:
        sched = job.get("schedule") or {}
        job["active_days"] = _parse_active_days(sched.get("day_of_week"))
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page": "settings",
        "jobs": jobs,
        "services": settings.services,
        "all_days": _ALL_DAYS,
    })


@router.post("/reschedule/{job_id}")
async def reschedule_job(
    job_id: str,
    hour: int = Form(...),
    minute: int = Form(...),
    days: List[str] = Form(default=[]),
):
    payload = {"hour": hour, "minute": minute}
    if days:
        payload["day_of_week"] = ",".join(days)
    result = await agent_post("99", f"/jobs/{job_id}/reschedule", json=payload)
    if result is None:
        logger.warning("Reschedule call failed for %s", job_id)
    return RedirectResponse("/settings", status_code=303)
