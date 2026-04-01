"""Async HTTP fetcher: calls Agents 02, 03, 04, 05 concurrently.

All calls use HS256 JWT auth with sub='agent-12'.
Score lookup uses DB-first strategy: reads platform_shared.income_scores before
calling Agent 03 live, so proposals always reflect the latest scored data.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt
from sqlalchemy import text

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
# Use cached score if it was computed within this window
_SCORE_CACHE_TTL_HOURS = 24


def _fetch_score_from_db(ticker: str) -> Optional[dict]:
    """Read the most recent income_score for ticker from platform_shared.

    Returns a dict compatible with the Agent 03 /scores/evaluate response,
    or None if no score exists or it is older than _SCORE_CACHE_TTL_HOURS.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_SCORE_CACHE_TTL_HOURS)
    query = text("""
        SELECT
            i.total_score,
            i.grade,
            i.recommendation,
            i.nav_erosion_penalty,
            i.factor_details,
            i.quality_gate_status,
            i.scored_at,
            COALESCE(sec.asset_type, i.asset_class) AS asset_class
        FROM platform_shared.income_scores i
        LEFT JOIN platform_shared.securities sec ON sec.symbol = i.ticker
        WHERE i.ticker = :ticker
          AND i.scored_at >= :cutoff
        ORDER BY i.scored_at DESC
        LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {"ticker": ticker, "cutoff": cutoff}).fetchone()
        if row is None:
            return None
        return {
            "total_score":         row.total_score,
            "grade":               row.grade,
            "recommendation":      row.recommendation,
            "nav_erosion_penalty": row.nav_erosion_penalty,
            "factor_details":      row.factor_details,
            "quality_gate_status": row.quality_gate_status,
            "asset_class":         row.asset_class,
        }
    except Exception as exc:
        logger.warning("DB score lookup failed for %s: %s", ticker, exc)
        return None


def _make_token() -> str:
    """Generate a short-lived HS256 JWT for service-to-service calls."""
    secret = os.environ.get("JWT_SECRET", settings.jwt_secret)
    payload = {
        "sub": "agent-12",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,  # 5 min TTL
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_make_token()}"}


# ---------------------------------------------------------------------------
# Individual fetchers
# ---------------------------------------------------------------------------

async def fetch_agent02_signal(ticker: str) -> dict:
    """GET {agent02_url}/signal/{ticker} → AnalystSignalResponse dict.

    Raises httpx.HTTPError or httpx.TimeoutException on failure.
    A 404 or non-2xx response raises httpx.HTTPStatusError.
    """
    url = f"{settings.agent02_url}/signal/{ticker}"
    async with httpx.AsyncClient(timeout=settings.agent02_timeout) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()


async def fetch_agent03_score(ticker: str) -> Optional[dict]:
    """Return a score dict for ticker using DB-first strategy.

    1. Check platform_shared.income_scores for a score < 24 h old.
       If found, return it immediately (avoids live re-evaluation on every proposal).
    2. Fall back to POST {agent03_url}/scores/evaluate for stale / missing scores.
    Returns None on failure (non-fatal per spec).
    """
    # DB-first: avoids redundant scoring calls and returns the canonical cached data
    cached = await asyncio.to_thread(_fetch_score_from_db, ticker)
    if cached is not None:
        logger.debug("Score cache hit for %s (scored_at in last %dh)", ticker, _SCORE_CACHE_TTL_HOURS)
        return cached

    logger.info("No fresh score in DB for %s — calling Agent 03 live", ticker)
    url = f"{settings.agent03_url}/scores/evaluate"
    try:
        async with httpx.AsyncClient(timeout=settings.agent03_timeout) as client:
            resp = await client.post(
                url, json={"ticker": ticker}, headers=_auth_headers()
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("Agent 03 call failed for %s: %s", ticker, exc)
        return None


async def fetch_agent04_entry_price(ticker: str, portfolio_id: Optional[str] = None) -> Optional[dict]:
    """POST {agent04_url}/entry-price/{ticker}.

    Returns None on failure; caller uses market price fallback.
    """
    url = f"{settings.agent04_url}/entry-price/{ticker}"
    params = {}
    if portfolio_id:
        params["portfolio_id"] = portfolio_id
    try:
        async with httpx.AsyncClient(timeout=settings.agent04_timeout) as client:
            resp = await client.post(url, params=params, headers=_auth_headers())
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("Agent 04 call failed for %s: %s", ticker, exc)
        return None


async def fetch_agent05_tax_placement(
    ticker: str, portfolio_id: Optional[str] = None
) -> Optional[dict]:
    """POST {agent05_url}/tax/placement body: {"ticker": ticker, "portfolio_id": portfolio_id}.

    Returns None on failure (non-fatal per spec).
    """
    url = f"{settings.agent05_url}/tax/placement"
    body: dict = {"ticker": ticker}
    if portfolio_id:
        body["portfolio_id"] = portfolio_id
    try:
        async with httpx.AsyncClient(timeout=settings.agent05_timeout) as client:
            resp = await client.post(url, json=body, headers=_auth_headers())
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("Agent 05 call failed for %s: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Concurrent fetch
# ---------------------------------------------------------------------------

async def fetch_all(
    ticker: str,
    portfolio_id: Optional[str] = None,
) -> tuple[dict, Optional[dict], Optional[dict], Optional[dict]]:
    """Fetch Agent 02 signal then concurrently fetch 03/04/05.

    Returns (signal, score, entry_price, tax_placement).
    Agent 02 is non-fatal — returns {} when no analyst signal exists (e.g. scanner-originated tickers).
    """
    try:
        signal = await fetch_agent02_signal(ticker)
    except Exception as exc:
        logger.warning("Agent 02 signal unavailable for %s (platform-only proposal): %s", ticker, exc)
        signal = {}

    # Agents 03/04/05 are non-fatal — run concurrently
    score, entry_price, tax = await asyncio.gather(
        fetch_agent03_score(ticker),
        fetch_agent04_entry_price(ticker, portfolio_id),
        fetch_agent05_tax_placement(ticker, portfolio_id),
        return_exceptions=False,
    )

    return signal, score, entry_price, tax
