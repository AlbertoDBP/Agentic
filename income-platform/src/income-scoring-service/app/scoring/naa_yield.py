# app/scoring/naa_yield.py
"""
NAA Yield — Net After-All Yield.

Formula: (Gross Dividends - Annual Fee Drag - Annual Tax Drag) / Total Invested

All monetary inputs (gross dividends, fee drag, tax drag, total_invested)
come from the API caller's request payload — portfolio accounting data,
not market data. The caller is responsible for annualizing income_received
and sourcing tax drag from the Tax Optimization Service.

If tax data is unavailable (annual_tax_drag=None):
  - pre_tax_flag = True (shown in UI as "Yield shown pre-tax")
  - tax_drag treated as 0 (optimistic, not pessimistic)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class TaxProfile:
    roc_pct: float        # 0.0–1.0 — Return of Capital (0% current tax)
    qualified_pct: float
    ordinary_pct: float
    qualified_rate: float
    ordinary_rate: float


@dataclass
class NAAYieldResult:
    gross_annual_dividends: float
    annual_fee_drag: float
    annual_tax_drag: float
    net_income: float
    total_invested: float
    naa_yield_pct: float
    pre_tax_flag: bool


class NAAYieldCalculator:

    def compute(
        self,
        gross_annual_dividends: float,
        annual_fee_drag: float,
        annual_tax_drag: Optional[float],
        total_invested: float,
    ) -> NAAYieldResult:
        pre_tax_flag = annual_tax_drag is None
        tax = annual_tax_drag if annual_tax_drag is not None else 0.0
        net = max(0.0, gross_annual_dividends - annual_fee_drag - tax)
        pct = (net / total_invested * 100) if total_invested > 0 else 0.0
        return NAAYieldResult(
            gross_annual_dividends=gross_annual_dividends,
            annual_fee_drag=annual_fee_drag,
            annual_tax_drag=tax,
            net_income=net,
            total_invested=total_invested,
            naa_yield_pct=round(pct, 4),
            pre_tax_flag=pre_tax_flag,
        )

    @staticmethod
    def estimate_tax_drag(gross: float, profile: TaxProfile) -> float:
        """Estimate annual tax drag from income character and bracket rates."""
        return round(
            gross * profile.qualified_pct * profile.qualified_rate
            + gross * profile.ordinary_pct * profile.ordinary_rate,
            4,
        )
