"""Market Data Service — historical price orchestration (cache → DB → Alpha Vantage)."""
import logging
import statistics as _stats
from datetime import date
from typing import List, Optional

from cache import CacheManager
from fetchers.alpha_vantage import AlphaVantageClient
from repositories.price_history_repository import PriceHistoryRepository

logger = logging.getLogger(__name__)

# 6-hour TTL for historical data — changes rarely compared to current quotes
_TTL_HISTORY = 6 * 60 * 60


class MarketDataService:
    """Orchestrates historical price retrieval: cache → price_history DB → Alpha Vantage."""

    def __init__(
        self,
        price_history_repo: PriceHistoryRepository,
        cache_manager: CacheManager,
        av_api_key: str,
        av_calls_per_minute: int = 5,
    ):
        self.repo = price_history_repo
        self.cache = cache_manager
        self.av_api_key = av_api_key
        self.av_calls_per_minute = av_calls_per_minute

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_historical_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """Return OHLCV records for symbol in [start_date, end_date].

        Strategy (in order):
        1. Cache — key ``price:history:{symbol}:{start_date}:{end_date}``
        2. DB    — price_history table via PriceHistoryRepository
        3. Alpha Vantage — fetches adjusted daily data, persists to DB + cache

        Returns list of dicts with keys: date, open, high, low, close,
        volume, adjusted_close — matching the HistoricalPrice Pydantic model.
        All 'date' values are ISO-format strings for JSON serialisability.
        """
        symbol = symbol.upper()
        cache_key = f"price:history:{symbol}:{start_date}:{end_date}"

        # 1. Cache check
        if self.cache:
            try:
                cached = await self.cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} history [{start_date}–{end_date}]")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # 2. DB check
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

        # 3. Alpha Vantage fetch (TIME_SERIES_DAILY compact — only FREE tier option)
        # compact covers ~100 trading days (~140 calendar days).
        # Requests for ranges older than that return empty here; the DB is the
        # only source for data beyond the compact window.
        days_since_end = (date.today() - end_date).days
        if days_since_end > 140:
            logger.info(
                f"📅 {symbol} range ends {days_since_end}d ago — outside compact window, "
                "DB-only lookup (no AV fetch)"
            )
            return []

        logger.info(f"📡 Fetching {symbol} history from Alpha Vantage (compact)...")
        async with AlphaVantageClient(
            api_key=self.av_api_key,
            calls_per_minute=self.av_calls_per_minute,
        ) as client:
            prices = await client.get_daily_prices(symbol, outputsize="compact")

        if not prices:
            logger.warning(f"No historical data returned for {symbol}")
            return []

        # Persist ALL fetched records to DB (best-effort, normalise dates first)
        if self.repo:
            try:
                normalised = _normalise_dates(prices)
                count = await self.repo.bulk_save_prices(symbol, normalised)
                logger.info(f"✅ Persisted {count} records for {symbol}")
            except Exception as e:
                logger.error(f"❌ DB write error for {symbol} history: {e}")

        # Filter to the requested range and cache
        result = _filter_by_range(prices, start_date, end_date)
        await self._cache_history(cache_key, result)
        return result

    async def refresh_historical_prices(
        self,
        symbol: str,
        full_history: bool = False,
    ) -> int:
        """Force-fetch from Alpha Vantage and upsert to the price_history table.

        Always bypasses cache and DB read — goes directly to the API.

        Args:
            symbol:       Ticker symbol.
            full_history: True  → request up to 20 years (outputsize='full').
                          False → last ~100 trading days (outputsize='compact').

        Returns:
            Number of rows upserted into price_history.
        """
        symbol = symbol.upper()
        # TIME_SERIES_DAILY full outputsize is a premium feature; free tier is compact only.
        outputsize = "compact"
        logger.info(f"🔄 Refreshing {symbol} history from Alpha Vantage (compact)...")

        async with AlphaVantageClient(
            api_key=self.av_api_key,
            calls_per_minute=self.av_calls_per_minute,
        ) as client:
            prices = await client.get_daily_prices(symbol, outputsize=outputsize)

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

    async def get_price_statistics(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Calculate price statistics from stored price_history data.

        Reads from the DB only — no API fallback. If no data is present,
        call refresh_historical_prices() first.

        Returns dict with:
            symbol, start_date, end_date, count,
            min_close, max_close, avg_close, volatility (std dev of daily closes).
        """
        symbol = symbol.upper()
        base = {
            "symbol": symbol,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
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
                "count": 0,
                "min_close": None,
                "max_close": None,
                "avg_close": None,
                "volatility": None,
            }

        closes = [float(r.close_price) for r in rows if r.close_price is not None]
        count = len(closes)

        return {
            **base,
            "count": count,
            "min_close": round(min(closes), 4),
            "max_close": round(max(closes), 4),
            "avg_close": round(sum(closes) / count, 4),
            "volatility": round(_stats.stdev(closes), 4) if count > 1 else 0.0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _cache_history(self, cache_key: str, data: list) -> None:
        """Write history list to Redis cache (best-effort)."""
        if not self.cache or not data:
            return
        try:
            await self.cache.set(cache_key, data, ttl=_TTL_HISTORY)
        except Exception as e:
            logger.warning(f"Cache write error for {cache_key}: {e}")


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _row_to_dict(row) -> dict:
    """Convert a PriceHistory ORM row to a HistoricalPrice-compatible dict."""
    return {
        "date": row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date),
        "open": float(row.open_price) if row.open_price is not None else None,
        "high": float(row.high_price) if row.high_price is not None else None,
        "low": float(row.low_price) if row.low_price is not None else None,
        "close": float(row.close_price) if row.close_price is not None else None,
        "volume": int(row.volume) if row.volume is not None else 0,
        "adjusted_close": float(row.adjusted_close) if row.adjusted_close is not None else None,
    }


def _normalise_dates(prices: List[dict]) -> List[dict]:
    """Ensure every record's 'date' field is a date object (not a string).

    fetch_daily_adjusted returns date objects on a fresh API call but ISO strings
    when the result comes from the Redis cache. The DB repository requires date objects.
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

    Handles 'date' field as either a date object or an ISO-format string.
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
