"""Finnhub REST API client — credit rating via /stock/metric.

Usage:
    async with FinnhubClient(api_key=settings.finnhub_api_key) as client:
        rating = await client.get_credit_rating("AAPL")

Returns the credit rating string (e.g. "BBB+") or None if unavailable.
Never raises — all errors are logged and degraded to None.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"
_TIMEOUT = aiohttp.ClientTimeout(total=15)
# Finnhub free tier: 60 requests/minute → 1 s minimum interval
_MIN_INTERVAL = 1.0


class FinnhubClient:
    """Finnhub REST API client for credit rating data.

    Rate limit: 60 requests/minute (1 s minimum interval).
    The class-level ``_last_request_time`` is shared across all instances,
    identical to the pattern used by PolygonClient and FMPClient.
    """

    # Class-level rate-limit timestamp, shared across all instances
    _last_request_time: Optional[datetime] = None

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Async context-manager
    # ------------------------------------------------------------------

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_credit_rating(self, symbol: str) -> Optional[str]:
        """Return the credit rating string for *symbol*, or None.

        Calls GET /stock/metric?symbol={symbol}&metric=all&token={api_key}.
        Extracts response["metric"]["creditRating"].

        Never raises — all errors are caught, logged, and returned as None.
        """
        if not self.api_key:
            logger.debug("FinnhubClient: no API key configured, skipping credit rating")
            return None

        symbol = symbol.upper()
        try:
            await self._rate_limit()
            data = await self._get("/stock/metric", params={"symbol": symbol, "metric": "all"})
            rating = (data.get("metric") or {}).get("creditRating")
            if rating:
                logger.info(f"✅ Finnhub credit rating for {symbol}: {rating}")
                return str(rating).strip() or None
            logger.debug(f"Finnhub: no creditRating in metric response for {symbol}")
            return None
        except Exception as e:
            logger.warning(f"FinnhubClient.get_credit_rating({symbol}) failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Authenticated GET — token passed as query param."""
        if not self.session:
            raise RuntimeError("FinnhubClient must be used as an async context manager")

        all_params = {"token": self.api_key, **(params or {})}
        url = f"{_BASE_URL}{path}"
        async with self.session.get(url, params=all_params, timeout=_TIMEOUT) as resp:
            if resp.status == 429:
                logger.warning("Finnhub rate limit hit (HTTP 429)")
                return {}
            if resp.status in (401, 403):
                logger.warning(f"Finnhub auth error HTTP {resp.status}")
                return {}
            resp.raise_for_status()
            return await resp.json()

    async def _rate_limit(self) -> None:
        """Enforce the per-minute rate limit using a class-level shared timestamp."""
        if FinnhubClient._last_request_time is not None:
            elapsed = (datetime.now() - FinnhubClient._last_request_time).total_seconds()
            if elapsed < _MIN_INTERVAL:
                wait = _MIN_INTERVAL - elapsed
                logger.debug(f"Finnhub rate limit: waiting {wait:.3f}s")
                await asyncio.sleep(wait)
        FinnhubClient._last_request_time = datetime.now()
