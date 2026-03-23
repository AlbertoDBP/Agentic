"""
Agent 07 — Opportunity Scanner Service
Scoring Client: classifies via Agent 04, then calls Agent 03 POST /scores/evaluate.

Uses HS256 JWT token (60-second expiry) for inter-service auth.
Returns None on any error — never raises.

Fast path: GET /scores/{ticker} returns the cached score from Agent 03's DB.
Only falls through to the slow path (classify + evaluate) if the score is
missing or older than score_cache_ttl seconds.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _make_token() -> str:
    """Generate a short-lived HS256 JWT for inter-service calls."""
    secret = settings.jwt_secret
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "agent-07", "exp": int(time.time()) + 60}).encode()
    ).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{signing_input}.{sig}"


async def _classify(ticker: str) -> Optional[str]:
    """
    Call Agent 04 to get asset_class for ticker.
    Returns the asset_class string, or None on any error.
    """
    url = f"{settings.asset_classification_url.rstrip('/')}/classify"
    try:
        token = _make_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=settings.asset_classification_timeout) as client:
            resp = await client.post(url, json={"ticker": ticker}, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("asset_class")
        logger.warning("Agent 04 returned HTTP %d for %s", resp.status_code, ticker)
        return None
    except Exception as exc:
        logger.warning("Agent 04 classify failed for %s: %s", ticker, exc)
        return None


async def score_ticker(ticker: str) -> Optional[dict]:
    """
    Return a score dict for ticker.

    Fast path — GET /scores/{ticker}:
      If Agent 03 already has a score younger than score_cache_ttl seconds,
      return it immediately (single DB read, no FMP / market-data calls).

    Slow path — classify + POST /scores/evaluate:
      Used only when there is no cached score or it is stale.
    """
    # ── Fast path: cached score ───────────────────────────────────────────
    url_get = f"{settings.income_scoring_url.rstrip('/')}/scores/{ticker.upper()}"
    try:
        token = _make_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url_get, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            data = resp.json()
            scored_at_raw = data.get("scored_at")
            if scored_at_raw:
                scored_at = datetime.fromisoformat(scored_at_raw.replace("Z", "+00:00"))
                age_secs = (datetime.now(timezone.utc) - scored_at).total_seconds()
                if age_secs < settings.score_cache_ttl:
                    logger.debug("Score cache hit for %s (age %.0fs)", ticker, age_secs)
                    return data
                logger.debug("Score cache stale for %s (age %.0fs)", ticker, age_secs)
    except Exception as exc:
        logger.debug("Score cache GET failed for %s: %s", ticker, exc)

    # ── Slow path: classify → evaluate ───────────────────────────────────
    asset_class = await _classify(ticker)
    if asset_class is None:
        logger.warning("Could not classify %s via Agent 04, skipping score", ticker)
        return None

    url_post = f"{settings.income_scoring_url.rstrip('/')}/scores/evaluate"
    try:
        token = _make_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=settings.income_scoring_timeout) as client:
            resp = await client.post(
                url_post,
                json={"ticker": ticker, "asset_class": asset_class, "gate_data": {}},
                headers=headers,
            )
        if resp.status_code != 200:
            logger.warning("Agent 03 returned HTTP %d for %s", resp.status_code, ticker)
            return None
        return resp.json()
    except httpx.TimeoutException:
        logger.warning("Agent 03 timed out for %s", ticker)
        return None
    except Exception as exc:
        logger.warning("Agent 03 call failed for %s: %s", ticker, exc)
        return None
