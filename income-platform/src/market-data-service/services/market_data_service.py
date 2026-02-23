"""Market Data Service — orchestrates price, dividend, fundamental, and ETF data.

Data is served via a ProviderRouter that fans out to Polygon → FMP → yfinance
depending on the request type.  Historical prices are additionally persisted
to and read from the price_history DB table for range queries.

Lifecycle
---------
This service owns the ProviderRouter, which manages aiohttp sessions for
Polygon and FMP.  Call ``await service.connect()`` during application startup
and ``await service.disconnect()`` during shutdown — mirroring the pattern
used by DatabaseManager.

    service = MarketDataService(repo, cache, polygon_api_key="...", fmp_api_key="...")
    await service.connect()
    ...
    await service.disconnect()
"""
import logging
import statistics as _stats
from datetime import date
from typing import List, Optional

from cache import CacheManager
from fetchers.fmp_client import FMPClient
from fetchers.polygon_client import PolygonClient
from fetchers.provider_router import ProviderRouter
from fetchers.yfinance_client import YFinanceClient
from repositories.price_history_repository import PriceHistoryRepository

logger = logging.getLogger(__name__)

# Service-level TTL for date-range history cache entries.
# Individual provider responses are cached separately inside each provider.
_TTL_HISTORY = 6 * 60 * 60   # 6 hours


