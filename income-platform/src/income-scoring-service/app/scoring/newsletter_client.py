"""
Agent 03 — Income Scoring Service
Newsletter Client: Fetches analyst signal data from Agent 02.

Calls: GET {newsletter_service_url}/signal/{ticker}

Returns None on any failure — signal layer is non-blocking and must degrade
gracefully when Agent 02 is unavailable (timeout, 404, network error, disabled).
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch_signal(ticker: str) -> dict | None:
    """
    Call Agent 02 GET /signal/{ticker}.

    Returns:
        Parsed response dict on success (contains signal_strength, consensus,
        recommendation keys — see Agent 02 AnalystSignalResponse schema).
        None if:
          - newsletter_service_enabled is False
          - Agent 02 returns 404 (no signal for this ticker)
          - Any network/HTTP error (timeout, connection refused, etc.)

    Never raises — signal layer must degrade gracefully.
    """
    if not settings.newsletter_service_enabled:
        logger.debug("Newsletter service disabled — skipping signal fetch for %s", ticker)
        return None

    url = f"{settings.newsletter_service_url}/signal/{ticker}"
    try:
        async with httpx.AsyncClient(timeout=float(settings.newsletter_timeout)) as client:
            resp = await client.get(url)

        if resp.status_code == 404:
            logger.debug("No signal available from Agent 02 for %s (404)", ticker)
            return None

        resp.raise_for_status()
        return resp.json()

    except httpx.TimeoutException:
        logger.warning("Agent 02 signal fetch timed out for %s (timeout=%ss)", ticker, settings.newsletter_timeout)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Agent 02 signal fetch HTTP error for %s: %s", ticker, exc)
        return None
    except Exception as exc:
        logger.warning("Agent 02 signal fetch failed for %s: %s", ticker, exc)
        return None
