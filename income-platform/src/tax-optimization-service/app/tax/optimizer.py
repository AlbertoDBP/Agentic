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
    HoldingAnalysis,
    HoldingInput,
    OptimizationRequest,
    OptimizationResponse,
    PlacementRecommendation,
    TaxCalculationRequest,
    TaxProfileRequest,
)
from app.tax.calculator import (
    calculate_tax_burden,
    _niit_applicable,
    _ordinary_rate,
    _qualified_rate,
    _state_rate,
)
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
    AssetClass.MUNICIPAL_BOND_FUND,  # Tax-exempt income — sheltering wastes IRA space
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
        primary_treatment = profile.primary_tax_treatment
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
        elif primary_treatment == TaxTreatment.TAX_EXEMPT:
            # Municipal bond funds: income already tax-exempt at federal level.
            # Sheltering them in a tax-deferred account wastes IRA space
            # without additional benefit — keep in taxable.
            recommended = AccountType.TAXABLE
            reason = (
                "Municipal bond distributions are federally tax-exempt. "
                "Sheltering in an IRA provides no additional tax benefit and "
                "wastes tax-advantaged space. Keep in taxable account."
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

    # ── Build holdings_analysis for ALL holdings ──────────────────────────────
    # Index recommendations by symbol for fast lookup
    rec_map: dict[str, PlacementRecommendation] = {
        r.symbol: r for r in recommendations
    }

    holdings_analysis: list[HoldingAnalysis] = []
    total_gross_income = 0.0
    total_net_income = 0.0

    for holding in request.holdings:
        # Resolve asset class (re-use profile already built; re-call is cheap)
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
        treatment = profile.primary_tax_treatment

        gross_income = holding.current_value * holding.annual_yield
        gross_yield = holding.annual_yield

        # Determine if tax-sheltered
        is_sheltered = holding.account_type in (
            AccountType.TRAD_IRA, AccountType.ROTH_IRA,
            AccountType.HSA, AccountType.FOUR01K,
        )

        if is_sheltered:
            effective_tax_rate = 0.0
            tax_withheld = 0.0
        else:
            # Compute effective tax rate using the same logic as calculator.py
            income = request.annual_income
            filing = request.filing_status
            state = _state_rate(request.state_code)

            use_qualified = treatment in (
                TaxTreatment.QUALIFIED_DIVIDEND,
                TaxTreatment.CAPITAL_GAIN_LONG,
                TaxTreatment.SECTION_1256_60_40,
            )

            if treatment == TaxTreatment.TAX_EXEMPT:
                fed_rate = 0.0
            elif treatment == TaxTreatment.RETURN_OF_CAPITAL:
                fed_rate = 0.0
            elif treatment == TaxTreatment.SECTION_1256_60_40:
                ltcg_rate = _qualified_rate(income, filing)
                st_rate = _ordinary_rate(income, filing)
                fed_rate = 0.60 * ltcg_rate + 0.40 * st_rate
            elif treatment in (TaxTreatment.MLP_DISTRIBUTION, TaxTreatment.REIT_DISTRIBUTION):
                fed_rate = _ordinary_rate(income, filing) * 0.30
            elif use_qualified:
                fed_rate = _qualified_rate(income, filing)
            else:
                fed_rate = _ordinary_rate(income, filing)

            niit_rate = 0.038 if (
                treatment not in (
                    TaxTreatment.TAX_EXEMPT,
                    TaxTreatment.RETURN_OF_CAPITAL,
                    TaxTreatment.MLP_DISTRIBUTION,
                )
                and _niit_applicable(income, filing)
            ) else 0.0

            effective_tax_rate = fed_rate + state + niit_rate
            tax_withheld = gross_income * effective_tax_rate

        after_tax_income = gross_income - tax_withheld
        after_tax_yield = after_tax_income / holding.current_value if holding.current_value > 0 else 0.0

        # Expense drag
        expense_ratio = holding.expense_ratio or 0.0
        expense_drag_amount = holding.current_value * expense_ratio
        expense_drag_pct = expense_ratio

        net_annual_income = after_tax_income - expense_drag_amount
        nay = net_annual_income / holding.current_value if holding.current_value > 0 else 0.0

        # Placement mismatch: holding is in wrong shelter/taxable category.
        # Fine-grained ROTH vs TRAD swaps within already-sheltered holdings
        # are NOT considered a mismatch — the holding is already optimally placed
        # from a tax-efficiency standpoint.
        rec = rec_map.get(holding.symbol)
        _sheltered_types = (
            AccountType.TRAD_IRA, AccountType.ROTH_IRA,
            AccountType.HSA, AccountType.FOUR01K,
        )
        current_is_sheltered = holding.account_type in _sheltered_types
        recommended_account_type = rec.recommended_account if rec else holding.account_type
        recommended_is_sheltered = recommended_account_type in _sheltered_types
        placement_mismatch = (
            rec is not None
            and current_is_sheltered != recommended_is_sheltered
        )
        recommended_account = recommended_account_type.value
        estimated_savings = rec.estimated_annual_tax_savings if rec else 0.0
        reason = rec.reason if rec else "Holding is optimally placed."

        total_gross_income += gross_income
        total_net_income += net_annual_income

        holdings_analysis.append(
            HoldingAnalysis(
                symbol=holding.symbol,
                asset_class=ac.value,
                current_account=holding.account_type.value,
                recommended_account=recommended_account,
                placement_mismatch=placement_mismatch,
                treatment=treatment.value,
                gross_yield=round(gross_yield, 6),
                effective_tax_rate=round(effective_tax_rate, 6),
                after_tax_yield=round(after_tax_yield, 6),
                expense_ratio=holding.expense_ratio,
                expense_drag_pct=round(expense_drag_pct, 6),
                nay=round(nay, 6),
                annual_income=round(gross_income, 4),
                tax_withheld=round(tax_withheld, 4),
                expense_drag_amount=round(expense_drag_amount, 4),
                net_annual_income=round(net_annual_income, 4),
                estimated_annual_tax_savings=round(estimated_savings, 2),
                reason=reason,
            )
        )

    # Portfolio-level metrics
    portfolio_gross_yield = (
        total_gross_income / total_value if total_value > 0 else 0.0
    )
    portfolio_nay = (
        total_net_income / total_value if total_value > 0 else 0.0
    )

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
        holdings_analysis=holdings_analysis,
        portfolio_gross_yield=round(portfolio_gross_yield, 6),
        portfolio_nay=round(portfolio_nay, 6),
        suboptimal_count=len(recommendations),
    )
