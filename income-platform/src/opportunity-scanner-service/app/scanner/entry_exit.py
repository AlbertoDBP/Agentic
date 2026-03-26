# src/opportunity-scanner-service/app/scanner/entry_exit.py
"""
Agent 07 — Entry/Exit Price Engine

Computes concrete dollar entry and exit limit prices from cached market data.
All inputs come from platform_shared.market_data_cache — no new FMP calls.

Entry limit = min(technical_entry, yield_entry, nav_entry) — applicable signals only.
Exit limit  = min(technical_exit, yield_exit, nav_exit)   — applicable signals only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

NAV_ELIGIBLE_CLASSES = {"BDC", "MORTGAGE_REIT"}


class ZoneStatus(str, Enum):
    BELOW_ENTRY = "BELOW_ENTRY"   # price < entry_limit
    IN_ZONE     = "IN_ZONE"       # entry_limit ≤ price ≤ entry_limit × 1.03
    NEAR_ENTRY  = "NEAR_ENTRY"    # price ≤ entry_limit × 1.05
    ABOVE_ENTRY = "ABOVE_ENTRY"   # price > entry_limit × 1.05
    UNKNOWN     = "UNKNOWN"       # entry_limit is None


@dataclass
class EntryExitResult:
    entry_limit: Optional[float]
    exit_limit: Optional[float]
    current_price: Optional[float]
    pct_from_entry: Optional[float]
    zone_status: ZoneStatus
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_limit": self.entry_limit,
            "exit_limit": self.exit_limit,
            "current_price": self.current_price,
            "pct_from_entry": self.pct_from_entry,
            "zone_status": self.zone_status.value,
            "signals": self.signals,
        }


def _safe(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def compute_entry_exit(
    asset_class: str,
    price: Optional[float],
    support_level: Optional[float],
    sma_200: Optional[float],
    resistance_level: Optional[float],
    week_52_high: Optional[float],
    dividend_yield: Optional[float],   # percent, e.g. 6.5 = 6.5%
    nav_value: Optional[float],
) -> EntryExitResult:
    """Compute entry/exit limit prices and zone status for one ticker."""

    price           = _safe(price)
    support_level   = _safe(support_level)
    sma_200         = _safe(sma_200)
    resistance_level = _safe(resistance_level)
    week_52_high    = _safe(week_52_high)
    dividend_yield  = _safe(dividend_yield)
    nav_value       = _safe(nav_value)
    nav_eligible = asset_class in NAV_ELIGIBLE_CLASSES

    # ── Derived yield values ─────────────────────────────────────────────────
    annual_dividend: Optional[float] = None
    yield_entry_target: Optional[float] = None
    yield_exit_target: Optional[float] = None

    if price is not None and dividend_yield is not None:
        annual_dividend = price * (dividend_yield / 100.0)
        yield_entry_target = dividend_yield * 1.15   # proxy for historical high yield
        yield_exit_target  = dividend_yield * 0.85   # proxy for historical low yield

    # ── Entry signals ────────────────────────────────────────────────────────
    technical_entry: Optional[float] = None
    if support_level is not None or sma_200 is not None:
        candidates = []
        if support_level is not None:
            candidates.append(support_level)
        if sma_200 is not None:
            candidates.append(sma_200 * 1.01)
        technical_entry = max(candidates)

    yield_entry: Optional[float] = None
    if annual_dividend is not None and yield_entry_target is not None and yield_entry_target > 0:
        yield_entry = annual_dividend / (yield_entry_target / 100.0)

    nav_entry: Optional[float] = None
    if nav_eligible and nav_value is not None:
        nav_entry = nav_value * 0.95

    entry_signals = [s for s in [technical_entry, yield_entry, nav_entry] if s is not None]
    entry_limit = min(entry_signals) if entry_signals else None
    # Round entry_limit before computing pct_from_entry for consistency
    entry_limit = round(entry_limit, 2) if entry_limit is not None else None

    # ── Exit signals ─────────────────────────────────────────────────────────
    technical_exit: Optional[float] = None
    if resistance_level is not None or week_52_high is not None:
        candidates = []
        if resistance_level is not None:
            candidates.append(resistance_level)
        if week_52_high is not None:
            candidates.append(week_52_high * 0.95)
        technical_exit = min(candidates)

    yield_exit: Optional[float] = None
    if annual_dividend is not None and yield_exit_target is not None and yield_exit_target > 0:
        yield_exit = annual_dividend / (yield_exit_target / 100.0)

    nav_exit: Optional[float] = None
    if nav_eligible and nav_value is not None:
        nav_exit = nav_value * 1.05

    exit_signals = [s for s in [technical_exit, yield_exit, nav_exit] if s is not None]
    exit_limit = min(exit_signals) if exit_signals else None
    # Round exit_limit for consistency
    exit_limit = round(exit_limit, 2) if exit_limit is not None else None

    # ── Zone status ──────────────────────────────────────────────────────────
    pct_from_entry: Optional[float] = None
    if entry_limit is None:
        zone_status = ZoneStatus.UNKNOWN
    elif price is None:
        zone_status = ZoneStatus.UNKNOWN
    else:
        pct_from_entry = round((price - entry_limit) / entry_limit * 100.0, 2)
        if price < entry_limit:
            zone_status = ZoneStatus.BELOW_ENTRY
        elif price <= entry_limit * 1.03:
            zone_status = ZoneStatus.IN_ZONE
        elif price <= entry_limit * 1.05:
            zone_status = ZoneStatus.NEAR_ENTRY
        else:
            zone_status = ZoneStatus.ABOVE_ENTRY

    return EntryExitResult(
        entry_limit=entry_limit,
        exit_limit=exit_limit,
        current_price=price,
        pct_from_entry=pct_from_entry,
        zone_status=zone_status,
        signals={
            "technical_entry": round(technical_entry, 2) if technical_entry is not None else None,
            "yield_entry":     round(yield_entry, 2)     if yield_entry is not None else None,
            "nav_entry":       round(nav_entry, 2)       if nav_entry is not None else None,
            "technical_exit":  round(technical_exit, 2)  if technical_exit is not None else None,
            "yield_exit":      round(yield_exit, 2)      if yield_exit is not None else None,
            "nav_exit":        round(nav_exit, 2)        if nav_exit is not None else None,
        },
    )
