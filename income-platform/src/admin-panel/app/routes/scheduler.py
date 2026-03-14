"""Scheduler — job table with trigger buttons."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import agent_get, agent_post

logger = logging.getLogger("admin.scheduler")
router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def scheduler_page(request: Request):
    jobs_data = await agent_get("99", "/jobs")
    jobs = jobs_data.get("jobs", []) if jobs_data else []

    return templates.TemplateResponse("scheduler.html", {
        "request": request,
        "page": "scheduler",
        "jobs": jobs,
    })


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str):
    await agent_post("99", f"/jobs/{job_id}/run")
    return RedirectResponse("/scheduler", status_code=303)
