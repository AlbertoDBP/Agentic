"""
Broker Service — Alpaca provider.

Uses Alpaca's Trading API v2 directly via httpx (no SDK dependency).
Supports both paper (https://paper-api.alpaca.markets) and live endpoints.

Docs: https://docs.alpaca.markets/reference/getaccount
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.providers.base import (
    AccountInfo,
    BaseBrokerProvider,
    BrokerPosition,
    ConnectionStatus,
    OrderRequest,
    OrderResult,
)

logger = logging.getLogger(__name__)

# Alpaca account type strings → platform account_type enum
_ALPACA_ACCOUNT_TYPE_MAP = {
    "MARGIN": "taxable",
    "CASH": "taxable",
    "PAPER": "taxable",
}


class AlpacaProvider(BaseBrokerProvider):
    """Alpaca Trading API v2 integration."""

    BROKER_NAME = "alpaca"

    def __init__(self, api_key: str, secret_key: str, base_url: str):
        if not api_key or not secret_key:
            raise ValueError("Alpaca API key and secret key are required")
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self._headers, json=body)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str) -> bool:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(url, headers=self._headers)
        return resp.status_code in (200, 204)

    # ── Provider interface ────────────────────────────────────────────────────

    async def test_connection(self) -> ConnectionStatus:
        try:
            data = await self._get("/v2/account")
            return ConnectionStatus(
                connected=True,
                broker=self.BROKER_NAME,
                account_id=data.get("id"),
                account_label=data.get("account_number"),
            )
        except Exception as exc:
            logger.warning("Alpaca connection test failed: %s", exc)
            return ConnectionStatus(
                connected=False,
                broker=self.BROKER_NAME,
                error=str(exc),
            )

    async def get_account(self) -> AccountInfo:
        data = await self._get("/v2/account")
        account_type = _ALPACA_ACCOUNT_TYPE_MAP.get(
            data.get("account_type", "").upper(), "taxable"
        )
        return AccountInfo(
            broker=self.BROKER_NAME,
            account_id=data["id"],
            account_label=data.get("account_number", data["id"]),
            account_type=account_type,
            cash_balance=float(data.get("cash", 0) or 0),
            buying_power=float(data.get("buying_power", 0) or 0),
            portfolio_value=float(data.get("portfolio_value", 0) or 0),
            currency="USD",
            raw=data,
        )

    async def get_positions(self) -> list[BrokerPosition]:
        rows = await self._get("/v2/positions")
        positions = []
        for p in rows:
            try:
                qty = float(p.get("qty", 0) or 0)
                avg_cb = float(p.get("avg_entry_price", 0) or 0)
                cur_price = float(p.get("current_price", 0) or 0)
                market_val = float(p.get("market_value", 0) or 0)
                unreal_pl = float(p.get("unrealized_pl", 0) or 0)
                unreal_plpct = float(p.get("unrealized_plpc", 0) or 0) * 100

                # Alpaca asset_class: us_equity | crypto | etc.
                raw_class = p.get("asset_class", "us_equity")
                asset_type = "ETF" if raw_class == "us_equity" else raw_class.upper()

                positions.append(BrokerPosition(
                    symbol=p["symbol"].upper(),
                    quantity=qty,
                    avg_cost_basis=avg_cb,
                    current_price=cur_price,
                    current_value=market_val,
                    unrealized_pl=unreal_pl,
                    unrealized_pl_pct=unreal_plpct,
                    asset_type=asset_type,
                    raw=p,
                ))
            except Exception as exc:
                logger.warning("Skipping Alpaca position %s: %s", p.get("symbol"), exc)
        return positions

    async def place_order(self, req: OrderRequest) -> OrderResult:
        body: dict = {
            "symbol": req.symbol.upper(),
            "qty": str(req.qty),
            "side": req.side.lower(),
            "type": req.order_type.lower(),
            "time_in_force": req.time_in_force.lower(),
        }
        if req.limit_price is not None:
            body["limit_price"] = str(req.limit_price)
        if req.stop_price is not None:
            body["stop_price"] = str(req.stop_price)
        if req.client_order_id:
            body["client_order_id"] = req.client_order_id

        data = await self._post("/v2/orders", body)
        return self._parse_order(data)

    async def get_order(self, order_id: str) -> OrderResult:
        data = await self._get(f"/v2/orders/{order_id}")
        return self._parse_order(data)

    async def cancel_order(self, order_id: str) -> bool:
        return await self._delete(f"/v2/orders/{order_id}")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse_order(self, data: dict) -> OrderResult:
        filled_qty = float(data.get("filled_qty", 0) or 0)
        filled_avg = data.get("filled_avg_price")
        return OrderResult(
            order_id=data["id"],
            client_order_id=data.get("client_order_id"),
            symbol=data.get("symbol", "").upper(),
            side=data.get("side", ""),
            qty=float(data.get("qty", 0) or 0),
            order_type=data.get("type", ""),
            status=data.get("status", ""),
            filled_qty=filled_qty,
            filled_avg_price=float(filled_avg) if filled_avg else None,
            limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
            submitted_at=data.get("submitted_at"),
            filled_at=data.get("filled_at"),
            broker=self.BROKER_NAME,
            raw=data,
        )
