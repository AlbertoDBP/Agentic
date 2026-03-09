"""
Agent 05 — Tax Optimization Service
Tax Calculator — computes federal, state, and NIIT burden on distributions.
Uses 2024 IRS brackets; updated annually via constant tables (no external API).
"""
from __future__ import annotations

import logging
from typing import Optional

from app.models import (
    AccountType,
    AssetClass,
    FilingStatus,
    TaxBracketDetail,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxTreatment,
)
from app.tax.profiler import build_tax_profile, _PROFILE_MAP
from app.models import TaxProfileRequest

logger = logging.getLogger(__name__)


# ─── 2024 Federal ordinary income brackets ────────────────────────────────────
# (taxable_income_threshold, rate)
_ORDINARY_BRACKETS: dict[FilingStatus, list[tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (609_350, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.MARRIED_JOINT: [
        (23_200, 0.10),
        (94_300, 0.12),
        (201_050, 0.22),
        (383_900, 0.24),
        (487_450, 0.32),
        (731_200, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.MARRIED_SEPARATE: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (365_600, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (16_550, 0.10),
        (63_100, 0.12),
        (100_500, 0.22),
        (191_950, 0.24),
        (243_700, 0.32),
        (609_350, 0.35),
        (float("inf"), 0.37),
    ],
}

# 2024 qualified dividend / LTCG brackets
_QUALIFIED_BRACKETS: dict[FilingStatus, list[tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (47_025, 0.00),
        (518_900, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.MARRIED_JOINT: [
        (94_050, 0.00),
        (583_750, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.MARRIED_SEPARATE: [
        (47_025, 0.00),
        (291_850, 0.15),
        (float("inf"), 0.20),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (63_000, 0.00),
        (551_350, 0.15),
        (float("inf"), 0.20),
    ],
}

# NIIT threshold (income above this amount subject to 3.8%)
_NIIT_THRESHOLD: dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 200_000,
    FilingStatus.MARRIED_JOINT: 250_000,
    FilingStatus.MARRIED_SEPARATE: 125_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
}

# Flat state income tax rates (approximations; updated annually)
# Values represent marginal rate on investment income for top bracket
_STATE_RATES: dict[str, float] = {
    "AL": 0.05, "AK": 0.00, "AZ": 0.025, "AR": 0.039, "CA": 0.133,
    "CO": 0.044, "CT": 0.069, "DE": 0.066, "FL": 0.00, "GA": 0.055,
    "HI": 0.11, "ID": 0.058, "IL": 0.0495, "IN": 0.031, "IA": 0.06,
    "KS": 0.057, "KY": 0.045, "LA": 0.043, "ME": 0.071, "MD": 0.0575,
    "MA": 0.05, "MI": 0.0425, "MN": 0.0985, "MS": 0.05, "MO": 0.048,
    "MT": 0.069, "NE": 0.0664, "NV": 0.00, "NH": 0.00, "NJ": 0.1075,
    "NM": 0.059, "NY": 0.109, "NC": 0.045, "ND": 0.029, "OH": 0.039,
    "OK": 0.047, "OR": 0.099, "PA": 0.0307, "RI": 0.0599, "SC": 0.065,
    "SD": 0.00, "TN": 0.00, "TX": 0.00, "UT": 0.048, "VT": 0.0875,
    "VA": 0.0575, "WA": 0.00, "WV": 0.065, "WI": 0.0765, "WY": 0.00,
    "DC": 0.1075,
}


def _marginal_rate(income: float, brackets: list[tuple[float, float]]) -> float:
    """Return the marginal rate for the given income level."""
    prev_threshold = 0.0
    for threshold, rate in brackets:
        if income <= threshold:
            return rate
        prev_threshold = threshold
    return brackets[-1][1]


def _niit_applicable(income: float, filing: FilingStatus) -> bool:
    return income > _NIIT_THRESHOLD.get(filing, 200_000)


def _ordinary_rate(income: float, filing: FilingStatus) -> float:
    return _marginal_rate(income, _ORDINARY_BRACKETS[filing])


def _qualified_rate(income: float, filing: FilingStatus) -> float:
    return _marginal_rate(income, _QUALIFIED_BRACKETS[filing])


def _state_rate(state_code: Optional[str]) -> float:
    if not state_code:
        return 0.0
    return _STATE_RATES.get(state_code.upper(), 0.05)


def _tax_treatment_for_class(asset_class: AssetClass) -> TaxTreatment:
    return _PROFILE_MAP.get(asset_class, _PROFILE_MAP[AssetClass.UNKNOWN])["primary"]


def _is_tax_sheltered(account_type: AccountType) -> bool:
    return account_type in (AccountType.TRAD_IRA, AccountType.ROTH_IRA,
                            AccountType.HSA, AccountType.FOUR01K)


async def calculate_tax_burden(request: TaxCalculationRequest) -> TaxCalculationResponse:
    """Compute the net-of-tax distribution and effective rate."""
    notes: list[str] = []

    # Short-circuit for tax-sheltered accounts
    if _is_tax_sheltered(request.account_type):
        notes.append(
            f"Account type {request.account_type} is tax-sheltered; "
            "distributions not taxed at distribution time."
        )
        return TaxCalculationResponse(
            symbol=request.symbol,
            gross_distribution=request.distribution_amount,
            federal_tax_owed=0.0,
            state_tax_owed=0.0,
            niit_owed=0.0,
            total_tax_owed=0.0,
            net_distribution=request.distribution_amount,
            effective_tax_rate=0.0,
            after_tax_yield_uplift=0.0,
            bracket_detail=[],
            notes=notes,
        )

    # Resolve asset class via profiler (handles fallback)
    profile = await build_tax_profile(
        TaxProfileRequest(
            symbol=request.symbol,
            asset_class=request.asset_class,
            annual_income=request.annual_income,
            filing_status=request.filing_status,
            state_code=request.state_code,
            account_type=request.account_type,
        )
    )
    if profile.asset_class_fallback:
        notes.append("Asset class fallback to ORDINARY_INCOME applied.")

    treatment = profile.primary_tax_treatment
    income = request.annual_income
    dist = request.distribution_amount
    filing = request.filing_status
    state = _state_rate(request.state_code)

    # Determine federal rate based on treatment
    use_qualified = treatment in (
        TaxTreatment.QUALIFIED_DIVIDEND,
        TaxTreatment.CAPITAL_GAIN_LONG,
        TaxTreatment.SECTION_1256_60_40,
    )

    if treatment == TaxTreatment.TAX_EXEMPT:
        fed_rate = 0.0
        notes.append("Federal tax-exempt income (e.g., municipal bond ETF).")
    elif treatment == TaxTreatment.RETURN_OF_CAPITAL:
        fed_rate = 0.0
        notes.append(
            "Return of capital is not taxed at distribution; it reduces cost basis."
        )
    elif treatment == TaxTreatment.SECTION_1256_60_40:
        # 60% LTCG + 40% short-term blended
        ltcg_rate = _qualified_rate(income, filing)
        st_rate = _ordinary_rate(income, filing)
        fed_rate = 0.60 * ltcg_rate + 0.40 * st_rate
        notes.append(
            f"Section 1256 60/40 blended rate applied "
            f"(60% LTCG @ {ltcg_rate:.1%} + 40% ST @ {st_rate:.1%})."
        )
    elif use_qualified:
        fed_rate = _qualified_rate(income, filing)
    else:
        fed_rate = _ordinary_rate(income, filing)

    # NIIT — applies to investment income for ordinary and qualified treatment
    niit = 0.0
    niit_flag = False
    if treatment not in (TaxTreatment.TAX_EXEMPT, TaxTreatment.RETURN_OF_CAPITAL,
                          TaxTreatment.MLP_DISTRIBUTION):
        if _niit_applicable(income, filing):
            niit = dist * 0.038
            niit_flag = True

    # MLP/REIT — often mostly ROC; simplify to ordinary on ~30% and ROC on 70%
    if treatment in (TaxTreatment.MLP_DISTRIBUTION, TaxTreatment.REIT_DISTRIBUTION):
        taxable_fraction = 0.30
        fed_rate = _ordinary_rate(income, filing) * taxable_fraction
        notes.append(
            "Approximately 70% of distribution assumed to be return of capital "
            f"(taxable fraction: {taxable_fraction:.0%} of ordinary rate)."
        )

    federal_tax = dist * fed_rate
    state_tax = dist * state
    total_tax = federal_tax + state_tax + niit
    net_dist = dist - total_tax
    effective_rate = total_tax / dist if dist > 0 else 0.0

    # Uplift vs treating as pure ordinary income baseline
    ordinary_baseline = (
        _ordinary_rate(income, filing) + state + (0.038 if _niit_applicable(income, filing) else 0)
    ) * dist
    uplift = (ordinary_baseline - total_tax) / dist if dist > 0 else 0.0

    bracket_detail = [
        TaxBracketDetail(
            income_type=treatment.value,
            rate_federal=fed_rate,
            rate_state=state,
            rate_combined=fed_rate + state,
            niit_applicable=niit_flag,
        )
    ]

    return TaxCalculationResponse(
        symbol=request.symbol,
        gross_distribution=dist,
        federal_tax_owed=round(federal_tax, 4),
        state_tax_owed=round(state_tax, 4),
        niit_owed=round(niit, 4),
        total_tax_owed=round(total_tax, 4),
        net_distribution=round(net_dist, 4),
        effective_tax_rate=round(effective_rate, 4),
        after_tax_yield_uplift=round(uplift, 4),
        bracket_detail=bracket_detail,
        notes=notes,
    )
