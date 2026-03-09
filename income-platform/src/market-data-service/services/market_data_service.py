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
from datetime import date, datetime, timedelta
from typing import List, Optional

from cache import CacheManager
from fetchers.finnhub_client import FinnhubClient
from fetchers.fmp_client import FMPClient
from fetchers.polygon_client import PolygonClient
from fetchers.provider_router import ProviderRouter
from fetchers.yfinance_client import YFinanceClient
from repositories.features_repository import FeaturesRepository, compute_credit_quality_proxy
from repositories.price_history_repository import PriceHistoryRepository
from repositories.securities_repository import SecuritiesRepository

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
        finnhub_api_key:    Finnhub API key.  Empty string disables Finnhub.
        securities_repo:    Repository for platform_shared.securities (may be None).
        features_repo:      Repository for platform_shared.features_historical (may be None).
    """

    def __init__(
        self,
        price_history_repo: Optional[PriceHistoryRepository],
        cache_manager: Optional[CacheManager],
        polygon_api_key: str = "",
        fmp_api_key: str = "",
        finnhub_api_key: str = "",
        securities_repo: Optional[SecuritiesRepository] = None,
        features_repo: Optional[FeaturesRepository] = None,
    ):
        self.repo  = price_history_repo
        self.cache = cache_manager
        self._securities_repo = securities_repo
        self._features_repo   = features_repo

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

        self._finnhub = FinnhubClient(api_key=finnhub_api_key) if finnhub_api_key else None
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open HTTP sessions for all configured providers."""
        await self._router.__aenter__()
        if self._finnhub:
            await self._finnhub.__aenter__()
        self._connected = True
        logger.info("✅ MarketDataService providers connected")

    async def disconnect(self) -> None:
        """Close HTTP sessions for all configured providers."""
        if self._connected:
            await self._router.__aexit__(None, None, None)
            if self._finnhub:
                await self._finnhub.__aexit__(None, None, None)
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
    # Credit rating (Finnhub)
    # ------------------------------------------------------------------

    async def get_credit_rating(self, symbol: str) -> Optional[str]:
        """Return the credit rating for *symbol* from Finnhub, or None."""
        if not self._finnhub:
            return None
        return await self._finnhub.get_credit_rating(symbol)

    # ------------------------------------------------------------------
    # Sync — enriches platform_shared tables for a single symbol
    # ------------------------------------------------------------------

    async def sync_symbol(self, symbol: str) -> dict:
        """Fetch, compute, and persist key features for *symbol*.

        Sequence:
          1. get_fundamentals()        → pe_ratio, payout_ratio, sector
          2. get_dividend_history()    → yield_trailing_12m, div_cagr_5y, yield_5yr_avg
          3. get_current_price()       → current price for yield normalisation
          4. get_credit_rating()       → credit_rating (Finnhub)
          5. SecuritiesRepository      → upsert (fire-and-forget)
          6. FeaturesRepository        → upsert (fire-and-forget)

        Returns a dict matching SyncResponse fields.
        """
        symbol = symbol.upper()
        missing_fields: List[str] = []
        providers_used: List[str] = []

        # 1. Fundamentals
        pe_ratio = payout_ratio = sector = None
        name = asset_type = exchange = currency = interest_coverage = None
        try:
            fundamentals = await self.get_fundamentals(symbol)
            pe_ratio       = fundamentals.get("pe_ratio")
            payout_ratio   = fundamentals.get("payout_ratio")
            sector         = fundamentals.get("sector")
            # These are not returned by current providers but accept them if present
            name              = fundamentals.get("name")
            asset_type        = fundamentals.get("asset_type")
            exchange          = fundamentals.get("exchange")
            currency          = fundamentals.get("currency")
            interest_coverage = fundamentals.get("interest_coverage")
            providers_used.append("fmp_fundamentals")
        except Exception as e:
            logger.warning(f"sync_symbol: fundamentals failed for {symbol}: {e}")

        if name is None:
            missing_fields.append("name")
        if interest_coverage is None:
            missing_fields.append("interest_coverage")
        if pe_ratio is None:
            missing_fields.append("pe_ratio")

        # 2. Dividend history + current price for yield calculations
        yield_trailing_12m = div_cagr_5y = yield_5yr_avg = None
        try:
            dividends = await self.get_dividend_history(symbol)
            if dividends:
                providers_used.append("fmp_dividends")
                # Get current price for yield normalisation (best-effort)
                current_price: Optional[float] = None
                try:
                    quote = await self._router.get_current_price(symbol)
                    current_price = float(quote["price"])
                except Exception:
                    pass

                yield_trailing_12m = _compute_yield_trailing_12m(dividends, current_price)
                div_cagr_5y        = _compute_div_cagr_5y(dividends)
                yield_5yr_avg      = _compute_yield_5yr_avg(dividends, current_price)
        except Exception as e:
            logger.warning(f"sync_symbol: dividend history failed for {symbol}: {e}")

        if yield_trailing_12m is None:
            missing_fields.append("yield_trailing_12m")
        if div_cagr_5y is None:
            missing_fields.append("div_cagr_5y")
        if yield_5yr_avg is None:
            missing_fields.append("yield_5yr_avg")

        # chowder_number = yield_trailing_12m + div_cagr_5y (both as %)
        chowder_number: Optional[float] = None
        if yield_trailing_12m is not None and div_cagr_5y is not None:
            chowder_number = round(yield_trailing_12m + div_cagr_5y, 4)

        # 3. Credit rating
        credit_rating = await self.get_credit_rating(symbol)
        if credit_rating:
            providers_used.append("finnhub")
        else:
            missing_fields.append("credit_rating")

        credit_quality_proxy = compute_credit_quality_proxy(credit_rating, interest_coverage)
        if credit_quality_proxy is None:
            missing_fields.append("credit_quality_proxy")

        as_of_date = date.today()

        # 4. Upsert security (fire-and-forget — errors logged inside repo)
        securities_updated = False
        if self._securities_repo:
            await self._securities_repo.upsert_security(
                symbol=symbol,
                name=name,
                asset_type=asset_type,
                sector=sector,
                exchange=exchange,
                currency=currency,
                expense_ratio=None,
                aum_millions=None,
            )
            securities_updated = True

        # 5. Upsert features (fire-and-forget — errors logged inside repo)
        features_updated = False
        if self._features_repo:
            # missing_feature_ratio: fraction of the 8 core features that are None
            _core = [
                yield_trailing_12m, yield_5yr_avg, div_cagr_5y,
                chowder_number, payout_ratio, pe_ratio,
                credit_rating, interest_coverage,
            ]
            missing_feature_ratio = round(
                sum(1 for v in _core if v is None) / len(_core), 4
            )
            await self._features_repo.upsert_features(
                symbol=symbol,
                as_of_date=as_of_date,
                yield_trailing_12m=yield_trailing_12m,
                yield_5yr_avg=yield_5yr_avg,
                div_cagr_5y=div_cagr_5y,
                chowder_number=chowder_number,
                payout_ratio=payout_ratio,
                pe_ratio=pe_ratio,
                credit_rating=credit_rating,
                credit_quality_proxy=credit_quality_proxy,
                interest_coverage=interest_coverage,
                advisor_coverage_count=None,
                missing_feature_ratio=missing_feature_ratio,
            )
            features_updated = True

        logger.info(
            f"✅ sync_symbol({symbol}): securities={securities_updated}, "
            f"features={features_updated}, missing={missing_fields}"
        )

        return {
            "symbol":               symbol,
            "as_of_date":           as_of_date,
            "securities_updated":   securities_updated,
            "features_updated":     features_updated,
            "credit_rating":        credit_rating,
            "credit_quality_proxy": credit_quality_proxy,
            "chowder_number":       chowder_number,
            "yield_5yr_avg":        yield_5yr_avg,
            "providers_used":       providers_used,
            "missing_fields":       missing_fields,
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


# ------------------------------------------------------------------
# Dividend computation helpers (used by sync_symbol)
# ------------------------------------------------------------------

def _parse_div_date(record: dict) -> Optional[date]:
    """Parse ex_date from a dividend record to a date object."""
    raw = record.get("ex_date")
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        return None


def _compute_yield_trailing_12m(
    dividends: List[dict],
    current_price: Optional[float],
) -> Optional[float]:
    """Return trailing-12-month dividend yield as a percentage.

    Sum all dividend amounts whose ex_date falls within the last 12 months,
    then divide by current_price.  Returns None if no dividends or no price.
    """
    if not dividends or not current_price or current_price <= 0:
        return None
    cutoff = date.today() - timedelta(days=365)
    ttm_amount = sum(
        float(d.get("amount") or 0)
        for d in dividends
        if (_parse_div_date(d) or date.min) >= cutoff
    )
    if ttm_amount <= 0:
        return None
    return round((ttm_amount / current_price) * 100, 4)


def _compute_div_cagr_5y(dividends: List[dict]) -> Optional[float]:
    """Return 5-year dividend CAGR as a percentage.

    Groups dividends by calendar year, sums each year's total, then
    computes CAGR between the earliest and most recent full years.
    Returns None if fewer than 2 years of data are available.
    """
    if not dividends:
        return None

    by_year: dict[int, float] = {}
    today_year = date.today().year
    cutoff_year = today_year - 5

    for d in dividends:
        ex = _parse_div_date(d)
        if ex is None or ex.year < cutoff_year:
            continue
        # Exclude current in-progress year to avoid partial-year bias
        if ex.year >= today_year:
            continue
        by_year[ex.year] = by_year.get(ex.year, 0.0) + float(d.get("amount") or 0)

    if len(by_year) < 2:
        return None

    years = sorted(by_year)
    first_amt = by_year[years[0]]
    last_amt  = by_year[years[-1]]
    n_years   = years[-1] - years[0]

    if first_amt <= 0 or n_years <= 0:
        return None

    cagr = ((last_amt / first_amt) ** (1.0 / n_years) - 1) * 100
    return round(cagr, 4)


def _compute_yield_5yr_avg(
    dividends: List[dict],
    current_price: Optional[float],
) -> Optional[float]:
    """Return the average annual dividend yield over the last 5 calendar years.

    For each year, compute (total annual dividends / current_price) * 100,
    then average those yields.  Uses current_price as a price proxy for all
    years — an approximation, but avoids needing per-year historical prices.

    Returns None if current_price is unavailable or fewer than 2 years of
    dividend data exist.
    """
    if not dividends or not current_price or current_price <= 0:
        return None

    today_year = date.today().year
    cutoff_year = today_year - 5
    by_year: dict[int, float] = {}

    for d in dividends:
        ex = _parse_div_date(d)
        if ex is None or ex.year < cutoff_year or ex.year >= today_year:
            continue
        by_year[ex.year] = by_year.get(ex.year, 0.0) + float(d.get("amount") or 0)

    if len(by_year) < 2:
        return None

    annual_yields = [
        (total / current_price) * 100
        for total in by_year.values()
        if total > 0
    ]
    if not annual_yields:
        return None
    return round(sum(annual_yields) / len(annual_yields), 4)
