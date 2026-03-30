# app/scoring/portfolio_health.py
"""
Portfolio Health Layer — two outputs, never collapsed.

Output A: position-weighted aggregate HHS. Gate-failed/stale excluded but counted.
Output B: independent metrics panel — NAA Yield, Total Return, HHI, placeholders.

Total Return and NAA Yield use portfolio accounting data (original_cost,
current_value, income_received, tax_drag) provided by the API caller.
Sharpe/Sortino/VaR: placeholder None — wired in Phase 3 via scenario-simulation-service.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from app.scoring.hhs_wrapper import HHSResult, HHSStatus
from app.scoring.naa_yield import NAAYieldResult


@dataclass
class HoldingInput:
    ticker: str
    hhs: HHSResult
    naa: NAAYieldResult
    position_value: float
    original_cost: float
    current_value: float
    income_received: float
    tax_drag: float


@dataclass
class PortfolioHealthResult:
    # Output A
    aggregate_hhs: Optional[float]
    scored_holding_count: int
    excluded_holding_count: int
    unsafe_count: int
    unsafe_tickers: list[str]
    gate_fail_count: int
    gate_fail_tickers: list[str] = field(default_factory=list)
    insufficient_data_count: int = 0
    stale_count: int = 0
    # Output B
    portfolio_naa_yield_pct: float = 0.0
    portfolio_naa_pre_tax_flag: bool = False
    total_return_pct: float = 0.0
    hhi: float = 0.0
    concentration_flags: list[str] = field(default_factory=list)
    sharpe: Optional[float] = None   # Phase 3
    sortino: Optional[float] = None  # Phase 3
    var_95: Optional[float] = None   # Phase 3


class PortfolioHealthCalculator:

    def __init__(self, hhi_flag_threshold: float = 0.10):
        self.hhi_flag_threshold = hhi_flag_threshold

    def compute(self, holdings: list[HoldingInput]) -> PortfolioHealthResult:
        scored  = [h for h in holdings if h.hhs.status == HHSStatus.SCORED and h.hhs.hhs_score is not None]
        fails   = [h for h in holdings if h.hhs.status == HHSStatus.QUALITY_GATE_FAIL]
        insuf   = [h for h in holdings if h.hhs.status == HHSStatus.INSUFFICIENT_DATA]
        stale   = [h for h in holdings if h.hhs.status == HHSStatus.STALE]
        unsafe  = [h for h in scored if h.hhs.unsafe]

        # Output A — Aggregate HHS
        total_val = sum(h.position_value for h in scored)
        aggregate_hhs = (
            sum(h.hhs.hhs_score * (h.position_value / total_val) for h in scored)
            if total_val > 0 else None
        )

        # Output B — NAA Yield (position-weighted across all holdings)
        all_invested = sum(h.naa.total_invested for h in holdings)
        naa_yield = (
            sum(h.naa.naa_yield_pct * (h.naa.total_invested / all_invested) for h in holdings)
            if all_invested > 0 else 0.0
        )
        pre_tax = any(h.naa.pre_tax_flag for h in holdings)

        # Total Return
        cost    = sum(h.original_cost for h in holdings)
        current = sum(h.current_value for h in holdings)
        income  = sum(h.income_received for h in holdings)
        taxes   = sum(h.tax_drag for h in holdings)
        total_return = ((current - cost + income - taxes) / cost * 100) if cost > 0 else 0.0

        # HHI
        all_val = sum(h.position_value for h in holdings)
        hhi, flags = 0.0, []
        if all_val > 0:
            for h in holdings:
                w = h.position_value / all_val
                hhi += w ** 2
                if w > self.hhi_flag_threshold:
                    flags.append(h.ticker)

        return PortfolioHealthResult(
            aggregate_hhs=round(aggregate_hhs, 2) if aggregate_hhs is not None else None,
            scored_holding_count=len(scored),
            excluded_holding_count=len(fails) + len(insuf) + len(stale),
            unsafe_count=len(unsafe),
            unsafe_tickers=[h.ticker for h in unsafe],
            gate_fail_count=len(fails),
            gate_fail_tickers=[h.ticker for h in fails],
            insufficient_data_count=len(insuf),
            stale_count=len(stale),
            portfolio_naa_yield_pct=round(naa_yield, 4),
            portfolio_naa_pre_tax_flag=pre_tax,
            total_return_pct=round(total_return, 4),
            hhi=round(hhi, 6),
            concentration_flags=flags,
        )
