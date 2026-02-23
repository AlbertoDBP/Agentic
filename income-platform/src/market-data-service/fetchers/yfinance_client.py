"""yfinance fallback provider — wraps the yfinance library for Yahoo Finance data.

FALLBACK ONLY: This client is intended as a last-resort fallback when both
Polygon and FMP are unavailable.  It runs against Yahoo Finance's unofficial
API via the yfinance library, which:
  - Has no SLA or rate-limit guarantees
  - Should not be used as a primary data source in production
  - Requires no API key

All yfinance calls are synchronous; they are dispatched to a thread pool via
``asyncio.to_thread`` to avoid blocking the event loop.

No Redis caching is applied — fallback calls are rare and data freshness
matters more than cache efficiency in these scenarios.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from fetchers.base_provider import BaseDataProvider, DataUnavailableError, ProviderError

logger = logging.getLogger(__name__)


class YFinanceClient(BaseDataProvider):
    """Yahoo Finance fallback provider via the yfinance library.

    No API key, no rate limiting, no Redis caching.
    Use only when Polygon and FMP are both unavailable.
    """

    # No __aenter__ / __aexit__ override needed — base class no-ops are sufficient.
    # yfinance manages its own HTTP sessions internally.

    # ------------------------------------------------------------------
    # BaseDataProvider implementation
    # ------------------------------------------------------------------

    async def get_current_price(self, symbol: str) -> dict:
        # FALLBACK ONLY — not for production primary use
        """Return the latest price from ``ticker.fast_info``.

        ``fast_info`` makes a single lightweight HTTP call and is significantly
        faster than ``ticker.info``.

        Returns:
            { symbol, price, volume, timestamp, source }
        """
        symbol = symbol.upper()

        def _fetch():
            t = yf.Ticker(symbol)
            fi = t.fast_info
            price = fi.last_price
            volume = fi.last_volume
            ts = fi.last_trade_date   # datetime (tz-aware) or None
            return price, volume, ts

        try:
            price, volume, ts = await asyncio.to_thread(_fetch)
        except Exception as e:
            raise ProviderError(f"yfinance error fetching price for {symbol}: {e}") from e

        if price is None:
            raise DataUnavailableError(f"No price data available for {symbol} via yfinance")

        timestamp = (
            ts.isoformat()
            if ts is not None
            else datetime.now(tz=timezone.utc).isoformat()
        )
        return {
            "symbol":    symbol,
            "price":     float(price),
            "volume":    int(volume) if volume is not None else 0,
            "timestamp": timestamp,
            "source":    "yfinance",
        }

    async def get_daily_prices(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> list[dict]:
        # FALLBACK ONLY — not for production primary use
        """Return daily OHLCV bars from ``ticker.history()``.

        yfinance returns split- and dividend-adjusted prices by default
        (``auto_adjust=True``), so ``adjusted_close`` equals ``close``.

        Args:
            symbol:     Ticker symbol.
            outputsize: "compact" → period="3mo" (~63 trading days).
                        "full"   → period="2y".

        Returns:
            List of dicts sorted by date descending (most recent first).
        """
        symbol = symbol.upper()
        period = "3mo" if outputsize == "compact" else "2y"

        def _fetch():
            t = yf.Ticker(symbol)
            # auto_adjust=True (default) returns split/dividend-adjusted prices
            return t.history(period=period, auto_adjust=True)

        try:
            hist = await asyncio.to_thread(_fetch)
        except Exception as e:
            raise ProviderError(
                f"yfinance error fetching history for {symbol}: {e}"
            ) from e

        if hist is None or hist.empty:
            raise DataUnavailableError(
                f"No historical price data available for {symbol} via yfinance"
            )

        results = []
        for ts, row in hist.iterrows():
            try:
                close = float(row["Close"])
                results.append({
                    "date":           ts.date().isoformat(),
                    "open":           float(row["Open"]),
                    "high":           float(row["High"]),
                    "low":            float(row["Low"]),
                    "close":          close,
                    "adjusted_close": close,   # history() already returns adjusted prices
                    "volume":         int(row["Volume"]),
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed bar for {symbol}: {e}")
                continue

        results.sort(key=lambda x: x["date"], reverse=True)
        logger.info(
            f"✅ yfinance fetched {len(results)} daily bars for {symbol} ({outputsize})"
        )
        return results

    async def get_dividend_history(self, symbol: str) -> list[dict]:
        # FALLBACK ONLY — not for production primary use
        """Return dividend history from ``ticker.dividends``.

        ``ticker.dividends`` is a pandas Series indexed by ex-date.
        ``ticker.actions`` adds stock-split context but the dividend amounts
        are the same; it is fetched alongside dividends here for consistency
        with the spec intent (both are read in the same thread call).

        Frequency is inferred from the average interval between ex-dates.
        Payment date is not available via yfinance and is always None.
        yield_pct is computed as (dividend / current_price) * 100 using
        ``fast_info.last_price`` fetched in the same thread call.

        Returns:
            List of dicts sorted by ex_date descending.
        """
        symbol = symbol.upper()

        def _fetch():
            t = yf.Ticker(symbol)
            divs    = t.dividends   # Series: DatetimeIndex → float
            _actions = t.actions    # DataFrame (Dividends + Stock Splits) — fetched per spec
            price   = t.fast_info.last_price
            return divs, price

        try:
            divs, current_price = await asyncio.to_thread(_fetch)
        except Exception as e:
            raise ProviderError(
                f"yfinance error fetching dividends for {symbol}: {e}"
            ) from e

        if divs is None or divs.empty:
            return []

        # Infer frequency from the spacing between ex-dates
        ex_dates = [ts.date() for ts in divs.index]
        frequency = _infer_frequency(ex_dates)

        results = []
        for ts, amount in divs.items():
            try:
                amt = float(amount)
                yield_pct = (
                    round((amt / float(current_price)) * 100, 4)
                    if current_price and float(current_price) > 0 and amt > 0
                    else None
                )
                results.append({
                    "ex_date":      ts.date().isoformat(),
                    "payment_date": None,   # not available via yfinance
                    "amount":       amt,
                    "frequency":    frequency,
                    "yield_pct":    yield_pct,
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed dividend for {symbol}: {e}")
                continue

        results.sort(key=lambda x: x["ex_date"], reverse=True)
        logger.info(
            f"✅ yfinance fetched {len(results)} dividend records for {symbol}"
        )
        return results

    async def get_fundamentals(self, symbol: str) -> dict:
        # FALLBACK ONLY — not for production primary use
        """Return fundamental metrics from ``ticker.info``.

        ``ticker.info`` makes several HTTP requests and is slow (~1-3 s).
        It returns a flat dict with hundreds of fields; only the subset
        defined by BaseDataProvider is extracted here.

        yfinance field mapping:
            trailingPE     → pe_ratio
            debtToEquity   → debt_to_equity  (ratio, e.g. 1.47 = 147%)
            payoutRatio    → payout_ratio     (decimal, e.g. 0.15 = 15%)
            earningsGrowth → earnings_growth  (decimal, e.g. 0.12 = 12%)
            freeCashflow   → free_cash_flow   (USD)
            marketCap      → market_cap       (USD)
            sector         → sector
            (credit_rating is not available via yfinance — always None)
        """
        symbol = symbol.upper()

        def _fetch():
            return yf.Ticker(symbol).info

        try:
            info = await asyncio.to_thread(_fetch)
        except Exception as e:
            raise ProviderError(
                f"yfinance error fetching fundamentals for {symbol}: {e}"
            ) from e

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            # yfinance returns a mostly-empty dict for invalid tickers
            if not info.get("symbol") and not info.get("longName"):
                raise DataUnavailableError(
                    f"No fundamental data available for {symbol} via yfinance"
                )

        return {
            "pe_ratio":        _safe_float(info.get("trailingPE")),
            "debt_to_equity":  _safe_float(info.get("debtToEquity")),
            "payout_ratio":    _safe_float(info.get("payoutRatio")),
            "earnings_growth": _safe_float(info.get("earningsGrowth")),
            "free_cash_flow":  _safe_float(info.get("freeCashflow")),
            "credit_rating":   None,   # not available via yfinance
            "market_cap":      _safe_float(info.get("marketCap")),
            "sector":          info.get("sector"),
        }

    async def get_etf_holdings(self, symbol: str) -> dict:
        # FALLBACK ONLY — not for production primary use
        """Return ETF metadata from ``ticker.funds_data`` (if available) and ``ticker.info``.

        Holdings source:
            ``ticker.funds_data.top_holdings`` (yfinance >= 0.2.18).
            Falls back to an empty list if ``funds_data`` is unavailable
            (e.g. the ticker is not a fund, or the yfinance version is older).

        Profile source (``ticker.info``):
            annualReportExpenseRatio → expense_ratio (e.g. 0.0009 for 0.09%)
            totalNetAssets           → aum (USD)
            longBusinessSummary      → scanned for "covered call" / "buy-write"

        Returns:
            { expense_ratio, aum, top_holdings, covered_call }
        """
        symbol = symbol.upper()

        def _fetch():
            t    = yf.Ticker(symbol)
            info = t.info

            # funds_data was added in yfinance 0.2.18; guard with try/except
            holdings_df = None
            try:
                fd = t.funds_data
                if fd is not None:
                    holdings_df = fd.top_holdings
            except Exception as e:
                logger.debug(f"funds_data unavailable for {symbol}: {e}")

            return info, holdings_df

        try:
            info, holdings_df = await asyncio.to_thread(_fetch)
        except Exception as e:
            raise ProviderError(
                f"yfinance error fetching ETF holdings for {symbol}: {e}"
            ) from e

        # --- top holdings ---
        top_holdings = []
        if holdings_df is not None and not holdings_df.empty:
            for holding_name, row in holdings_df.iterrows():
                try:
                    # top_holdings columns: "Symbol", "Holding Percent", etc.
                    ticker_sym = row.get("Symbol") if hasattr(row, "get") else None
                    weight_raw = (
                        row.get("Holding Percent")
                        if hasattr(row, "get")
                        else row["Holding Percent"]
                    )
                    top_holdings.append({
                        "ticker":     ticker_sym,
                        "name":       str(holding_name),
                        "weight_pct": round(float(weight_raw) * 100, 4)
                        if weight_raw is not None
                        else None,
                    })
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Skipping malformed ETF holding for {symbol}: {e}")
                    continue

        # --- expense_ratio and aum from info ---
        expense_ratio = _safe_float(info.get("annualReportExpenseRatio"))
        aum           = _safe_float(info.get("totalNetAssets"))

        # --- covered_call detection from description and fund name ---
        description = (info.get("longBusinessSummary") or "").lower()
        fund_name   = (info.get("longName") or info.get("shortName") or "").lower()
        covered_call = (
            "covered call" in description
            or "buy-write"  in description
            or "covered call" in fund_name
            or "buy-write"  in fund_name
        )

        logger.info(
            f"✅ yfinance fetched ETF holdings for {symbol} "
            f"({len(top_holdings)} positions)"
        )
        return {
            "expense_ratio": expense_ratio,
            "aum":           aum,
            "top_holdings":  top_holdings,
            "covered_call":  covered_call,
        }


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _safe_float(value) -> Optional[float]:
    """Return float(value), or None if value is None or non-numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_frequency(dates: list) -> Optional[str]:
    """Infer dividend payment frequency from a list of ex-dates.

    Computes the average gap in calendar days between consecutive dates
    and maps it to a human-readable frequency string.

    Thresholds:
        ≤ 45 days  → monthly
        ≤ 120 days → quarterly
        ≤ 240 days → semi-annually
        > 240 days → annually

    Returns None when fewer than two dates are provided.
    """
    if len(dates) < 2:
        return None
    sorted_dates = sorted(dates)
    gaps = [
        (sorted_dates[i + 1] - sorted_dates[i]).days
        for i in range(len(sorted_dates) - 1)
    ]
    avg_gap = sum(gaps) / len(gaps)
    if avg_gap <= 45:
        return "monthly"
    elif avg_gap <= 120:
        return "quarterly"
    elif avg_gap <= 240:
        return "semi-annually"
    return "annually"
