"""Financial Modeling Prep (FMP) REST API client — stable API.

Usage (mirrors AlphaVantageClient / PolygonClient pattern):

    async with FMPClient(api_key=settings.fmp_api_key) as client:
        price = await client.get_current_price("AAPL")
        bars  = await client.get_daily_prices("AAPL", outputsize="compact")

Authentication: apikey query parameter (not a header).
Rate limit: 300 requests/minute (0.2 s minimum interval).

Stable API (https://financialmodelingprep.com/stable) replaces the legacy
v3 API (https://financialmodelingprep.com/api/v3).  All endpoints now use
query parameters for the symbol instead of path segments, and several field
names changed (mktCap → marketCap, priceEarningsRatio → priceToEarningsRatio,
debtEquityRatio → debtToEquityRatio, payoutRatio → dividendPayoutRatio).
Historical prices are now a flat list rather than {"historical": [...]}.
Dividends now include a "frequency" string ("Quarterly", "Monthly", etc.).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from fetchers.base_provider import BaseDataProvider, DataUnavailableError, ProviderError

logger = logging.getLogger(__name__)

# Cache TTLs — same values as PolygonClient
_TTL_PRICE        =  5 * 60        # 5 minutes
_TTL_DIVIDENDS    =  4 * 60 * 60   # 4 hours
_TTL_FUNDAMENTALS = 24 * 60 * 60   # 24 hours

# Known covered-call / buy-write ETF symbols.  Checked as a last resort when
# description and fund name do not contain sufficient keywords.
_COVERED_CALL_SYMBOLS = frozenset(
    ["JEPI", "JEPQ", "XYLD", "QYLD", "RYLD", "DIVO", "PBP", "BXMX"]
)


class FMPClient(BaseDataProvider):
    """Financial Modeling Prep stable API client.

    Rate limit: 300 requests/minute (0.2 s minimum interval).
    The class-level ``_last_request_time`` is shared across all instances so
    that the rate limit is respected even when a new client is created per
    request — identical to the pattern used in AlphaVantageClient and
    PolygonClient.
    """

    BASE_URL = "https://financialmodelingprep.com/stable"

    # Class-level rate-limit timestamp, shared across all instances
    _last_request_time: Optional[datetime] = None

    def __init__(
        self,
        api_key: str,
        calls_per_minute: int = 300,
        cache=None,
    ):
        """
        Args:
            api_key:          FMP API key.
            calls_per_minute: Maximum requests per minute (default: 300).
            cache:            Optional CacheManager instance for Redis caching.
        """
        self.api_key = api_key
        self.min_interval = 60.0 / calls_per_minute  # seconds between requests (0.2 s default)
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache = cache

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
    # BaseDataProvider implementation
    # ------------------------------------------------------------------

    async def get_current_price(self, symbol: str) -> dict:
        """Return the latest quote from /quote?symbol={symbol}.

        Stable /quote returns price, volume, and a Unix-seconds timestamp.

        Returns:
            { symbol, price, volume, timestamp, source }
        """
        symbol = symbol.upper()
        cache_key = f"fmp:price:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} current price (fmp)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        data = await self._get("/quote", params={"symbol": symbol})

        # Stable /quote returns a list
        if not isinstance(data, list) or not data:
            raise DataUnavailableError(f"No quote data returned for {symbol}")
        q = data[0]
        if not q.get("price"):
            raise DataUnavailableError(f"Empty price in quote response for {symbol}")

        ts = q.get("timestamp")
        timestamp = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            if ts
            else datetime.now(tz=timezone.utc).isoformat()
        )
        out = {
            "symbol":    symbol,
            "price":     float(q["price"]),
            "volume":    int(q.get("volume") or 0),
            "timestamp": timestamp,
            "source":    "fmp",
        }
        await self._cache_set(cache_key, out, _TTL_PRICE)
        return out

    async def get_daily_prices(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> list[dict]:
        """Return daily OHLCV bars from /historical-price-eod/full?symbol={symbol}.

        Args:
            symbol:     Ticker symbol.
            outputsize: "compact" → last 100 calendar days (timeseries=100).
                        "full"   → full available history.

        Stable API field mapping:
            date → date, open → open, high → high, low → low,
            close → close, vwap → adjusted_close, volume → volume.

        Note: The stable endpoint returns a flat list (no "historical" wrapper).
              "vwap" replaces "adjClose" from the legacy v3 endpoint.

        Returns:
            List of dicts sorted by date descending (most recent first).
        """
        symbol = symbol.upper()
        cache_key = f"fmp:daily:{symbol}:{outputsize}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(
                        f"✅ Cache hit for {symbol} daily prices (fmp/{outputsize})"
                    )
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        params: dict[str, Any] = {"symbol": symbol}
        if outputsize == "compact":
            params["timeseries"] = 100

        data = await self._get("/historical-price-eod/full", params=params)

        # Stable endpoint returns a flat list
        historical = data if isinstance(data, list) else []
        if not historical:
            logger.warning(f"No daily price data returned for {symbol}")
            return []

        results = []
        for bar in historical:
            try:
                results.append({
                    "date":           bar["date"],
                    "open":           _safe_float(bar.get("open")),
                    "high":           _safe_float(bar.get("high")),
                    "low":            _safe_float(bar.get("low")),
                    "close":          float(bar["close"]),
                    # vwap in stable; adjClose in legacy v3; fallback to close
                    "adjusted_close": _safe_float(
                        bar.get("vwap") or bar.get("adjClose") or bar.get("close")
                    ),
                    "volume":         int(bar["volume"]) if bar.get("volume") is not None else 0,
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed bar for {symbol}: {e}")
                continue

        # Stable returns newest-first — consistent with PolygonClient
        logger.info(f"✅ Fetched {len(results)} daily bars for {symbol} (fmp/{outputsize})")
        await self._cache_set(cache_key, results, _TTL_PRICE)
        return results

    async def get_dividend_history(self, symbol: str) -> list[dict]:
        """Return dividend payment history from /dividends?symbol={symbol}.

        Stable API field mapping:
            date        → ex_date
            paymentDate → payment_date
            dividend    → amount
            frequency   → frequency (lowercased: "quarterly", "monthly", etc.)

        yield_pct: computed as (dividend / current_price) * 100 using the
        current quote fetched concurrently.  This is a per-payment approximation
        using today's price, not the price at each historical ex-date.

        Note: The stable endpoint returns a flat list (no "historical" wrapper).
              "frequency" is now populated (was always None in the legacy v3 endpoint).

        Returns:
            List of dicts sorted by ex_date descending (newest first, per FMP default).
        """
        symbol = symbol.upper()
        cache_key = f"fmp:dividends:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} dividends (fmp)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # Fetch dividends and current price concurrently; price used for yield_pct
        divs_result, quote_result = await asyncio.gather(
            self._get("/dividends", params={"symbol": symbol}),
            self._get("/quote",     params={"symbol": symbol}),
            return_exceptions=True,
        )

        if isinstance(divs_result, Exception):
            raise ProviderError(
                f"Failed to fetch dividends for {symbol}: {divs_result}"
            ) from divs_result

        # Stable endpoint returns a flat list directly
        historical = divs_result if isinstance(divs_result, list) else []

        if not historical:
            logger.warning(f"No dividend history returned for {symbol}")
            return []

        # Resolve current price for yield approximation (best-effort; None if unavailable)
        current_price: Optional[float] = None
        if (
            not isinstance(quote_result, Exception)
            and isinstance(quote_result, list)
            and quote_result
        ):
            try:
                current_price = float(quote_result[0]["price"])
            except (KeyError, ValueError, TypeError):
                pass

        results = []
        for item in historical:
            try:
                amount = float(item.get("dividend") or 0)
                yield_pct = (
                    round((amount / current_price) * 100, 4)
                    if current_price and current_price > 0 and amount > 0
                    else None
                )
                # Normalize frequency to lowercase ("Quarterly" → "quarterly")
                raw_freq = item.get("frequency")
                frequency = raw_freq.lower() if isinstance(raw_freq, str) and raw_freq else None
                results.append({
                    "ex_date":      item.get("date"),
                    "payment_date": item.get("paymentDate"),
                    "amount":       amount,
                    "frequency":    frequency,
                    "yield_pct":    yield_pct,
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed dividend record for {symbol}: {e}")
                continue

        logger.info(f"✅ Fetched {len(results)} dividend records for {symbol} (fmp)")
        await self._cache_set(cache_key, results, _TTL_DIVIDENDS)
        return results

    async def get_fundamentals(self, symbol: str) -> dict:
        """Return key fundamental metrics from three FMP endpoints (concurrent fetch):

        1. /ratios?symbol={symbol}&limit=1
           — pe_ratio (priceToEarningsRatio), debt_to_equity (debtToEquityRatio),
             payout_ratio (dividendPayoutRatio).
        2. /cash-flow-statement?symbol={symbol}&limit=4&period=annual
           — free_cash_flow (3-4 year average of annual freeCashFlow).
        3. /profile?symbol={symbol}
           — market_cap (marketCap), sector.

        Fields not available from FMP basic endpoints (always None):
            earnings_growth — use /financial-growth endpoint for this metric.
            credit_rating   — use /rating endpoint or a dedicated credit API.
        """
        symbol = symbol.upper()
        cache_key = f"fmp:fundamentals:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} fundamentals (fmp)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # Three endpoints concurrently.
        # return_exceptions=True so secondary failures (cash-flow, profile) are
        # tolerated, but a ratios failure is re-raised as ProviderError so that
        # _try_chain can fall back to yfinance rather than returning all-None.
        ratios_result, cf_result, profile_result = await asyncio.gather(
            self._get("/ratios",               params={"symbol": symbol, "limit": 1}),
            self._get("/cash-flow-statement",  params={"symbol": symbol, "limit": 4, "period": "annual"}),
            self._get("/profile",              params={"symbol": symbol}),
            return_exceptions=True,
        )

        # Ratios is the primary source; if it failed, surface the error so the
        # router's fallback chain can try yfinance instead.
        if isinstance(ratios_result, Exception):
            raise ProviderError(
                f"FMP /ratios failed for {symbol}: {ratios_result}"
            ) from ratios_result

        # --- pe_ratio, debt_to_equity, payout_ratio ---
        # Stable ratios field names differ from legacy v3:
        #   priceEarningsRatio → priceToEarningsRatio
        #   debtEquityRatio    → debtToEquityRatio
        #   payoutRatio        → dividendPayoutRatio
        pe_ratio       = None
        debt_to_equity = None
        payout_ratio   = None
        if isinstance(ratios_result, list) and ratios_result:
            r = ratios_result[0]
            pe_ratio       = _safe_float(r.get("priceToEarningsRatio"))
            debt_to_equity = _safe_float(r.get("debtToEquityRatio"))
            payout_ratio   = _safe_float(r.get("dividendPayoutRatio"))

        # --- free_cash_flow: average over up to 4 annual periods ---
        # "freeCashFlow" field name is unchanged in the stable API.
        # Cash-flow failure is non-fatal; log and continue.
        free_cash_flow = None
        if isinstance(cf_result, Exception):
            logger.warning(f"FMP /cash-flow-statement unavailable for {symbol}: {cf_result}")
        elif isinstance(cf_result, list) and cf_result:
            fcf_values = [
                float(p["freeCashFlow"])
                for p in cf_result
                if p.get("freeCashFlow") is not None
            ]
            if fcf_values:
                free_cash_flow = sum(fcf_values) / len(fcf_values)

        # --- market_cap and sector ---
        # Stable profile field: "marketCap" (was "mktCap" in legacy v3).
        # Profile failure is non-fatal; log and continue.
        market_cap = None
        sector     = None
        if isinstance(profile_result, Exception):
            logger.warning(f"FMP /profile unavailable for {symbol}: {profile_result}")
        elif isinstance(profile_result, list) and profile_result:
            p = profile_result[0]
            market_cap = _safe_float(p.get("marketCap") or p.get("mktCap"))
            sector     = p.get("sector")

        out = {
            "pe_ratio":        pe_ratio,
            "debt_to_equity":  debt_to_equity,
            "payout_ratio":    payout_ratio,
            "earnings_growth": None,   # available via /financial-growth, not fetched here
            "free_cash_flow":  free_cash_flow,
            "credit_rating":   None,   # available via /rating, not fetched here
            "market_cap":      market_cap,
            "sector":          sector,
        }
        await self._cache_set(cache_key, out, _TTL_FUNDAMENTALS)
        return out

    async def get_etf_holdings(self, symbol: str) -> dict:
        """Return ETF metadata from /etf-holder?symbol={symbol} and /profile?symbol={symbol}.

        Holdings source:  /etf-holder?symbol={symbol}
            Maps: asset → ticker, name → name,
                  weight (decimal ratio, e.g. 0.0741) → weight_pct (7.41).
            Capped at the top 20 holdings by position in the response.

        Profile source:   /profile?symbol={symbol}
            marketCap   → aum  (also tries legacy "mktCap" as fallback)
            covered_call detection uses OR logic — any match returns True:
                description contains "covered call", "buy-write", "option",
                  "eln", or "equity linked note"
                companyName contains "Premium Income", "Equity Premium",
                  or "buy-write"
                symbol is in _COVERED_CALL_SYMBOLS

        Note: FMP profile does not expose expense_ratio; that field is always None.

        Returns:
            { expense_ratio, aum, top_holdings, covered_call }
        """
        symbol = symbol.upper()
        cache_key = f"fmp:etf:{symbol}"

        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.info(f"✅ Cache hit for {symbol} ETF holdings (fmp)")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")

        # Fetch holdings and profile concurrently
        holdings_result, profile_result = await asyncio.gather(
            self._get("/etf-holder", params={"symbol": symbol}),
            self._get("/profile",    params={"symbol": symbol}),
            return_exceptions=True,
        )

        if isinstance(holdings_result, Exception):
            raise DataUnavailableError(
                f"ETF holdings unavailable for {symbol}: {holdings_result}"
            ) from holdings_result

        # --- parse holdings (weight is a decimal ratio: 0.0741 = 7.41%) ---
        raw_holdings = holdings_result if isinstance(holdings_result, list) else []
        top_holdings = []
        for h in raw_holdings[:20]:
            try:
                weight_raw = h.get("weight")
                weight_pct = round(float(weight_raw) * 100, 4) if weight_raw is not None else None
                top_holdings.append({
                    "ticker":     h.get("asset") or h.get("symbol"),
                    "name":       h.get("name") or h.get("company"),
                    "weight_pct": weight_pct,
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed holding for {symbol}: {e}")
                continue

        # --- profile: aum and covered_call detection ---
        # Stable profile uses "marketCap"; legacy v3 used "mktCap" — try both.
        expense_ratio = None   # FMP profile does not expose expense_ratio
        aum           = None
        covered_call  = False
        if (
            not isinstance(profile_result, Exception)
            and isinstance(profile_result, list)
            and profile_result
        ):
            p = profile_result[0]
            aum         = _safe_float(p.get("marketCap") or p.get("mktCap"))
            description = (p.get("description") or "").lower()
            fund_name   = (p.get("companyName") or "").lower()
            covered_call = (
                "covered call"          in description
                or "buy-write"          in description
                or "option"             in description
                or "eln"                in description
                or "equity linked note" in description
                or "premium income"     in fund_name
                or "equity premium"     in fund_name
                or "buy-write"          in fund_name
                or symbol               in _COVERED_CALL_SYMBOLS
            )
        else:
            logger.warning(f"Profile unavailable for ETF {symbol}: {profile_result}")

        out = {
            "expense_ratio": expense_ratio,
            "aum":           aum,
            "top_holdings":  top_holdings,
            "covered_call":  covered_call,
        }
        await self._cache_set(cache_key, out, _TTL_FUNDAMENTALS)
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """Authenticated GET with rate limiting.

        FMP authenticates via the ``apikey`` query parameter appended to every
        request (not an Authorization header like Polygon).

        Returns a list or dict depending on the endpoint.

        Raises:
            ProviderError        — network error, auth failure, rate-limit hit,
                                   or API-level error message.
            DataUnavailableError — HTTP 404 from the server.
        """
        if not self.session:
            raise RuntimeError("FMPClient must be used as an async context manager")

        if not self.api_key:
            raise ProviderError(
                "FMP API key is not configured — set FMP_API_KEY in the environment"
            )

        await self._rate_limit()

        url = f"{self.BASE_URL}{path}"
        all_params = {"apikey": self.api_key, **(params or {})}
        logger.debug(
            "FMP _get %s (params: %s)",
            url,
            {k: ("***" if k == "apikey" else v) for k, v in all_params.items()},
        )
        try:
            async with self.session.get(
                url,
                params=all_params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise ProviderError(
                        f"FMP auth error HTTP {resp.status} for {path}"
                    )
                if resp.status == 404:
                    raise DataUnavailableError(f"FMP: resource not found: {path}")
                if resp.status == 429:
                    raise ProviderError(
                        f"FMP rate limit exceeded (HTTP 429) for {path}"
                    )
                resp.raise_for_status()

                data = await resp.json()

                # FMP signals API-level errors in a dict payload (same pattern as AV)
                if isinstance(data, dict) and data.get("Error Message"):
                    raise ProviderError(
                        f"FMP API error for {path}: {data['Error Message']}"
                    )

                return data

        except (ProviderError, DataUnavailableError):
            raise
        except aiohttp.ClientError as e:
            raise ProviderError(f"Network error for {path}: {e}") from e

    async def _rate_limit(self) -> None:
        """Enforce the per-minute rate limit using a class-level shared timestamp."""
        if FMPClient._last_request_time is not None:
            elapsed = (
                datetime.now() - FMPClient._last_request_time
            ).total_seconds()
            if elapsed < self.min_interval:
                wait = self.min_interval - elapsed
                logger.debug(f"⏱️  FMP rate limit: waiting {wait:.3f}s")
                await asyncio.sleep(wait)
        FMPClient._last_request_time = datetime.now()

    async def _cache_set(self, key: str, value: Any, ttl: int) -> None:
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

def _safe_float(value: Any) -> Optional[float]:
    """Return float(value), or None if value is None or cannot be converted."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
