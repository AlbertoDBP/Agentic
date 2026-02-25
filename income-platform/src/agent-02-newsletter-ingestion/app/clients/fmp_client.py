"""
Agent 02 — Newsletter Ingestion Service
Client: Financial Modeling Prep (FMP) API wrapper

Provides market truth for the Intelligence Flow backtest pipeline:
  - Historical EOD price at T+30 and T+90 after recommendation publish date
  - Dividend history for dividend cut detection in the backtest window
  - Fundamental ratios for credit proxy (interest coverage, debt/equity)

FMP base URL: https://financialmodelingprep.com/stable
API key set via settings.fmp_api_key

Rate limiting: configurable via settings.fmp_calls_per_minute (default 30).
"""
import time
import logging
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = settings.fmp_base_url.rstrip("/")

_last_call_times: list[float] = []


def _rate_limit():
    """Sliding-window rate limiter: max fmp_calls_per_minute calls per 60s."""
    global _last_call_times
    now = time.time()
    window = 60.0
    _last_call_times = [t for t in _last_call_times if now - t < window]
    if len(_last_call_times) >= settings.fmp_calls_per_minute:
        sleep_for = window - (now - _last_call_times[0]) + 0.1
        logger.debug(f"FMP rate limit reached — sleeping {sleep_for:.1f}s")
        time.sleep(sleep_for)
    _last_call_times.append(time.time())


def _get(endpoint: str, params: dict = None) -> Optional[dict | list]:
    """
    Execute a GET request against the FMP stable API.
    Injects apikey automatically. Returns parsed JSON or None on failure.
    """
    params = params or {}
    params["apikey"] = settings.fmp_api_key
    url = f"{_BASE_URL}/{endpoint.lstrip('/')}"

    try:
        _rate_limit()
        with httpx.Client(timeout=settings.fmp_request_timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"FMP HTTP error {e.response.status_code} for {endpoint}: "
                     f"{e.response.text[:200]}")
    except httpx.TimeoutException:
        logger.error(f"FMP timeout for {endpoint}")
    except Exception as e:
        logger.error(f"FMP unexpected error for {endpoint}: {e}")

    return None


# ── Price History ─────────────────────────────────────────────────────────────

def _date_str(dt: datetime) -> str:
    """Format datetime as YYYY-MM-DD for FMP query params."""
    return dt.strftime("%Y-%m-%d")


def fetch_price_at_date(ticker: str, target_date: datetime) -> Optional[float]:
    """
    Return the closing price of `ticker` on or immediately after `target_date`.

    Uses /historical-price-eod/full with a ±5 day window around target to
    handle weekends and market holidays. Returns None if no data in window.

    Args:
        ticker:      Stock ticker symbol (uppercase).
        target_date: Target datetime (timezone-aware UTC).

    Returns:
        Closing price as float, or None.
    """
    # Fetch a 10-day window centred just after target_date to catch weekends
    from_dt = target_date - timedelta(days=1)
    to_dt = target_date + timedelta(days=7)

    data = _get(
        f"historical-price-eod/full",
        params={
            "symbol": ticker.upper(),
            "from": _date_str(from_dt),
            "to": _date_str(to_dt),
        },
    )

    if not data:
        return None

    # FMP returns {"symbol": "...", "historical": [{date, close, ...}, ...]}
    # or a plain list depending on endpoint version — handle both
    historical = data if isinstance(data, list) else data.get("historical", [])

    if not historical:
        logger.debug(f"FMP: no price history for {ticker} around {_date_str(target_date)}")
        return None

    # Sort ascending by date, find first trading day >= target_date
    target_date_only = target_date.date()
    candidates = []
    for row in historical:
        try:
            row_date = date.fromisoformat(row["date"])
            if row_date >= target_date_only:
                candidates.append((row_date, float(row["close"])))
        except (KeyError, ValueError, TypeError):
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    price = candidates[0][1]
    logger.debug(f"FMP price for {ticker} at {_date_str(target_date)}: {price}")
    return price


def fetch_price_at_t30_t90(
    ticker: str,
    published_at: datetime,
) -> tuple[Optional[float], Optional[float]]:
    """
    Fetch closing price at T+30 and T+90 days after recommendation publish date.

    Returns:
        (price_at_t30, price_at_t90) — either value may be None if unavailable.
    """
    t30 = published_at + timedelta(days=30)
    t90 = published_at + timedelta(days=90)

    # Only fetch T+90 if enough time has passed (avoid calling FMP for future dates)
    now = datetime.now(timezone.utc)
    price_t30 = fetch_price_at_date(ticker, t30) if now >= t30 else None
    price_t90 = fetch_price_at_date(ticker, t90) if now >= t90 else None

    return price_t30, price_t90


