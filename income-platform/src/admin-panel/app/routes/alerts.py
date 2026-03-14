"""Alerts — NAV alerts (Agent 10) + unified alerts (Agent 11)."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import agent_get, agent_post

logger = logging.getLogger("admin.alerts")
router = APIRouter(prefix="/alerts", tags=["Alerts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def alerts_page(request: Request):
    nav_alerts = await agent_get("10", "/monitor/alerts") or []
    if isinstance(nav_alerts, dict):
        nav_alerts = nav_alerts.get("alerts", [])

    unified_alerts = await agent_get("11", "/alerts") or []
    if isinstance(unified_alerts, dict):
        unified_alerts = unified_alerts.get("alerts", [])

    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "page": "alerts",
        "nav_alerts": nav_alerts,
        "unified_alerts": unified_alerts,
    })


@router.post("/resolve/{alert_id}")
async def resolve_alert(alert_id: str):
    await agent_post("11", f"/alerts/{alert_id}/resolve")
    return RedirectResponse("/alerts", status_code=303)
