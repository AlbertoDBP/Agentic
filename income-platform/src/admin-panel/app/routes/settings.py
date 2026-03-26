"""Settings — platform parameters including schedule management."""
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import agent_get, agent_post
from app.config import settings

logger = logging.getLogger("admin.settings")
router = APIRouter(prefix="/settings", tags=["Settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request):
    jobs_data = await agent_get("99", "/jobs")
    jobs = jobs_data.get("jobs", []) if jobs_data else []
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page": "settings",
        "jobs": jobs,
        "services": settings.services,
    })


@router.post("/reschedule/{job_id}")
async def reschedule_job(
    job_id: str,
    hour: int = Form(...),
    minute: int = Form(...),
    day_of_week: str = Form(None),
):
    payload = {"hour": hour, "minute": minute}
    if day_of_week:
        payload["day_of_week"] = day_of_week
    result = await agent_post("99", f"/jobs/{job_id}/reschedule", json=payload)
    if result is None:
        logger.warning("Reschedule call failed for %s", job_id)
    return RedirectResponse("/settings", status_code=303)
