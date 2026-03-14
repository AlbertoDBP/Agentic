"""Proposals — list, accept/reject workflow (Agent 12)."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import agent_get, agent_post

logger = logging.getLogger("admin.proposals")
router = APIRouter(prefix="/proposals", tags=["Proposals"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def proposals_page(request: Request):
    data = await agent_get("12", "/proposals") or []
    if isinstance(data, dict):
        data = data.get("proposals", [])

    return templates.TemplateResponse("proposals.html", {
        "request": request,
        "page": "proposals",
        "proposals": data,
    })


@router.post("/{proposal_id}/accept")
async def accept_proposal(proposal_id: str):
    await agent_post("12", f"/proposals/{proposal_id}/accept")
    return RedirectResponse("/proposals", status_code=303)


@router.post("/{proposal_id}/reject")
async def reject_proposal(proposal_id: str):
    await agent_post("12", f"/proposals/{proposal_id}/reject")
    return RedirectResponse("/proposals", status_code=303)
