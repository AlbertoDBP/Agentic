"""Newsletters — ingested SA articles visualizer."""
import logging
import re

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import auth_headers
from app.client import agent_get
from app.config import get_service_url, settings

logger = logging.getLogger("admin.newsletters")
router = APIRouter(prefix="/newsletters", tags=["Newsletters"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def newsletters_page(request: Request, analyst_id: str = None):
    path = "/analysts/articles"
    if analyst_id:
        path += f"?analyst_id={analyst_id}"
    articles = await agent_get("02", path) or []

    analysts_data = await agent_get("02", "/analysts") or {}
    if isinstance(analysts_data, dict):
        analysts = analysts_data.get("analysts", [])
    else:
        analysts = analysts_data if isinstance(analysts_data, list) else []

    return templates.TemplateResponse("newsletters.html", {
        "request": request,
        "page": "newsletters",
        "articles": articles,
        "analysts": analysts,
        "selected_analyst": analyst_id,
    })


@router.post("/ingest")
async def ingest_article(request: Request):
    form = await request.form()
    url_or_id = form.get("sa_article_id", "").strip()
    analyst_id = form.get("analyst_id", "").strip()

    match = re.search(r'/article/(\d+)', url_or_id)
    if match:
        sa_id = match.group(1)
    else:
        digit_match = re.search(r'\d+', url_or_id)
        sa_id = digit_match.group(0) if digit_match else None

    if sa_id and analyst_id:
        url = f"{get_service_url('02')}/analysts/articles/ingest"
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    url,
                    headers=auth_headers(),
                    json={"sa_article_id": sa_id, "analyst_id": int(analyst_id)},
                )
                if resp.status_code >= 300:
                    logger.warning(f"Ingest POST {url} -> {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Ingest request failed: {e}")

    return RedirectResponse("/newsletters", status_code=303)


@router.post("/sync-suggestions/{article_id}")
async def sync_suggestions(article_id: int, request: Request):
    """Push BUY recommendations from an already-ingested article into analyst_suggestions."""
    url = f"{get_service_url('02')}/analysts/articles/{article_id}/sync-suggestions"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=auth_headers())
            result = resp.json() if resp.status_code < 300 else {}
            synced = result.get("synced", 0)
            logger.info(f"Sync suggestions article {article_id}: {synced} written")
    except Exception as e:
        logger.error(f"Sync suggestions failed for article {article_id}: {e}")
    return RedirectResponse("/newsletters", status_code=303)
