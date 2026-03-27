"""Analysts — list registered analysts, trigger harvest (Agent 02)."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from fastapi.responses import JSONResponse
from app.client import agent_get, agent_post, agent_put

logger = logging.getLogger("admin.analysts")
router = APIRouter(prefix="/analysts", tags=["Analysts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def analysts_page(request: Request):
    data = await agent_get("02", "/analysts") or []
    if isinstance(data, dict):
        data = data.get("analysts", [])

    # Flow status
    flow_status = await agent_get("02", "/flows/status") or []

    return templates.TemplateResponse("analysts.html", {
        "request": request,
        "page": "analysts",
        "analysts": data,
        "flow_status": flow_status,
    })


@router.post("/harvest")
async def trigger_harvest():
    await agent_post("02", "/flows/harvester/trigger")
    return RedirectResponse("/analysts", status_code=303)


@router.post("/intelligence")
async def trigger_intelligence():
    await agent_post("02", "/flows/intelligence/trigger")
    return RedirectResponse("/analysts", status_code=303)


@router.post("/add")
async def add_analyst(request: Request):
    """Add a new analyst by SA publishing ID and display name."""
    form = await request.form()
    payload = {
        "sa_publishing_id": form.get("sa_publishing_id", "").strip(),
        "display_name": form.get("display_name", "").strip(),
    }
    await agent_post("02", "/analysts", payload)
    return RedirectResponse("/analysts", status_code=303)


@router.get("/lookup")
async def lookup_analyst_name(sa_id: str):
    """Proxy: look up SA author display name for a given SA publishing ID."""
    result = await agent_get("02", f"/analysts/lookup?sa_id={sa_id}")
    return JSONResponse(result or {"sa_id": sa_id, "display_name": None})


@router.post("/{analyst_id}/edit")
async def edit_analyst(analyst_id: int, request: Request):
    """Update an analyst's display_name, sa_publishing_id, and/or is_active status."""
    form = await request.form()
    payload: dict = {}
    if form.get("display_name"):
        payload["display_name"] = form.get("display_name").strip()
    if form.get("sa_publishing_id"):
        payload["sa_publishing_id"] = form.get("sa_publishing_id").strip()
    # is_active comes from a select: "true" or "false"
    if form.get("is_active") in ("true", "false"):
        payload["is_active"] = form.get("is_active") == "true"

    if payload:
        await agent_put("02", f"/analysts/{analyst_id}", payload)
    return RedirectResponse("/analysts", status_code=303)