# ── Dividend History ──────────────────────────────────────────────────────────

def fetch_dividends_in_window(
    ticker: str,
    from_date: datetime,
    to_date: datetime,
) -> list[dict]:
    """
    Return dividend payment records for `ticker` between from_date and to_date.

    Each record: {"date": "YYYY-MM-DD", "dividend": float}
    Returns empty list if no data or on error.
    """
    data = _get(
        "dividends-historical",
        params={"symbol": ticker.upper()},
    )

    if not data:
        return []

    # FMP returns {"symbol": "...", "historical": [{date, dividend, ...}, ...]}
    historical = data if isinstance(data, list) else data.get("historical", [])

    from_date_only = from_date.date()
    to_date_only = to_date.date()

    results = []
    for row in historical:
        try:
            row_date = date.fromisoformat(row.get("date", ""))
            if from_date_only <= row_date <= to_date_only:
                div_amount = float(row.get("dividend", row.get("adjDividend", 0)))
                results.append({"date": str(row_date), "dividend": div_amount})
        except (KeyError, ValueError, TypeError):
            continue

    logger.debug(
        f"FMP dividends for {ticker} "
        f"[{from_date_only} → {to_date_only}]: {len(results)} records"
    )
    return results


def detect_dividend_cut(
    ticker: str,
    published_at: datetime,
    lookback_days: int = 90,
) -> tuple[bool, Optional[datetime]]:
    """
    Detect whether a dividend cut occurred within `lookback_days` after
    the recommendation publish date.

    Logic:
      1. Fetch dividends in [published_at - 180d, published_at + lookback_days]
      2. Compute the median dividend amount in the 180 days BEFORE publish_at
         as the "baseline" payment
      3. Flag a cut if any payment in the lookback window is < baseline * 0.9
         (10% reduction threshold)

    Returns:
        (cut_occurred: bool, cut_date: Optional[datetime])
    """
    pre_window_start = published_at - timedelta(days=180)
    post_window_end = published_at + timedelta(days=lookback_days)

    all_divs = fetch_dividends_in_window(ticker, pre_window_start, post_window_end)
    if not all_divs:
        return False, None

    # Split into pre-publish (baseline) and post-publish (observation window)
    pre_publish = [d for d in all_divs if d["date"] < str(published_at.date())]
    post_publish = [d for d in all_divs if d["date"] >= str(published_at.date())]

    if not pre_publish or not post_publish:
        return False, None

    # Baseline: median of pre-publish payments
    pre_amounts = sorted([d["dividend"] for d in pre_publish if d["dividend"] > 0])
    if not pre_amounts:
        return False, None

    median_idx = len(pre_amounts) // 2
    baseline = pre_amounts[median_idx]
    cut_threshold = baseline * 0.9

    # Check post-publish window for cuts
    post_sorted = sorted(post_publish, key=lambda x: x["date"])
    for row in post_sorted:
        if row["dividend"] < cut_threshold:
            try:
                cut_dt = datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc)
            except ValueError:
                cut_dt = None
            logger.info(
                f"Dividend cut detected for {ticker}: "
                f"baseline={baseline:.4f} → actual={row['dividend']:.4f} "
                f"on {row['date']}"
            )
            return True, cut_dt

    return False, None


# ── Fundamental Ratios (Credit Proxy) ─────────────────────────────────────────

def fetch_ratios(ticker: str) -> Optional[dict]:
    """
    Fetch key fundamental ratios for credit proxy evaluation.

    Returns dict with:
      - interest_coverage_ratio: float or None
      - debt_equity_ratio: float or None
      - pe_ratio: float or None

    Used by Agent 03 credit safety grade priority chain when SA grade
    is unavailable.
    """
    data = _get(f"ratios/{ticker.upper()}")

    if not data:
        return None

    # FMP returns list; take the most recent entry
    rows = data if isinstance(data, list) else [data]
    if not rows:
        return None

    row = rows[0]
    try:
        return {
            "interest_coverage_ratio": _safe_float(
                row.get("interestCoverageRatio") or row.get("interest_coverage_ratio")
            ),
            "debt_equity_ratio": _safe_float(
                row.get("debtEquityRatio") or row.get("debt_equity_ratio")
            ),
            "pe_ratio": _safe_float(
                row.get("peRatio") or row.get("pe_ratio")
            ),
        }
    except Exception as e:
        logger.warning(f"FMP ratios parse error for {ticker}: {e}")
        return None


def _safe_float(value) -> Optional[float]:
    """Convert value to float, returning None on failure."""
    if value is None:
        return None
    try:
        result = float(value)
        return None if (result != result) else result  # NaN check
    except (TypeError, ValueError):
        return None
