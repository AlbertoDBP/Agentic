"""
Agent 03 — Income Scoring Service
Data Client: async HTTP client for Agent 01 (Market Data Service, port 8001).

All methods use httpx.AsyncClient with timeout and base URL from settings.
On any connection error or non-200 response: log warning and return {} or [].
"""
import logging
from typing import Any, Optional

import asyncpg
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _build_dsn() -> tuple[str, bool]:
    """Return (clean_dsn, ssl_required). Strip ?sslmode=* from URL; detect ssl from it."""
    url = settings.database_url
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    ssl_required = "sslmode=require" in url
    if "?" in url:
        url = url.split("?")[0]
    return url, ssl_required


async def init_pool() -> None:
    global _pool
    dsn, ssl_required = _build_dsn()
    _pool = await asyncpg.create_pool(
        dsn,
        ssl="require" if ssl_required else None,
        min_size=2,
        max_size=10,
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


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

    async def get_features(self, ticker: str) -> dict:
        """Query platform_shared.features_historical for the latest feature row.

        Returns dict with keys: yield_trailing_12m, div_cagr_5y, chowder_number,
        yield_5yr_avg, credit_rating, credit_quality_proxy.
        Returns empty dict on any error — never raises.
        """
        try:
            async with _pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT yield_trailing_12m, div_cagr_5y, chowder_number,
                           yield_5yr_avg, credit_rating, credit_quality_proxy
                    FROM platform_shared.features_historical
                    WHERE symbol = $1
                    ORDER BY as_of_date DESC
                    LIMIT 1
                    """,
                    ticker,
                )
            return dict(row) if row is not None else {}
        except Exception as e:
            logger.warning("get_features failed for %s: %s", ticker, e)
            return {}

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict = None) -> Any:
        url = f"{self.base_url}{path}"
        headers = {}
        if settings.service_token:
            headers["Authorization"] = f"Bearer {settings.service_token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params, headers=headers)
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
