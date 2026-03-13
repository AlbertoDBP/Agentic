"""
Agent 02 — Newsletter Ingestion Service
Alignment Client: calls Agent 03 POST /scores/evaluate to compute platform alignment.

Uses HS256 JWT token (60-second expiry) for inter-service auth.
Returns None on any error — never raises.
Synchronous — called from Prefect tasks (sync context).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
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
        json.dumps({"sub": "agent-02", "exp": int(time.time()) + 60}).encode()
    ).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{signing_input}.{sig}"


def score_ticker_sync(ticker: str) -> Optional[dict]:
    """
    Call Agent 03 POST /scores/evaluate for a single ticker (synchronous).
    Returns the score dict on success, None on any error.
    """
    url = f"{settings.income_scoring_url.rstrip('/')}/scores/evaluate"
    try:
        token = _make_token()
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=settings.income_scoring_timeout) as client:
            resp = client.post(url, json={"ticker": ticker}, headers=headers)
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


def _derive_alignment(sentiment_score: Optional[float], total_score: float) -> str:
    """
    Determine platform_alignment label from analyst sentiment and Agent 03 score.

    Alignment rules:
      BULLISH (sentiment > +0.20):
        score ≥ 70 → Aligned
        score < 70 → Vetoed  (platform cannot support a bullish stance below 70)
      BEARISH (sentiment < -0.20):
        score ≤ 55 → Aligned  (both agree: avoid)
        score ≥ 70 → Divergent (platform bullish, analyst bearish)
        55 < score < 70 → Partial
      NEUTRAL (±0.20):
        any score → Partial
    """
    s = float(sentiment_score) if sentiment_score is not None else 0.0
    score = float(total_score)

    if s > 0.20:          # BULLISH
        return "Aligned" if score >= 70 else "Vetoed"
    elif s < -0.20:       # BEARISH
        if score >= 70:
            return "Divergent"
        elif score >= 55:
            return "Partial"
        return "Aligned"
    else:                 # NEUTRAL
        return "Partial"
