"""ProviderRouter — routes market data requests across Polygon, FMP, and yfinance.

Priority chains (left = highest priority):

    get_current_price    : Polygon → FMP → yfinance
    get_daily_prices     : Polygon → yfinance
    get_dividend_history : FMP → yfinance
    get_fundamentals     : FMP → yfinance
    get_etf_holdings     : FMP → yfinance

Typical usage:

    router = ProviderRouter(
        polygon=PolygonClient(api_key=settings.polygon_api_key),
        fmp=FMPClient(api_key=settings.fmp_api_key),
        yfinance=YFinanceClient(),
        cache=cache_manager,
    )
    async with router:
        price = await router.get_current_price("AAPL")

Any provider may be None when its API key is absent; it is silently skipped.
The router is itself an async context manager that opens and closes the HTTP
sessions of all configured child providers.
"""
import logging
from typing import Any, Callable, Coroutine, Optional

from fetchers.base_provider import DataUnavailableError, ProviderError

logger = logging.getLogger(__name__)

# Readable type alias: a no-arg async callable that returns any value
_CoroFactory = Callable[[], Coroutine[Any, Any, Any]]


class ProviderRouter:
    """Routes data requests to the best available provider with automatic fallback.

    Args:
        polygon:  PolygonClient instance (or None if not configured).
        fmp:      FMPClient instance (or None if not configured).
        yfinance: YFinanceClient instance (or None if not configured).
        cache:    CacheManager instance (stored for future use; caching is
                  currently handled inside each individual provider).
    """

    def __init__(self, polygon, fmp, yfinance, cache=None):
        self.polygon  = polygon
        self.fmp      = fmp
        self.yfinance = yfinance
        self.cache    = cache

    # ------------------------------------------------------------------
    # Async context-manager — manages child provider sessions
    # ------------------------------------------------------------------

    async def __aenter__(self):
        """Open HTTP sessions for all configured providers.

        Providers that fail to initialise are set to None so they are
        automatically skipped during routing rather than crashing requests.
        """
        for name in ("polygon", "fmp", "yfinance"):
            provider = getattr(self, name)
            if provider is None:
                continue
            try:
                await provider.__aenter__()
            except Exception as e:
                logger.warning(
                    f"⚠️  Could not open {name} session: {e} — {name} will be skipped"
                )
                setattr(self, name, None)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP sessions for all configured providers."""
        for name in ("polygon", "fmp", "yfinance"):
            provider = getattr(self, name)
            if provider is None:
                continue
            try:
                await provider.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"Error closing {name} session: {e}")

    # ------------------------------------------------------------------
    # Public routing methods
    # ------------------------------------------------------------------

    async def get_current_price(self, symbol: str) -> dict:
        """Return the latest quote for *symbol*.

        Chain: Polygon (real-time, ms precision) → FMP → yfinance (fallback).
        """
        symbol = symbol.upper()
        chain  = self._build_chain(
            symbol, "get_current_price",
            [self.polygon, self.fmp, self.yfinance],
            ["polygon",    "fmp",    "yfinance"],
        )
        return await self._try_chain(f"get_current_price({symbol})", chain)

    async def get_daily_prices(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> list[dict]:
        """Return daily OHLCV bars for *symbol*.

        Chain: Polygon (VWAP-adjusted, full data) → yfinance (auto-adjusted).
        FMP is intentionally absent — Polygon is a better fit for price series.
        """
        symbol = symbol.upper()
        chain  = self._build_chain(
            symbol, "get_daily_prices",
            [self.polygon, self.yfinance],
            ["polygon",    "yfinance"],
            outputsize=outputsize,
        )
        return await self._try_chain(f"get_daily_prices({symbol}/{outputsize})", chain)

    async def get_dividend_history(self, symbol: str) -> list[dict]:
        """Return dividend payment history for *symbol*.

        Chain: FMP (most complete dividend records) → yfinance.
        Polygon is intentionally absent — dividend coverage is limited on the
        Starter tier.
        """
        symbol = symbol.upper()
        chain  = self._build_chain(
            symbol, "get_dividend_history",
            [self.fmp,  self.yfinance],
            ["fmp",     "yfinance"],
        )
        return await self._try_chain(f"get_dividend_history({symbol})", chain)

    async def get_fundamentals(self, symbol: str) -> dict:
        """Return key fundamental metrics for *symbol*.

        Chain: FMP (pre-computed ratios + cash-flow) → yfinance.
        Polygon is intentionally absent — financial statement coverage is
        limited on the Starter tier.
        """
        symbol = symbol.upper()
        chain  = self._build_chain(
            symbol, "get_fundamentals",
            [self.fmp,  self.yfinance],
            ["fmp",     "yfinance"],
        )
        return await self._try_chain(f"get_fundamentals({symbol})", chain)

    async def get_etf_holdings(self, symbol: str) -> dict:
        """Return ETF metadata and top holdings for *symbol*.

        Chain: FMP (etf-holder endpoint) → yfinance (funds_data).
        Polygon is intentionally absent — ETF holdings are not available
        via the Polygon API.
        """
        symbol = symbol.upper()
        chain  = self._build_chain(
            symbol, "get_etf_holdings",
            [self.fmp,  self.yfinance],
            ["fmp",     "yfinance"],
        )
        return await self._try_chain(f"get_etf_holdings({symbol})", chain)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_chain(
        self,
        symbol: str,
        method_name: str,
        providers: list,
        names: list[str],
        **kwargs,
    ) -> list[tuple[str, _CoroFactory]]:
        """Build an ordered list of (provider_name, coro_factory) pairs.

        Only providers that are not None are included.  ``**kwargs`` are
        forwarded to the provider method as keyword arguments.
        """
        chain: list[tuple[str, _CoroFactory]] = []
        for name, provider in zip(names, providers):
            if provider is None:
                continue
            method = getattr(provider, method_name)
            # Capture provider and method by reference at chain-build time;
            # kwargs are also captured here so each factory is self-contained.
            if kwargs:
                factory: _CoroFactory = (
                    lambda sym=symbol, m=method, kw=kwargs: m(sym, **kw)
                )
            else:
                factory = (lambda sym=symbol, m=method: m(sym))
            chain.append((name, factory))
        return chain

    async def _try_chain(
        self,
        label: str,
        chain: list[tuple[str, _CoroFactory]],
    ) -> Any:
        """Try each (name, coro_factory) in *chain* in order.

        Returns the first successful result.  ProviderError and
        DataUnavailableError are caught and logged as warnings; any other
        exception propagates immediately (programming error or truly
        unrecoverable failure).

        Raises:
            ProviderError — when every configured provider has failed,
                            with a concatenated summary of all failures.
            ProviderError — when no providers are configured at all.
        """
        if not chain:
            raise ProviderError(f"No providers configured for {label}")

        failures: list[str] = []
        for name, coro_factory in chain:
            try:
                result = await coro_factory()
                logger.info(f"✅ {label} served by {name}")
                return result
            except (ProviderError, DataUnavailableError) as e:
                logger.warning(
                    f"⚠️  {label}: {name} failed ({type(e).__name__}): {e}"
                )
                failures.append(f"{name}[{type(e).__name__}]: {e}")

        raise ProviderError(
            f"All providers failed for {label} — "
            + " | ".join(failures)
        )
