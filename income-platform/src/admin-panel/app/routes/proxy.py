"""
Admin Panel — JSON proxy routes for Agent 05 (Tax), 06 (Scenario), 07 (Scanner).
The Next.js frontend calls these endpoints; the admin panel forwards with auth.

Routes:
  /api/scanner/*   → Agent 07 (port 8007)
  /api/scenarios/* → Agent 06 (port 8006)
  /api/tax/*       → Agent 05 (port 8005)
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import auth_headers
from app.config import settings

logger = logging.getLogger("admin.proxy")
router = APIRouter(prefix="/api")

# Increase timeout for scan operations (scoring can take a while)
_SCAN_TIMEOUT = 120
_DEFAULT_TIMEOUT = 30


def _base(service: str) -> str:
    return {
        "scanner": settings.agent07_url,
        "scenarios": settings.agent06_url,
        "tax": settings.agent05_url,
        "market-data": settings.agent01_url,
        "broker": settings.broker_url,
        "scoring": settings.agent03_url,
        "alerts": settings.agent11_url,
    }[service]


async def _proxy(
    method: str,
    service: str,
    sub_path: str,
    request: Request,
    timeout: int = _DEFAULT_TIMEOUT,
) -> JSONResponse:
    """Forward a request to the target service with auth headers."""
    url = f"{_base(service)}{sub_path}"
    headers = auth_headers()

    # Forward query params
    query = str(request.url.query)
    if query:
        url = f"{url}?{query}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            elif method == "PATCH":
                body = await request.body()
                resp = await client.patch(
                    url,
                    headers={**headers, "Content-Type": "application/json"},
                    content=body,
                )
            else:
                body = await request.body()
                resp = await client.post(
                    url,
                    headers={**headers, "Content-Type": "application/json"},
                    content=body,
                )

        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text[:500])
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"{service} service timed out")
    except Exception as exc:
        logger.error("Proxy %s %s → %s", method, url, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ─── Broker Service ──────────────────────────────────────────────────────────

@router.get("/broker/providers")
async def broker_providers(request: Request):
    return await _proxy("GET", "broker", "/broker/providers", request)


@router.get("/broker/connection")
async def broker_connection(request: Request):
    return await _proxy("GET", "broker", "/broker/connection", request)


@router.post("/broker/sync")
async def broker_sync(request: Request):
    return await _proxy("POST", "broker", "/broker/sync", request, timeout=60)


@router.post("/broker/orders")
async def broker_place_order(request: Request):
    return await _proxy("POST", "broker", "/broker/orders", request, timeout=30)


@router.get("/broker/orders/{order_id}")
async def broker_get_order(order_id: str, request: Request):
    return await _proxy("GET", "broker", f"/broker/orders/{order_id}", request)


@router.delete("/broker/orders/{order_id}")
async def broker_cancel_order(order_id: str, request: Request):
    return await _proxy("DELETE", "broker", f"/broker/orders/{order_id}", request)


# ─── Market Data (Agent 01) ───────────────────────────────────────────────────

@router.get("/market-data/price/{symbol}")
async def market_data_price(symbol: str, request: Request):
    return await _proxy("GET", "market-data", f"/stocks/{symbol.upper()}/price", request)


@router.get("/market-data/fundamentals/{symbol}")
async def market_data_fundamentals(symbol: str, request: Request):
    return await _proxy("GET", "market-data", f"/stocks/{symbol.upper()}/fundamentals", request)


# ─── Scanner (Agent 07) ───────────────────────────────────────────────────────

@router.get("/scanner/quote/{symbol}")
async def scanner_quote(symbol: str, request: Request):
    return await _proxy("GET", "scanner", f"/quote/{symbol.upper()}", request)


@router.post("/scanner/scan")
async def scanner_scan(request: Request):
    return await _proxy("POST", "scanner", "/scan", request, timeout=_SCAN_TIMEOUT)


@router.get("/scanner/scan/{scan_id}")
async def scanner_get_scan(scan_id: str, request: Request):
    return await _proxy("GET", "scanner", f"/scan/{scan_id}", request)


@router.get("/scanner/universe")
async def scanner_universe(request: Request):
    return await _proxy("GET", "scanner", "/universe", request)


@router.post("/scanner/cache/refresh")
async def scanner_cache_refresh(request: Request):
    return await _proxy("POST", "scanner", "/cache/refresh", request, timeout=_SCAN_TIMEOUT)


# ─── Scenarios (Agent 06) ─────────────────────────────────────────────────────

@router.post("/scenarios/stress-test")
async def scenarios_stress_test(request: Request):
    return await _proxy("POST", "scenarios", "/scenarios/stress-test", request, timeout=_SCAN_TIMEOUT)


@router.post("/scenarios/income-projection")
async def scenarios_income_projection(request: Request):
    return await _proxy("POST", "scenarios", "/scenarios/income-projection", request, timeout=_SCAN_TIMEOUT)


@router.post("/scenarios/vulnerability")
async def scenarios_vulnerability(request: Request):
    return await _proxy("POST", "scenarios", "/scenarios/vulnerability", request, timeout=_SCAN_TIMEOUT)


@router.get("/scenarios/library")
async def scenarios_library(request: Request):
    return await _proxy("GET", "scenarios", "/scenarios/library", request)


# ─── Tax (Agent 05) ──────────────────────────────────────────────────────────

@router.get("/tax/profile/{symbol}")
async def tax_profile_get(symbol: str, request: Request):
    return await _proxy("GET", "tax", f"/tax/profile/{symbol}", request)


@router.post("/tax/profile")
async def tax_profile_post(request: Request):
    return await _proxy("POST", "tax", "/tax/profile", request)


@router.post("/tax/calculate")
async def tax_calculate(request: Request):
    return await _proxy("POST", "tax", "/tax/calculate", request)


@router.get("/tax/calculate/{symbol}")
async def tax_calculate_get(symbol: str, request: Request):
    return await _proxy("GET", "tax", f"/tax/calculate/{symbol}", request)


# ─── Income Scoring (Agent 03) ───────────────────────────────────────────────

@router.post("/scores/evaluate")
async def scores_evaluate(request: Request):
    return await _proxy("POST", "scoring", "/scores/evaluate", request, timeout=60)


@router.get("/scores/{ticker}")
async def scores_get(ticker: str, request: Request):
    return await _proxy("GET", "scoring", f"/scores/{ticker.upper()}", request)


@router.get("/scores")
async def scores_list(request: Request):
    return await _proxy("GET", "scoring", "/scores/", request)


# ─── Tax (Agent 05) ──────────────────────────────────────────────────────────

@router.post("/tax/optimize")
async def tax_optimize(request: Request):
    return await _proxy("POST", "tax", "/tax/optimize", request, timeout=_SCAN_TIMEOUT)


@router.post("/tax/optimize/portfolio")
async def tax_optimize_portfolio(request: Request):
    return await _proxy("POST", "tax", "/tax/optimize/portfolio", request, timeout=_SCAN_TIMEOUT)


@router.post("/tax/harvest")
async def tax_harvest(request: Request):
    return await _proxy("POST", "tax", "/tax/harvest", request)


@router.get("/tax/asset-classes")
async def tax_asset_classes(request: Request):
    return await _proxy("GET", "tax", "/tax/asset-classes", request)


# ─── Smart Alerts (Agent 11) ────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(request: Request):
    return await _proxy("GET", "alerts", "/alerts", request)


@router.post("/alerts/scan")
async def scan_alerts(request: Request):
    return await _proxy("POST", "alerts", "/alerts/scan", request)


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: Request):
    return await _proxy("PATCH", "alerts", f"/alerts/{alert_id}/resolve", request)
