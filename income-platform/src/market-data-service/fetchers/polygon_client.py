"""Polygon.io REST API client — Stocks Starter tier (100 req/min).

Usage (mirrors AlphaVantageClient pattern):

    async with PolygonClient(api_key=settings.polygon_api_key) as client:
        price = await client.get_current_price("AAPL")
        bars  = await client.get_daily_prices("AAPL", outputsize="compact")
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import aiohttp

from fetchers.base_provider import BaseDataProvider, DataUnavailableError, ProviderError

logger = logging.getLogger(__name__)

# Cache TTLs
_TTL_PRICE        =  5 * 60       # 5 minutes  — prices change frequently
_TTL_DIVIDENDS    =  4 * 60 * 60  # 4 hours    — dividend records are stable intraday
_TTL_FUNDAMENTALS = 24 * 60 * 60  # 24 hours   — financial statements change quarterly

# Polygon frequency integer → human-readable string
_FREQ_MAP: dict[int, str] = {
    1:  "annually",
    2:  "semi-annually",
    4:  "quarterly",
    12: "monthly",
    52: "weekly",
}

# Polygon API status values that indicate a successful (possibly delayed) response
_OK_STATUSES = {"OK", "DELAYED", ""}


class PolygonClient(BaseDataProvider):
    """Polygon.io REST API v2/v3 client — Stocks Starter tier.

    Rate limit: 100 requests/minute (0.6 s minimum interval).
    The class-level ``_last_request_time`` is shared across all instances so
    that the rate limit is respected even when a new client is created per
    request — identical to the pattern used in AlphaVantageClient.
    """

    BASE_URL = "https://api.polygon.io"

    # Class-level rate-limit timestamp, shared across all instances
    _last_request_time: Optional[datetime] = None

    def __init__(
        self,
        api_key: str,
        calls_per_minute: int = 100,
        cache=None,
    ):
        """
        Args:
            api_key:          Polygon.io API key (Stocks Starter or higher).
            calls_per_minute: Maximum requests per minute (default: 100 for Starter tier).
            cache:            Optional CacheManager instance for Redis caching.
        """
        self.api_key = api_key
        self.min_interval = 60.0 / calls_per_minute  # seconds between requests (0.6 s default)
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache = cache

    # ------------------------------------------------------------------
    # Async context-manager
    # ------------------------------------------------------------------

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # BaseDataProvider implementation
    # ------------------------------------------------------------------

    async def get_current_price(self, symbol: str) -> dict:
        """Return the latest trade price for *symbol*.

        Strategy:
        1. Redis cache (5-minute TTL).
        2. /v2/last/trade/{symbol}          — last individual trade (real-time).
        3. /v2/snapshot/.../tickers/{symbol} — fallback when the last-trade
           endpoint returns no data (e.g. outside market hours).

        Returns:
            { symbol, price, volume, timestamp, source }
        """
        symbol = symbol.upper()
        cache_key = f"polygon:price:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} current price (polygon)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # --- primary: last trade ---
        try:
            data = await self._get(f"/v2/last/trade/{symbol}")
            trade = data.get("results") or {}
            if trade and trade.get("p"):
                out = {
                    "symbol":    symbol,
                    "price":     float(trade["p"]),
                    "volume":    int(trade.get("s", 0)),   # size of this individual trade
                    "timestamp": _ns_to_iso(trade.get("t", 0)),
                    "source":    "polygon",
                }
                await self._cache_set(cache_key, out, _TTL_PRICE)
                return out
        except DataUnavailableError:
            logger.info(f"Last-trade returned no data for {symbol}, trying snapshot")
        except ProviderError as e:
            logger.warning(f"Last-trade failed for {symbol}: {e}, trying snapshot")

        # --- fallback: market snapshot (carries daily volume) ---
        data = await self._get(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
        )
        ticker = data.get("ticker") or {}
        if not ticker:
            raise DataUnavailableError(f"No price data available for {symbol}")

        last_trade = ticker.get("lastTrade") or {}
        day        = ticker.get("day") or {}
        out = {
            "symbol":    symbol,
            "price":     float(last_trade.get("p") or day.get("c") or 0),
            "volume":    int(day.get("v", 0)),
            "timestamp": _ns_to_iso(ticker.get("updated", 0)),
            "source":    "polygon",
        }
        await self._cache_set(cache_key, out, _TTL_PRICE)
        return out

    async def get_daily_prices(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> list[dict]:
        """Return daily OHLCV bars from /v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}.

        Args:
            symbol:     Ticker symbol.
            outputsize: "compact" → last ~140 calendar days (~100 trading days).
                        "full"   → last 2 years.

        Response fields mapped as specified:
            o → open, h → high, l → low, c → close, v → volume, vw → adjusted_close.

        Returns:
            List of dicts sorted by date descending (most recent first).
        """
        symbol = symbol.upper()
        today = date.today()
        days_back = 140 if outputsize == "compact" else 730
        start = (today - timedelta(days=days_back)).isoformat()
        end   = today.isoformat()

        cache_key = f"polygon:daily:{symbol}:{outputsize}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(
                        f"✅ Cache hit for {symbol} daily prices (polygon/{outputsize})"
                    )
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        data = await self._get(
            f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}",
            params={"adjusted": "true", "sort": "desc", "limit": 730},
        )

        raw = data.get("results") or []
        if not raw:
            logger.warning(f"No daily price data returned for {symbol}")
            return []

        results = []
        for bar in raw:
            try:
                results.append({
                    "date":           _ms_to_date(bar["t"]),
                    "open":           float(bar["o"]),
                    "high":           float(bar["h"]),
                    "low":            float(bar["l"]),
                    "close":          float(bar["c"]),
                    "adjusted_close": float(bar.get("vw") or bar["c"]),  # vw = VWAP
                    "volume":         int(bar["v"]),
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed bar for {symbol}: {e}")
                continue

        logger.info(f"✅ Fetched {len(results)} daily bars for {symbol} (polygon/{outputsize})")
        await self._cache_set(cache_key, results, _TTL_PRICE)
        return results

    async def get_dividend_history(self, symbol: str) -> list[dict]:
        """Return dividend payment history from /v3/reference/dividends.

        Maps:
            ex_dividend_date → ex_date
            pay_date         → payment_date
            cash_amount      → amount
            frequency (int)  → frequency (str, e.g. "quarterly")

        Note: Polygon v3 dividends does not provide a yield_pct field;
              that value is always returned as None.
        """
        symbol = symbol.upper()
        cache_key = f"polygon:dividends:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} dividends (polygon)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        data = await self._get(
            "/v3/reference/dividends",
            params={
                "ticker":       symbol,
                "limit":        50,
                "order":        "desc",
                "sort":         "ex_dividend_date",
            },
        )

        raw = data.get("results") or []
        results = []
        for item in raw:
            try:
                freq_int = item.get("frequency")
                results.append({
                    "ex_date":      item.get("ex_dividend_date"),
                    "payment_date": item.get("pay_date"),
                    "amount":       float(item.get("cash_amount", 0)),
                    "frequency":    _FREQ_MAP.get(freq_int) if freq_int is not None else None,
                    "yield_pct":    None,  # not provided by Polygon v3 dividends endpoint
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed dividend record for {symbol}: {e}")
                continue

        logger.info(f"✅ Fetched {len(results)} dividend records for {symbol} (polygon)")
        await self._cache_set(cache_key, results, _TTL_DIVIDENDS)
        return results

    async def get_fundamentals(self, symbol: str) -> dict:
        """Return key fundamental metrics from two Polygon endpoints (concurrent fetch):

        1. /vX/reference/financials?ticker={symbol}&limit=4
           — income statement, balance sheet, cash flow (4 most recent quarters).
        2. /v3/reference/tickers/{symbol}
           — market_cap, sector (sic_description).

        Derived metrics:
            pe_ratio        = market_cap / TTM net income
            debt_to_equity  = long_term_debt / equity  (latest quarter balance sheet)
            payout_ratio    = TTM dividends paid / TTM net income
            earnings_growth = (latest EPS - oldest EPS in window) / |oldest EPS|
            free_cash_flow  = TTM operating cash flow + TTM capex (capex is negative)

        Fields not available from Polygon (always None):
            credit_rating
        """
        symbol = symbol.upper()
        cache_key = f"polygon:fundamentals:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} fundamentals (polygon)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # Fetch both endpoints concurrently; capture individual failures without aborting
        fin_result, ticker_result = await asyncio.gather(
            self._get("/vX/reference/financials", params={"ticker": symbol, "limit": 4}),
            self._get(f"/v3/reference/tickers/{symbol}"),
            return_exceptions=True,
        )

        # --- market_cap and sector ---
        market_cap: Optional[float] = None
        sector:     Optional[str]   = None
        if not isinstance(ticker_result, Exception):
            td = ticker_result.get("results") or {}
            market_cap = float(td["market_cap"]) if td.get("market_cap") else None
            sector     = td.get("sic_description")
        else:
            logger.warning(f"Ticker details unavailable for {symbol}: {ticker_result}")

        # --- financial statement metrics ---
        pe_ratio        = None
        debt_to_equity  = None
        payout_ratio    = None
        earnings_growth = None
        free_cash_flow  = None

        if not isinstance(fin_result, Exception):
            periods = fin_result.get("results") or []
        else:
            logger.warning(f"Financials unavailable for {symbol}: {fin_result}")
            periods = []

        if periods:
            # --- TTM accumulators ---
            ttm_net_income  = 0.0
            ttm_div_paid    = 0.0
            ttm_op_cf       = 0.0
            ttm_capex       = 0.0
            ttm_has_income  = False
            ttm_has_cf      = False

            for p in periods:
                fin = p.get("financials") or {}
                inc = fin.get("income_statement")    or {}
                cf  = fin.get("cash_flow_statement") or {}

                ni = _fin_val(inc, "net_income_loss")
                if ni is not None:
                    ttm_net_income += ni
                    ttm_has_income  = True

                div = _fin_val(
                    cf,
                    "dividends_and_dividend_equivalents_paid_to_common_stock"
                    "_and_noncontrolling_interests",
                )
                if div is not None:
                    ttm_div_paid += abs(div)

                ocf = _fin_val(cf, "net_cash_flow_from_operating_activities")
                if ocf is not None:
                    ttm_op_cf    += ocf
                    ttm_has_cf    = True

                capex = _fin_val(cf, "capital_expenditure")
                if capex is not None:
                    ttm_capex += capex  # already negative in Polygon statements

            # PE = market cap / TTM net income
            if market_cap and ttm_has_income and ttm_net_income > 0:
                pe_ratio = round(market_cap / ttm_net_income, 2)

            # FCF = TTM operating CF + TTM capex (capex is negative)
            if ttm_has_cf:
                free_cash_flow = ttm_op_cf + ttm_capex

            # Payout ratio = TTM dividends paid / TTM net income
            if ttm_has_income and ttm_net_income > 0 and ttm_div_paid > 0:
                payout_ratio = round(ttm_div_paid / ttm_net_income, 4)

            # --- point-in-time metrics from the most recent period ---
            latest_fin = periods[0].get("financials") or {}
            bal = latest_fin.get("balance_sheet") or {}

            long_term_debt = _fin_val(bal, "long_term_debt")
            equity = _fin_val(bal, "equity") or _fin_val(bal, "stockholders_equity")
            if long_term_debt is not None and equity and equity != 0:
                debt_to_equity = round(long_term_debt / equity, 4)

            # Earnings growth: compare most recent EPS to oldest EPS in the window.
            # With limit=4 this spans ~1 year of quarters; treat as approximate YoY.
            if len(periods) >= 2:
                newest_inc = periods[0].get("financials", {}).get("income_statement", {})
                oldest_inc = periods[-1].get("financials", {}).get("income_statement", {})
                eps_new = _fin_val(newest_inc, "diluted_earnings_per_share")
                eps_old = _fin_val(oldest_inc, "diluted_earnings_per_share")
                if eps_new is not None and eps_old and eps_old != 0:
                    earnings_growth = round((eps_new - eps_old) / abs(eps_old), 4)

        out = {
            "pe_ratio":        pe_ratio,
            "debt_to_equity":  debt_to_equity,
            "payout_ratio":    payout_ratio,
            "earnings_growth": earnings_growth,
            "free_cash_flow":  free_cash_flow,
            "credit_rating":   None,   # not provided by Polygon
            "market_cap":      market_cap,
            "sector":          sector,
        }
        await self._cache_set(cache_key, out, _TTL_FUNDAMENTALS)
        return out

    async def get_etf_holdings(self, symbol: str) -> dict:
        """Not supported — Polygon.io does not provide ETF holdings data."""
        raise DataUnavailableError(
            f"ETF holdings are not available from Polygon.io (symbol: {symbol.upper()})"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Authenticated GET with rate limiting and structured error mapping.

        Raises:
            ProviderError        — network error, auth failure, rate-limit hit, or
                                   unexpected API status.
            DataUnavailableError — HTTP 404 or empty result set.
        """
        if not self.session:
            raise RuntimeError("PolygonClient must be used as an async context manager")

        await self._rate_limit()

        url = f"{self.BASE_URL}{path}"
        try:
            async with self.session.get(
                url,
                params=params or {},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise ProviderError(
                        f"Polygon auth error HTTP {resp.status} for {path}"
                    )
                if resp.status == 404:
                    raise DataUnavailableError(
                        f"Polygon: resource not found: {path}"
                    )
                if resp.status == 429:
                    raise ProviderError(
                        f"Polygon rate limit exceeded (HTTP 429) for {path}"
                    )
                resp.raise_for_status()

                data = await resp.json()
                status = data.get("status", "")
                if status not in _OK_STATUSES:
                    raise ProviderError(
                        f"Polygon unexpected status '{status}' for {path}: "
                        f"{data.get('error', '')}"
                    )
                return data

        except (ProviderError, DataUnavailableError):
            raise
        except aiohttp.ClientError as e:
            raise ProviderError(f"Network error for {path}: {e}") from e

    async def _rate_limit(self) -> None:
        """Enforce the per-minute rate limit using a class-level shared timestamp.

        Uses the same pattern as AlphaVantageClient._last_request_time so that
        rate limiting applies across all PolygonClient instances in the process.
        """
        if PolygonClient._last_request_time is not None:
            elapsed = (
                datetime.now() - PolygonClient._last_request_time
            ).total_seconds()
            if elapsed < self.min_interval:
                wait = self.min_interval - elapsed
                logger.debug(f"⏱️  Polygon rate limit: waiting {wait:.3f}s")
                await asyncio.sleep(wait)
        PolygonClient._last_request_time = datetime.now()

    async def _cache_set(self, key: str, value, ttl: int) -> None:
        """Write to Redis cache, best-effort (never raises)."""
        if not self._cache or not value:
            return
        try:
            await self._cache.set(key, value, ttl=ttl)
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _ns_to_iso(nanoseconds: int) -> str:
    """Convert a Unix nanosecond timestamp to an ISO-8601 UTC string.

    Polygon uses nanoseconds for trade and snapshot timestamps.
    Falls back to the current UTC time if nanoseconds is 0 or None.
    """
    if not nanoseconds:
        return datetime.now(tz=timezone.utc).isoformat()
    return datetime.fromtimestamp(
        nanoseconds / 1_000_000_000, tz=timezone.utc
    ).isoformat()


def _ms_to_date(milliseconds: int) -> str:
    """Convert a Unix millisecond timestamp to an ISO-8601 date string.

    Polygon uses milliseconds for aggregate bar timestamps.
    """
    return date.fromtimestamp(milliseconds / 1000).isoformat()


def _fin_val(section: dict, key: str) -> Optional[float]:
    """Safely extract a numeric value from a Polygon financials section.

    Polygon financial statement entries are shaped as:
        { "value": 12345678.9, "unit": "USD", "label": "...", ... }

    Returns None if the key is absent, the entry has no "value", or
    the value is not numeric.
    """
    entry = section.get(key)
    if entry is None:
        return None
    try:
        return float(entry["value"])
    except (KeyError, TypeError, ValueError):
        return None
