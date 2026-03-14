"""HTTP client helpers for calling agents + parallel health checks."""
import asyncio
import logging
import time

import httpx

from app.auth import auth_headers
from app.config import settings, get_service_url

logger = logging.getLogger("admin.client")


async def check_health(svc: dict) -> dict:
    """Check /health for one service. Returns dict with status info."""
    url = f"{get_service_url(svc['num'])}/health"
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(url)
            ms = int((time.monotonic() - start) * 1000)
            return {
                **svc,
                "healthy": resp.status_code == 200,
                "status_code": resp.status_code,
                "ms": ms,
                "detail": resp.json() if resp.status_code == 200 else None,
            }
    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        return {
            **svc,
            "healthy": False,
            "status_code": 0,
            "ms": ms,
            "detail": str(e),
        }


async def check_all_health() -> list[dict]:
    """Parallel health check for all services."""
    tasks = [check_health(svc) for svc in settings.services]
    return await asyncio.gather(*tasks)


async def agent_get(num: str, path: str) -> dict | list | None:
    """GET an agent endpoint with auth."""
    url = f"{get_service_url(num)}{path}"
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(url, headers=auth_headers())
            if resp.status_code < 300:
                return resp.json()
            logger.warning(f"GET {url} → {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"GET {url} → {e}")
        return None


async def agent_post(num: str, path: str, json: dict | None = None) -> dict | None:
    """POST to an agent endpoint with auth."""
    url = f"{get_service_url(num)}{path}"
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.post(url, headers=auth_headers(), json=json or {})
            if resp.status_code < 300:
                return resp.json()
            logger.warning(f"POST {url} → {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"POST {url} → {e}")
        return None
