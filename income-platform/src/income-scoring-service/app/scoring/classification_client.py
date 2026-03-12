"""
Agent 03 — Classification Client
Async HTTP client for Agent 04 (Asset Classification Service, port 8004).

Returns (asset_class, tax_efficiency) on success.
Returns (None, None) on any error so the caller can decide how to handle it.
"""
import logging
import os
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Read URL at call time (not import time) so tests can override via env var
_DEFAULT_URL = "http://localhost:8004"
_DEFAULT_TIMEOUT = 5


def _base_url() -> str:
    from app.config import settings
    return getattr(settings, "asset_classification_service_url", _DEFAULT_URL).rstrip("/")


def _timeout() -> int:
    from app.config import settings
    return getattr(settings, "asset_classification_timeout", _DEFAULT_TIMEOUT)


def _jwt_secret() -> str:
    from app.config import settings
    return settings.jwt_secret


def _make_token(secret: str) -> str:
    """Generate a short-lived HS256 JWT for inter-service calls (stdlib only)."""
    import base64
    import hashlib
    import hmac
    import json
    import time

    header  = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "agent-03", "exp": int(time.time()) + 60}).encode()
    ).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{signing_input}.{sig}"


async def get_asset_class(
    ticker: str,
) -> Tuple[Optional[str], Optional[dict]]:
    """Call Agent 04 to classify a ticker.

    Returns:
        (asset_class, tax_efficiency) on success.
        (None, None) on any connection or response error.
    """
    url = f"{_base_url()}/classify"
    try:
        secret = _jwt_secret()
        token  = _make_token(secret)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.post(url, json={"ticker": ticker}, headers=headers)
        if resp.status_code != 200:
            logger.warning(
                "Agent 04 classify %s returned HTTP %s", ticker, resp.status_code
            )
            return None, None
        data = resp.json()
        asset_class   = data.get("asset_class")
        tax_efficiency = data.get("tax_efficiency")
        logger.info("Agent 04 classified %s → %s (confidence=%.2f)",
                    ticker, asset_class, data.get("confidence", 0.0))
        return asset_class, tax_efficiency
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning("Agent 04 unavailable for %s: %s", ticker, e)
        return None, None
    except Exception as e:
        logger.warning("Agent 04 unexpected error for %s: %s", ticker, e)
        return None, None
