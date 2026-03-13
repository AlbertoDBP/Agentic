"""
Agent 08 — Tax Client
Calls Agent 05 POST /tax/harvest for tax-loss harvest impact.
Returns None on any error — never raises.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import date
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Default tax profile assumptions (can be overridden via user_preferences in future)
_DEFAULT_ANNUAL_INCOME = 150_000.0
_DEFAULT_FILING_STATUS = "single"


def _make_token() -> str:
    secret = settings.jwt_secret
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "agent-08", "exp": int(time.time()) + 60}).encode()
    ).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{signing_input}.{sig}"


def _holding_days(acquired_date) -> int:
    """Compute days held. Returns 0 if acquired_date is None."""
    if acquired_date is None:
        return 0
    if hasattr(acquired_date, "date"):
        acquired_date = acquired_date.date()
    return max(0, (date.today() - acquired_date).days)


async def get_harvest_impact(
    symbol: str,
    current_value: float,
    cost_basis: float,
    acquired_date,
) -> Optional[dict]:
    """
    Call Agent 05 POST /tax/harvest for a single position being trimmed/sold.
    Returns the relevant opportunity dict or None on error.
    """
    url = f"{settings.tax_optimization_url.rstrip('/')}/tax/harvest"
    holding_days = _holding_days(acquired_date)
    body = {
        "candidates": [{
            "symbol": symbol,
            "current_value": current_value,
            "cost_basis": cost_basis,
            "holding_period_days": holding_days,
            "account_type": "taxable",
        }],
        "annual_income": _DEFAULT_ANNUAL_INCOME,
        "filing_status": _DEFAULT_FILING_STATUS,
        "wash_sale_check": True,
    }
    try:
        token = _make_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=settings.tax_optimization_timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            logger.warning("Agent 05 returned HTTP %d for %s", resp.status_code, symbol)
            return None
        data = resp.json()
        opps = data.get("opportunities", [])
        return opps[0] if opps else None
    except httpx.TimeoutException:
        logger.warning("Agent 05 timed out for %s", symbol)
        return None
    except Exception as exc:
        logger.warning("Agent 05 call failed for %s: %s", symbol, exc)
        return None
