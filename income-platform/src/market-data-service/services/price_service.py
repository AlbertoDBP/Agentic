"""Price service — cache → DB → Alpha Vantage orchestration."""
import logging
from datetime import datetime, timezone
from typing import Optional

from cache import CacheManager
from fetchers.alpha_vantage import AlphaVantageClient
from repositories.price_repository import PriceRepository

logger = logging.getLogger(__name__)


class PriceService:
    """Orchestrates the cache-first, DB-fallback, API-last price retrieval chain."""

    def __init__(
        self,
        price_repo: PriceRepository,
        cache_manager: CacheManager,
        av_api_key: str,
        cache_ttl: int = 300,
        av_calls_per_minute: int = 5,
    ):
        self.price_repo = price_repo
        self.cache = cache_manager
        self.av_api_key = av_api_key
        self.cache_ttl = cache_ttl
        self.av_calls_per_minute = av_calls_per_minute

    async def get_current_price(self, ticker: str) -> dict:
        """
        Return current price data for ticker.

        Strategy (in order):
        1. Redis cache  — fastest, 5-minute TTL
        2. Database     — most-recent row from market_data_daily
        3. Alpha Vantage API — fetches and then persists to DB + cache

        Always returns a dict matching the PriceData Pydantic model.
        DB/cache failures are logged and allow fall-through to the next layer.
        """
        ticker = ticker.upper()
        cache_key = f"price:current:{ticker}"

        # 1. Cache check
        if self.cache:
            try:
                cached = await self.cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {ticker}")
                    return {**cached, "cached": True}
            except Exception as e:
                logger.warning(f"Cache read error for {ticker}: {e}")

        # 2. Database check
        if self.price_repo:
            try:
                row = await self.price_repo.get_latest_price(ticker)
                if row:
                    logger.info(f"✅ DB hit for {ticker} (trade_date={row.trade_date})")
                    price_data = self._row_to_dict(ticker, row)
                    # Warm the cache so the next request is served from Redis
                    if self.cache:
                        try:
                            await self.cache.set(cache_key, price_data, ttl=self.cache_ttl)
                        except Exception as e:
                            logger.warning(f"Cache write error after DB hit for {ticker}: {e}")
                    return {**price_data, "cached": False}
            except Exception as e:
                logger.warning(f"DB read error for {ticker}: {e}")

        # 3. Alpha Vantage API fetch
        logger.info(f"📡 Fetching {ticker} from Alpha Vantage...")
        async with AlphaVantageClient(
            api_key=self.av_api_key,
            calls_per_minute=self.av_calls_per_minute,
        ) as client:
            prices = await client.get_daily_prices(ticker, outputsize="compact")

        if not prices:
            raise ValueError(f"No data found for ticker {ticker}")

        latest = prices[0]
        change = 0.0
        change_percent = 0.0
        if len(prices) > 1:
            prev_close = prices[1]["close"]
            change = latest["close"] - prev_close
            change_percent = (change / prev_close) * 100

        price_data = {
            "ticker": ticker,
            "price": latest["close"],
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "volume": latest["volume"],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source": "alpha_vantage",
            "cached": False,
        }

        # Persist to DB (best-effort — don't fail the request if DB is down)
        if self.price_repo:
            try:
                await self.price_repo.save_price(ticker, latest["date"], latest)
                logger.info(f"✅ Persisted {ticker} {latest['date']} to DB")
            except Exception as e:
                logger.error(f"❌ DB write error for {ticker}: {e}")

        # Warm cache
        if self.cache:
            try:
                await self.cache.set(cache_key, price_data, ttl=self.cache_ttl)
            except Exception as e:
                logger.warning(f"Cache write error for {ticker}: {e}")

        logger.info(f"✅ Fetched {ticker}: ${price_data['price']}")
        return price_data

    @staticmethod
    def _row_to_dict(ticker: str, row) -> dict:
        """Convert a MarketDataDaily ORM row to a PriceData-compatible dict."""
        return {
            "ticker": ticker,
            "price": float(row.close_price),
            "change": 0.0,           # Not stored; only available from live API
            "change_percent": 0.0,
            "volume": row.volume or 0,
            "timestamp": row.created_at.isoformat() if row.created_at else datetime.now(tz=timezone.utc).isoformat(),
            "source": "database",
            "cached": False,
        }
