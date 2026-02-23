"""Abstract base class for market data providers."""
from abc import ABC, abstractmethod
from typing import Optional


class ProviderError(Exception):
    """Raised when a provider encounters an unrecoverable error (network, auth, etc.)."""


class DataUnavailableError(ProviderError):
    """Raised when the requested data does not exist for the given symbol."""


class BaseDataProvider(ABC):
    """Contract that every market data provider must satisfy.

    Implementations are expected to be used as async context managers so that
    underlying HTTP sessions are opened and closed cleanly, matching the pattern
    already established by AlphaVantageClient:

        async with MyProvider(api_key=...) as provider:
            price = await provider.get_current_price("AAPL")

    All methods raise:
        ProviderError       — network failure, auth error, or unexpected API response.
        DataUnavailableError — symbol not found or data not offered by this provider.
    """

    # ------------------------------------------------------------------
    # Async context-manager protocol (subclasses may override)
    # ------------------------------------------------------------------

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_current_price(self, symbol: str) -> dict:
        """Return the latest quote for *symbol*.

        Returns:
            {
                "symbol":    str,   # upper-cased ticker
                "price":     float,
                "volume":    int,
                "timestamp": str,   # ISO-8601 datetime string
                "source":    str,   # provider identifier, e.g. "alpha_vantage"
            }
        """

    @abstractmethod
    async def get_daily_prices(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> list[dict]:
        """Return daily OHLCV bars for *symbol*.

        Args:
            symbol:     Ticker symbol.
            outputsize: "compact" (last ~100 trading days) or
                        "full" (full available history).

        Returns:
            List of dicts, each containing:
            {
                "date":          str,            # ISO-8601 date string "YYYY-MM-DD"
                "open":          float,
                "high":          float,
                "low":           float,
                "close":         float,
                "adjusted_close": float | None,
                "volume":        int,
            }
            Sorted by date descending (most recent first).
        """

    @abstractmethod
    async def get_dividend_history(self, symbol: str) -> list[dict]:
        """Return dividend payment history for *symbol*.

        Returns:
            List of dicts, each containing:
            {
                "ex_date":      str,         # ISO-8601 date "YYYY-MM-DD"
                "payment_date": str | None,  # ISO-8601 date, if available
                "amount":       float,       # dividend per share
                "frequency":    str | None,  # e.g. "quarterly", "monthly"
                "yield_pct":    float | None,
            }
            Sorted by ex_date descending.
        """

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> dict:
        """Return key fundamental metrics for *symbol*.

        Returns:
            {
                "pe_ratio":        float | None,
                "debt_to_equity":  float | None,
                "payout_ratio":    float | None,
                "earnings_growth": float | None,  # e.g. 0.12 for 12%
                "free_cash_flow":  float | None,  # in USD
                "credit_rating":   str   | None,  # e.g. "BBB+"
                "market_cap":      float | None,  # in USD
                "sector":          str   | None,
            }
        """

    @abstractmethod
    async def get_etf_holdings(self, symbol: str) -> dict:
        """Return ETF-specific metadata for *symbol*.

        Returns:
            {
                "expense_ratio": float | None,       # e.g. 0.0035 for 0.35%
                "aum":           float | None,       # assets under management in USD
                "top_holdings":  list[dict],         # each: { ticker, weight_pct, name }
                "covered_call":  bool,               # True if this is a covered-call ETF
            }
        """
