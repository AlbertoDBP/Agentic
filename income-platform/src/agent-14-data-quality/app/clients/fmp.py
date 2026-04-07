# src/agent-14-data-quality/app/clients/fmp.py
"""FMP heal fetcher — fetches a single field for a single symbol."""
import logging
from typing import Any, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Maps field_name → (endpoint, response_key)
# endpoint: FMP path relative to base_url; use "{symbol}" placeholder for path-param endpoints.
# response_key: dict key to extract from first response item; None = requires computed logic.
_FIELD_MAP: dict[str, tuple[str, str]] = {
    "price":                    ("quote",                        "price"),
    "week52_high":              ("quote",                        "yearHigh"),
    "week52_low":               ("quote",                        "yearLow"),
    "dividend_yield":           ("profile",                      "lastDiv"),
    "div_frequency":            ("profile",                      "companyName"),   # derived separately
    "sma_50":                   ("technical-indicator/sma",      "sma"),
    "sma_200":                  ("technical-indicator/sma",      "sma"),
    "rsi_14d":                  ("technical-indicator/rsi",      "rsi"),
    "payout_ratio":             ("ratios",                       "payoutRatio"),
    "nav_value":                ("etf-info",                     "navPrice"),
    "nav_discount_pct":         ("etf-info",                     "premium"),
    "interest_coverage_ratio":  ("ratios",                       "interestCoverage"),
    "debt_to_equity":           ("ratios",                       "debtEquityRatio"),
    "return_on_equity":         ("ratios",                       "returnOnEquity"),
    "net_debt_ebitda":          ("key-metrics",                  "netDebtToEBITDA"),
    "price_to_book":            ("ratios",                       "priceToBookRatio"),
    "profit_margin":            ("ratios",                       "netProfitMargin"),
    "free_cash_flow_yield":     ("key-metrics",                  "freeCashFlowYield"),
    "pe_ratio":                 ("ratios",                       "priceEarningsRatio"),
    "forward_pe":               ("ratios-ttm",                   "peRatioTTM"),
    # credit_rating uses a path-param endpoint; symbol is embedded in the URL.
    "credit_rating":            ("rating/{symbol}",              "rating"),
    # Computed fields — healer escalates these; market-data-service sync handles them.
    "chowder_number":           ("profile",                      None),
    "consecutive_growth_yrs":   ("dividends-history",            None),
    "yield_5yr_avg":            ("dividends",                    None),
    "insider_ownership_pct":    ("insider-ownership",            None),
}

# Endpoints where the symbol is in the URL path (not as a query param).
_PATH_SYMBOL_ENDPOINTS: frozenset[str] = frozenset({"rating/{symbol}"})

# Fields that return a text value rather than a numeric one.
_STRING_FIELDS: frozenset[str] = frozenset({"credit_rating"})


class FMPHealClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, endpoint: str, symbol: str, extra_params: dict = None) -> Optional[Any]:
        sym_upper = symbol.upper()
        # Build URL — substitute {symbol} in path-param endpoints.
        if "{symbol}" in endpoint:
            url = f"{self.base_url}/{endpoint.lstrip('/').format(symbol=sym_upper)}"
            params = {"apikey": self.api_key}
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            params = {"symbol": sym_upper, "apikey": self.api_key}
        if extra_params:
            params.update(extra_params)
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

    def fetch_field(self, symbol: str, field_name: str) -> Optional[Any]:
        """Return scalar value for field_name, or None if unavailable."""
        value, _ = self.fetch_field_with_diagnostic(symbol, field_name)
        return value

    def fetch_field_with_diagnostic(self, symbol: str, field_name: str) -> Tuple[Optional[Any], dict]:
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

        # String fields — return as-is (credit_rating etc.)
        if field_name in _STRING_FIELDS:
            s = str(value).strip()
            if not s:
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"Empty string for {field_name}"}
            return s, {}

        if value == 0:
            return 0.0, {"code": "ZERO_VALUE", "detail": f"FMP returned 0 for {field_name}"}

        try:
            return float(value), {}
        except (TypeError, ValueError):
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"Non-numeric value: {value!r}"}
