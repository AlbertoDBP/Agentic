"""
Broker Service — Abstract base provider.

Every broker integration must implement this interface. The broker-service
routes calls to the correct provider based on the account's `broker` field.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ── Shared data classes ────────────────────────────────────────────────────────

@dataclass
class ConnectionStatus:
    connected: bool
    broker: str
    account_id: Optional[str] = None
    account_label: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AccountInfo:
    broker: str
    account_id: str
    account_label: str
    account_type: str           # taxable | roth_ira | traditional_ira | etc.
    cash_balance: float         # settled cash available to trade
    buying_power: float         # margin/cash buying power
    portfolio_value: float      # total equity value
    currency: str = "USD"
    raw: dict = field(default_factory=dict)   # full broker response for audit


@dataclass
class BrokerPosition:
    symbol: str
    quantity: float
    avg_cost_basis: float
    current_price: float
    current_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    asset_type: str = "UNKNOWN"
    raw: dict = field(default_factory=dict)


@dataclass
class OrderRequest:
    symbol: str
    side: str               # buy | sell
    qty: float
    order_type: str         # market | limit | stop | stop_limit
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"   # day | gtc | ioc | fok
    client_order_id: Optional[str] = None
    note: Optional[str] = None


@dataclass
class OrderResult:
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: str
    qty: float
    order_type: str
    status: str             # accepted | pending | filled | cancelled | rejected
    filled_qty: float = 0.0
    filled_avg_price: Optional[float] = None
    limit_price: Optional[float] = None
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    broker: str = ""
    raw: dict = field(default_factory=dict)


# ── Abstract provider ─────────────────────────────────────────────────────────

class BaseBrokerProvider(ABC):
    """
    All broker integrations implement this interface.
    Instantiate with broker credentials; the service selects the right
    provider based on account.broker (e.g. 'alpaca', 'schwab').
    """

    BROKER_NAME: str = ""   # override in subclass, e.g. "alpaca"

    @abstractmethod
    async def test_connection(self) -> ConnectionStatus:
        """Verify credentials and return account identity."""

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Return cash balance, buying power, and portfolio value."""

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Return all open positions held at the broker."""

    @abstractmethod
    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Submit an order. Raises on rejection."""

    @abstractmethod
    async def get_order(self, order_id: str) -> OrderResult:
        """Retrieve current status of an order by broker order ID."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if cancelled."""
