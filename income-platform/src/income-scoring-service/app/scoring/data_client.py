"""
Agent 03 — Income Scoring Service
Data Client: async HTTP client for Agent 01 (Market Data Service, port 8001).

All methods use httpx.AsyncClient with timeout and base URL from settings.
On any connection error or non-200 response: log warning and return {} or [].
"""
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MarketDataClient:
    """Async HTTP client for the Market Data Service (Agent 01).

    All methods return the parsed JSON on success, or {} / [] on any error,
    so the caller never needs to handle connection failures explicitly.
    """

    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = (base_url or settings.market_data_service_url).rstrip("/")
        self.timeout = timeout or settings.market_data_timeout

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_fundamentals(self, ticker: str) -> dict:
        """GET /stocks/{ticker}/fundamentals

        Returns dict with pe_ratio, debt_to_equity, payout_ratio,
        free_cash_flow, market_cap, sector, earnings_growth, credit_rating.
        """
        return await self._get(f"/stocks/{ticker}/fundamentals")

    async def get_dividend_history(self, ticker: str) -> list:
        """GET /stocks/{ticker}/dividends

        Returns list of dividend records (ex_date, payment_date, amount,
        frequency, yield_pct). Unwraps the StockDividendResponse envelope.
        """
        result = await self._get(f"/stocks/{ticker}/dividends")
        if isinstance(result, dict):
            return result.get("dividends") or []
        return []

    async def get_history_stats(
        self, ticker: str, start_date: str, end_date: str
    ) -> dict:
        """GET /stocks/{ticker}/history/stats

        Returns dict with volatility, min_price, max_price, avg_price,
        price_change_pct, period_days.
        """
        return await self._get(
            f"/stocks/{ticker}/history/stats",
            params={"start_date": start_date, "end_date": end_date},
        )

    async def get_etf_data(self, ticker: str) -> dict:
        """GET /stocks/{ticker}/etf

        Returns dict with aum, expense_ratio, covered_call, top_holdings.
        """
        return await self._get(f"/stocks/{ticker}/etf")

    async def get_current_price(self, ticker: str) -> dict:
        """GET /stocks/{ticker}/price

        Returns dict with symbol, price, volume, timestamp, source.
        """
        return await self._get(f"/stocks/{ticker}/price")

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        "Market data API %s returned HTTP %s", url, resp.status_code
                    )
                    return {}
                return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("Market data connection error for %s: %s", url, e)
            return {}
        except Exception as e:
            logger.warning("Market data unexpected error for %s: %s", url, e)
            return {}
