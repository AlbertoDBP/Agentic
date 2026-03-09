"""
Agent 05 — Tax Optimization Service
Tax Optimizer — recommends optimal account placement for each holding.
Rules:
  - High ordinary income assets (REITs, BDCs, Bond ETFs, MLPs, Covered Call ETFs)
    → tax-sheltered first (TRAD_IRA, ROTH_IRA)
  - Qualified dividend / LTCG assets → taxable accounts (low rate, no urgency to shelter)
  - ROTH_IRA best for highest-growth or highest-yield (permanent shelter)
  - MLP → never in IRA (UBTI), only TAXABLE
"""
from __future__ import annotations

import logging
from typing import List

from app.models import (
    AccountType,
    AssetClass,
    FilingStatus,
    HoldingInput,
    OptimizationRequest,
    OptimizationResponse,
    PlacementRecommendation,
    TaxCalculationRequest,
    TaxProfileRequest,
)
from app.tax.calculator import calculate_tax_burden
from app.tax.profiler import build_tax_profile, _PROFILE_MAP
from app.models import TaxTreatment

logger = logging.getLogger(__name__)

# Tax-inefficient classes that benefit most from sheltering
_SHELTER_PRIORITY = {
    AssetClass.BOND_ETF,
    AssetClass.REIT,
    AssetClass.BDC,
    AssetClass.COVERED_CALL_ETF,
    AssetClass.CLOSED_END_FUND,
    AssetClass.ORDINARY_INCOME,
    AssetClass.UNKNOWN,
}

# Tax-efficient classes that are fine in taxable accounts
_TAXABLE_FRIENDLY = {
    AssetClass.DIVIDEND_STOCK,
    AssetClass.PREFERRED_STOCK,
}

# Never shelter (UBTI issue)
_NEVER_SHELTER = {
    AssetClass.MLP,
}


def _best_shelter_account(holding_value: float, yield_: float) -> AccountType:
    """Simple heuristic: highest-yield/value → Roth for permanent shelter."""
    annual_income = holding_value * yield_
    if annual_income > 2_000:
        return AccountType.ROTH_IRA
    return AccountType.TRAD_IRA


async def optimize_portfolio(request: OptimizationRequest) -> OptimizationResponse:
    """Produce account-placement recommendations for each holding."""
    recommendations: List[PlacementRecommendation] = []
    total_value = sum(h.current_value for h in request.holdings)
    current_tax_burden = 0.0
    optimized_tax_burden = 0.0

    for holding in request.holdings:
        # Resolve asset class
        profile = await build_tax_profile(
            TaxProfileRequest(
                symbol=holding.symbol,
                asset_class=holding.asset_class,
                annual_income=request.annual_income,
                filing_status=request.filing_status,
                state_code=request.state_code,
                account_type=holding.account_type,
            )
        )
        ac = profile.asset_class
        dist_amount = holding.current_value * holding.annual_yield

        # Current tax burden
        current_calc = await calculate_tax_burden(
            TaxCalculationRequest(
                symbol=holding.symbol,
                annual_income=request.annual_income,
                filing_status=request.filing_status,
                state_code=request.state_code,
                account_type=holding.account_type,
                distribution_amount=dist_amount,
                asset_class=ac,
            )
        )
        current_tax_burden += current_calc.total_tax_owed

        # Determine recommended account
        if ac in _NEVER_SHELTER:
            recommended = AccountType.TAXABLE
            reason = (
                "MLPs generate Unrelated Business Taxable Income (UBTI) "
                "inside IRAs, creating unexpected tax liability. Keep in taxable."
            )
        elif ac in _SHELTER_PRIORITY:
            recommended = _best_shelter_account(holding.current_value, holding.annual_yield)
            reason = (
                f"{ac.value} distributions are primarily ordinary income. "
                f"Sheltering in {recommended.value} eliminates annual tax drag."
            )
        elif ac in _TAXABLE_FRIENDLY:
            recommended = AccountType.TAXABLE
            reason = (
                f"{ac.value} generates qualified dividends taxed at preferential rates. "
                "Holding in taxable is tax-efficient; shelter space better used elsewhere."
            )
        else:
            recommended = holding.account_type
            reason = "No change recommended based on current asset class profile."

        # Optimized tax (assume sheltered → 0 current tax; taxable stays same)
        optimized_calc = await calculate_tax_burden(
            TaxCalculationRequest(
                symbol=holding.symbol,
                annual_income=request.annual_income,
                filing_status=request.filing_status,
                state_code=request.state_code,
                account_type=recommended,
                distribution_amount=dist_amount,
                asset_class=ac,
            )
        )
        optimized_tax_burden += optimized_calc.total_tax_owed

        savings = current_calc.total_tax_owed - optimized_calc.total_tax_owed

        if recommended != holding.account_type or savings > 1.0:
            recommendations.append(
                PlacementRecommendation(
                    symbol=holding.symbol,
                    current_account=holding.account_type,
                    recommended_account=recommended,
                    reason=reason,
                    estimated_annual_tax_savings=round(max(savings, 0), 2),
                )
            )

    annual_savings = current_tax_burden - optimized_tax_burden

    return OptimizationResponse(
        total_portfolio_value=round(total_value, 2),
        current_annual_tax_burden=round(current_tax_burden, 2),
        optimized_annual_tax_burden=round(optimized_tax_burden, 2),
        estimated_annual_savings=round(max(annual_savings, 0), 2),
        placement_recommendations=recommendations,
        summary=(
            f"Estimated annual tax savings of ${annual_savings:,.2f} "
            f"achievable by optimizing account placement across "
            f"{len(recommendations)} holding(s)."
        ),
        notes=[
            "Recommendations are estimates based on marginal tax rates; consult a CPA.",
            "ROTH IRA capacity is limited by annual contribution limits.",
        ],
    )