class MarketDataService:
    """Orchestrates all market data requests through ProviderRouter with DB persistence.

    Args:
        price_history_repo: Repository for the price_history table (may be None
                            when the DB is unavailable).
        cache_manager:      Redis cache (may be None).
        polygon_api_key:    Polygon.io API key.  Empty string disables Polygon.
        fmp_api_key:        Financial Modeling Prep API key.  Empty string
                            disables FMP.
    """

    def __init__(
        self,
        price_history_repo: Optional[PriceHistoryRepository],
        cache_manager: Optional[CacheManager],
        polygon_api_key: str = "",
        fmp_api_key: str = "",
    ):
        self.repo  = price_history_repo
        self.cache = cache_manager

        # Build provider instances (sessions opened in connect())
        polygon  = PolygonClient(api_key=polygon_api_key,  cache=cache_manager) if polygon_api_key  else None
        fmp      = FMPClient(api_key=fmp_api_key,          cache=cache_manager) if fmp_api_key      else None
        yfinance = YFinanceClient()

        self._router: ProviderRouter = ProviderRouter(
            polygon=polygon,
            fmp=fmp,
            yfinance=yfinance,
            cache=cache_manager,
        )
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open HTTP sessions for all configured providers."""
        await self._router.__aenter__()
        self._connected = True
        logger.info("✅ MarketDataService providers connected")

    async def disconnect(self) -> None:
        """Close HTTP sessions for all configured providers."""
        if self._connected:
            await self._router.__aexit__(None, None, None)
            self._connected = False
            logger.info("MarketDataService providers disconnected")

    # ------------------------------------------------------------------
    # Historical prices (cache → DB → router)
    # ------------------------------------------------------------------

    async def get_historical_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """Return OHLCV records for *symbol* in [start_date, end_date].

        Strategy (in order):
        1. Service-level Redis cache — key ``price:history:{symbol}:{start}:{end}``
        2. price_history DB table via PriceHistoryRepository
        3. ProviderRouter.get_daily_prices → persists ALL returned rows to DB,
           then filters to the requested date range

        Returns list of dicts: date, open, high, low, close, volume,
        adjusted_close — matching the HistoricalPrice Pydantic model.
        All 'date' values are ISO-format strings for JSON serialisability.
        """
        symbol = symbol.upper()
        cache_key = f"price:history:{symbol}:{start_date}:{end_date}"

        # 1. Service-level cache
        if self.cache:
            try:
                cached = await self.cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} history [{start_date}–{end_date}]")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # 2. DB
        if self.repo:
            try:
                rows = await self.repo.get_price_range(symbol, start_date, end_date)
                if rows:
                    logger.info(
                        f"✅ DB hit for {symbol} [{start_date}–{end_date}]: {len(rows)} rows"
                    )
                    result = [_row_to_dict(r) for r in rows]
                    await self._cache_history(cache_key, result)
                    return result
            except Exception as e:
                logger.warning(f"DB read error for {symbol} history: {e}")

        # 3. Provider fetch — use compact (recent 100 days) for most requests;
        #    for ranges that fall entirely within the last 2 years the router
        #    will serve them from Polygon or FMP if compact misses.
        days_since_end = (date.today() - end_date).days
        if days_since_end > 730:
            logger.info(
                f"📅 {symbol} range ends {days_since_end}d ago — beyond 2-year provider "
                "window; returning empty (use refresh_historical_prices to backfill DB)"
            )
            return []

        outputsize = "compact" if days_since_end <= 140 else "full"
        logger.info(f"📡 Fetching {symbol} history via router ({outputsize})...")

        try:
            prices = await self._router.get_daily_prices(symbol, outputsize=outputsize)
        except Exception as e:
            logger.error(f"❌ Router failed to fetch history for {symbol}: {e}")
            return []

        if not prices:
            logger.warning(f"No historical data returned for {symbol}")
            return []

        # Persist ALL fetched records to DB (best-effort)
        if self.repo:
            try:
                normalised = _normalise_dates(prices)
                count = await self.repo.bulk_save_prices(symbol, normalised)
                logger.info(f"✅ Persisted {count} records for {symbol}")
            except Exception as e:
                logger.error(f"❌ DB write error for {symbol} history: {e}")

        result = _filter_by_range(prices, start_date, end_date)
        await self._cache_history(cache_key, result)
        return result

    async def refresh_historical_prices(
        self,
        symbol: str,
        full_history: bool = False,
    ) -> int:
        """Force-fetch from the provider chain and upsert to the price_history table.

        Always bypasses cache and DB read — goes directly to the router.

        Args:
            symbol:       Ticker symbol.
            full_history: True  → outputsize='full' (up to 2 years via Polygon/FMP).
                          False → outputsize='compact' (last ~100 trading days).

        Returns:
            Number of rows upserted into price_history.
        """
        symbol     = symbol.upper()
        outputsize = "full" if full_history else "compact"
        logger.info(f"🔄 Refreshing {symbol} history via router ({outputsize})...")

        try:
            prices = await self._router.get_daily_prices(symbol, outputsize=outputsize)
        except Exception as e:
            logger.error(f"❌ Router failed to refresh {symbol}: {e}")
            raise ValueError(str(e)) from e

        if not prices:
            logger.warning(f"No data returned for {symbol} refresh")
            return 0

        if not self.repo:
            logger.error("No DB repository available — cannot persist refresh data")
            return 0

        normalised = _normalise_dates(prices)
        count = await self.repo.bulk_save_prices(symbol, normalised)
        logger.info(f"✅ Refreshed {symbol}: {count} rows upserted ({outputsize})")
        return count

    # ------------------------------------------------------------------
    # Pass-through methods (router handles caching internally)
    # ------------------------------------------------------------------

    async def get_dividend_history(self, symbol: str) -> list[dict]:
        """Return dividend payment history for *symbol* via FMP → yfinance.

        Delegates directly to ProviderRouter.get_dividend_history.
        Caching is handled inside FMPClient (4-hour Redis TTL).
        """
        symbol = symbol.upper()
        logger.info(f"📡 Fetching dividend history for {symbol} via router...")
        return await self._router.get_dividend_history(symbol)

    async def get_fundamentals(self, symbol: str) -> dict:
        """Return key fundamental metrics for *symbol* via FMP → yfinance.

        Delegates directly to ProviderRouter.get_fundamentals.
        Caching is handled inside FMPClient (24-hour Redis TTL).
        """
        symbol = symbol.upper()
        logger.info(f"📡 Fetching fundamentals for {symbol} via router...")
        return await self._router.get_fundamentals(symbol)

    async def get_etf_holdings(self, symbol: str) -> dict:
        """Return ETF metadata and top holdings for *symbol* via FMP → yfinance.

        Delegates directly to ProviderRouter.get_etf_holdings.
        Caching is handled inside FMPClient (24-hour Redis TTL).
        """
        symbol = symbol.upper()
        logger.info(f"📡 Fetching ETF holdings for {symbol} via router...")
        return await self._router.get_etf_holdings(symbol)

    async def get_price_statistics(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Calculate price statistics from the price_history DB table.

        Reads from the DB only — no API fallback. Call
        refresh_historical_prices() first if the DB is empty for this symbol.

        Returns dict with:
            symbol, start_date, end_date, count,
            min_close, max_close, avg_close, volatility (std dev of daily closes).
        """
        symbol = symbol.upper()
        base = {
            "symbol":     symbol,
            "start_date": start_date.isoformat(),
            "end_date":   end_date.isoformat(),
        }

        if not self.repo:
            return {**base, "count": 0, "error": "DB not available"}

        try:
            rows = await self.repo.get_price_range(symbol, start_date, end_date)
        except Exception as e:
            logger.error(f"❌ DB error fetching stats for {symbol}: {e}")
            return {**base, "count": 0, "error": str(e)}

        if not rows:
            return {
                **base,
                "count":      0,
                "min_close":  None,
                "max_close":  None,
                "avg_close":  None,
                "volatility": None,
            }

        closes = [float(r.close_price) for r in rows if r.close_price is not None]
        count  = len(closes)
        return {
            **base,
            "count":      count,
            "min_close":  round(min(closes), 4),
            "max_close":  round(max(closes), 4),
            "avg_close":  round(sum(closes) / count, 4),
            "volatility": round(_stats.stdev(closes), 4) if count > 1 else 0.0,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _cache_history(self, cache_key: str, data: list) -> None:
        """Write a date-range result list to the service-level Redis cache."""
        if not self.cache or not data:
            return
        try:
            await self.cache.set(cache_key, data, ttl=_TTL_HISTORY)
        except Exception as e:
            logger.warning(f"Cache write error for {cache_key}: {e}")


# ------------------------------------------------------------------
# Module-level helpers (unchanged from original)
# ------------------------------------------------------------------

def _row_to_dict(row) -> dict:
    """Convert a PriceHistory ORM row to a HistoricalPrice-compatible dict."""
    return {
        "date":           row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date),
        "open":           float(row.open_price)     if row.open_price     is not None else None,
        "high":           float(row.high_price)     if row.high_price     is not None else None,
        "low":            float(row.low_price)      if row.low_price      is not None else None,
        "close":          float(row.close_price)    if row.close_price    is not None else None,
        "volume":         int(row.volume)           if row.volume         is not None else 0,
        "adjusted_close": float(row.adjusted_close) if row.adjusted_close is not None else None,
    }


def _normalise_dates(prices: List[dict]) -> List[dict]:
    """Ensure every record's 'date' field is a ``date`` object (not a string).

    Provider clients may return ISO strings (from Redis cache hits) or date
    objects (from live API calls).  The DB repository requires date objects.
    """
    result = []
    for p in prices:
        d = p.get("date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        result.append({**p, "date": d})
    return result


def _filter_by_range(prices: List[dict], start_date: date, end_date: date) -> List[dict]:
    """Return records whose date falls in [start_date, end_date], sorted ascending.

    Handles 'date' as either a ``date`` object or an ISO-format string.
    Output 'date' values are ISO strings for JSON serialisability.
    """
    result = []
    for p in prices:
        d = p.get("date")
        if d is None:
            continue
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if start_date <= d <= end_date:
            result.append({**p, "date": d.isoformat()})
    result.sort(key=lambda x: x["date"])
    return result
