# src/agent-14-data-quality/app/clients/massive.py
"""MASSIVE (Polygon.io) heal fetcher — real-time prices and technicals."""
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class MASSIVEHealClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict = None) -> Tuple[Optional[dict], Optional[dict]]:
        """Returns (data, diagnostic_or_None)."""
        all_params = {"apiKey": self.api_key}
        if params:
            all_params.update(params)
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=all_params)
                if resp.status_code == 429:
                    return None, {"code": "RATE_LIMITED", "detail": "Polygon.io 429"}
                if resp.status_code == 403:
                    return None, {"code": "AUTH_ERROR", "detail": "Polygon.io 403 — check MASSIVE_KEY"}
                if resp.status_code == 404:
                    return None, {"code": "TICKER_NOT_FOUND", "detail": f"Polygon.io 404 for {path}"}
                resp.raise_for_status()
                return resp.json(), None
        except httpx.TimeoutException:
            return None, {"code": "STALE_DATA", "detail": "Polygon.io timeout"}
        except Exception as e:
            return None, {"code": "TICKER_NOT_FOUND", "detail": str(e)}

    def fetch_field(self, symbol: str, field_name: str) -> Optional[float]:
        value, _ = self.fetch_field_with_diagnostic(symbol, field_name)
        return value

    def fetch_field_with_diagnostic(self, symbol: str, field_name: str) -> Tuple[Optional[float], dict]:
        sym = symbol.upper()

        if field_name == "price":
            data, diag = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{sym}")
            if diag:
                return None, diag
            try:
                value = data["ticker"]["day"]["c"]
                return float(value), {}
            except (KeyError, TypeError):
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": "price not in snapshot"}

        if field_name in ("sma_50", "sma_200"):
            window = 50 if field_name == "sma_50" else 200
            data, diag = self._get(
                f"/v1/indicators/sma/{sym}",
                params={"timespan": "day", "window": window, "limit": 1},
            )
            if diag:
                return None, diag
            try:
                value = data["results"]["values"][0]["value"]
                return float(value), {}
            except (KeyError, TypeError, IndexError):
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": "SMA not in response"}

        if field_name == "rsi_14d":
            data, diag = self._get(
                f"/v1/indicators/rsi/{sym}",
                params={"timespan": "day", "window": 14, "limit": 1},
            )
            if diag:
                return None, diag
            try:
                value = data["results"]["values"][0]["value"]
                return float(value), {}
            except (KeyError, TypeError, IndexError):
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": "RSI not in response"}

        if field_name in ("week52_high", "week52_low"):
            from datetime import date, timedelta
            end = date.today().isoformat()
            start = (date.today() - timedelta(days=365)).isoformat()
            data, diag = self._get(
                f"/v2/aggs/ticker/{sym}/range/1/day/{start}/{end}",
                params={"adjusted": "true", "limit": 365},
            )
            if diag:
                return None, diag
            try:
                results = data.get("results", [])
                if not results:
                    return None, {"code": "TICKER_NOT_FOUND", "detail": "No agg results"}
                if field_name == "week52_high":
                    return float(max(r["h"] for r in results)), {}
                else:
                    return float(min(r["l"] for r in results)), {}
            except Exception as e:
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": str(e)}

        return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"MASSIVE has no mapping for {field_name}"}
