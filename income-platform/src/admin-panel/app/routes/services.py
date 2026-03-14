"""Services — detailed health, restart, log viewer."""
import logging
import subprocess

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import check_all_health
from app.config import settings

logger = logging.getLogger("admin.services")
router = APIRouter(prefix="/services", tags=["Services"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def services_page(request: Request):
    health = await check_all_health()
    return templates.TemplateResponse("services.html", {
        "request": request,
        "page": "services",
        "services": health,
    })


@router.post("/{num}/restart")
async def restart_service(num: str):
    svc = next((s for s in settings.services if s["num"] == num), None)
    if not svc:
        return RedirectResponse("/services", status_code=303)
    try:
        subprocess.run(
            ["docker", "restart", svc["container"]],
            timeout=30, capture_output=True,
        )
        logger.info(f"Restarted {svc['container']}")
    except Exception as e:
        logger.error(f"Restart failed: {e}")
    return RedirectResponse("/services", status_code=303)


@router.get("/{num}/logs", response_class=HTMLResponse)
async def service_logs(request: Request, num: str, lines: int = 100):
    svc = next((s for s in settings.services if s["num"] == num), None)
    log_text = ""
    label = num
    if svc:
        label = svc["label"]
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), svc["container"]],
                timeout=10, capture_output=True, text=True,
            )
            log_text = result.stdout + result.stderr
        except Exception as e:
            log_text = f"Error fetching logs: {e}"
    else:
        log_text = f"Unknown service: {num}"

    return templates.TemplateResponse("logs.html", {
        "request": request,
        "page": "services",
        "label": label,
        "num": num,
        "lines": lines,
        "log_text": log_text,
    })
