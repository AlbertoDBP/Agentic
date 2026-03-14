"""Analysts — list registered analysts, trigger harvest (Agent 02)."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import agent_get, agent_post

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
