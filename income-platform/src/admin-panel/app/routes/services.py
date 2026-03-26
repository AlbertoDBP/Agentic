"""Services — detailed health, restart, log viewer via Docker socket API."""
import logging
import struct

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.client import check_all_health
from app.config import settings

logger = logging.getLogger("admin.services")
router = APIRouter(prefix="/services", tags=["Services"])
templates = Jinja2Templates(directory="app/templates")

DOCKER_SOCKET = "/var/run/docker.sock"


def _docker_transport():
    return httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET)


def _parse_docker_log_stream(data: bytes) -> str:
    """Parse Docker multiplexed log stream (8-byte header + payload per frame)."""
    lines = []
    i = 0
    while i + 8 <= len(data):
        size = struct.unpack(">I", data[i + 4 : i + 8])[0]
        i += 8
        if size and i + size <= len(data):
            lines.append(data[i : i + size].decode("utf-8", errors="replace"))
        i += size
    return "".join(lines) if lines else data.decode("utf-8", errors="replace")


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
        async with httpx.AsyncClient(
            transport=_docker_transport(), base_url="http://localhost"
        ) as client:
            resp = await client.post(f"/containers/{svc['container']}/restart")
            if resp.status_code in (204, 200):
                logger.info("Restarted %s", svc["container"])
            else:
                logger.warning("Restart %s → %s", svc["container"], resp.status_code)
    except Exception as e:
        logger.error("Restart failed: %s", e)
    return RedirectResponse("/services", status_code=303)


@router.get("/{num}/logs", response_class=HTMLResponse)
async def service_logs(request: Request, num: str, lines: int = 100):
    svc = next((s for s in settings.services if s["num"] == num), None)
    log_text = ""
    label = num
    if svc:
        label = svc["label"]
        try:
            async with httpx.AsyncClient(
                transport=_docker_transport(), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    f"/containers/{svc['container']}/logs",
                    params={"stdout": "1", "stderr": "1", "tail": str(lines)},
                )
                if resp.status_code == 200:
                    log_text = _parse_docker_log_stream(resp.content)
                else:
                    log_text = f"Docker API error {resp.status_code}: {resp.text}"
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
