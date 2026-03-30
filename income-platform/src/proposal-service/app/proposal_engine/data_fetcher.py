"""Async HTTP fetcher: calls Agents 02, 03, 04, 05 concurrently.

All calls use HS256 JWT auth with sub='agent-12'.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"


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
    """POST {agent03_url}/scores/evaluate body: {"ticker": ticker}.

    Returns None on failure (non-fatal per spec).
    """
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
