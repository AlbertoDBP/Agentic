# src/agent-14-data-quality/app/clients/fmp.py
"""FMP heal fetcher — fetches a single field for a single symbol."""
import logging
from typing import Any, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Maps field_name → (endpoint, response_key)
_FIELD_MAP: dict[str, tuple[str, str]] = {
    "price":                    ("quote",                    "price"),
    "week52_high":              ("quote",                    "yearHigh"),
    "week52_low":               ("quote",                    "yearLow"),
    "dividend_yield":           ("profile",                  "lastDiv"),
    "div_frequency":            ("profile",                  "companyName"),   # derived separately
    "sma_50":                   ("technical-indicator/sma",  "sma"),
    "sma_200":                  ("technical-indicator/sma",  "sma"),
    "rsi_14d":                  ("technical-indicator/rsi",  "rsi"),
    "payout_ratio":             ("ratios",                   "payoutRatio"),
    "nav_value":                ("etf-info",                 "navPrice"),
    "nav_discount_pct":         ("etf-info",                 "premium"),
    "interest_coverage_ratio":  ("ratios",                   "interestCoverage"),
    "debt_to_equity":           ("ratios",                   "debtEquityRatio"),
    "chowder_number":           ("profile",                  None),   # computed from dividends
    "consecutive_growth_yrs":   ("dividends-history",        None),  # computed from series
}


class FMPHealClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, endpoint: str, symbol: str, extra_params: dict = None) -> Optional[Any]:
        params = {"symbol": symbol.upper(), "apikey": self.api_key}
        if extra_params:
            params.update(extra_params)
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 429:
                    logger.warning(f"FMP rate limited for {symbol}/{endpoint}")
                    return None
                if resp.status_code == 401:
                    logger.error("FMP auth failed — check FMP_API_KEY")
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.warning(f"FMP timeout for {symbol}/{endpoint}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"FMP HTTP {e.response.status_code} for {symbol}/{endpoint}")
            return None
        except Exception as e:
            logger.error(f"FMP unexpected error for {symbol}/{endpoint}: {e}")
            return None

    def fetch_field(self, symbol: str, field_name: str) -> Optional[float]:
        """Return scalar value for field_name, or None if unavailable."""
        value, _ = self.fetch_field_with_diagnostic(symbol, field_name)
        return value

    def fetch_field_with_diagnostic(self, symbol: str, field_name: str) -> Tuple[Optional[float], dict]:
        if field_name not in _FIELD_MAP:
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"No FMP mapping for {field_name}"}

        endpoint, key = _FIELD_MAP[field_name]
        data = self._get(endpoint, symbol)

        if data is None:
            return None, {"code": "TICKER_NOT_FOUND", "detail": f"FMP returned no data for {symbol}"}

        # Normalise: FMP returns list for most endpoints
        row = data[0] if isinstance(data, list) and data else data
        if not row:
            return None, {"code": "TICKER_NOT_FOUND", "detail": f"Empty FMP response for {symbol}"}

        if key is None:
            # Field requires computed logic — not handled here
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"{field_name} requires computed extraction"}

        value = row.get(key)
        if value is None:
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"Key {key} absent in FMP response"}
        if value == 0:
            return 0.0, {"code": "ZERO_VALUE", "detail": f"FMP returned 0 for {field_name}"}

        try:
            return float(value), {}
        except (TypeError, ValueError):
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"Non-numeric value: {value!r}"}
