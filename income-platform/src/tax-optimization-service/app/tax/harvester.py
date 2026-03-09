"""
Agent 05 — Tax Optimization Service
Tax Harvester — identifies tax-loss harvesting opportunities.
Rules applied:
  • Only TAXABLE accounts — sheltered accounts have no harvesting benefit.
  • Loss must be > $100 to be worth actioning.
  • Holding period < 365 days → short-term loss (higher tax value).
  • Wash-sale warning: flags if position was purchased within 30 days.
  • No automatic execution — proposals only, per platform philosophy.
"""
from __future__ import annotations

import logging
from typing import List

from app.models import (
    AccountType,
    FilingStatus,
    HarvestingCandidate,
    HarvestingOpportunity,
    HarvestingRequest,
    HarvestingResponse,
)
from app.tax.calculator import _ordinary_rate, _qualified_rate, _niit_applicable

logger = logging.getLogger(__name__)

_MIN_HARVEST_LOSS = 100.0    # below this, not worth the transaction cost
_WASH_SALE_WINDOW = 30       # days before or after sale with similar security


def _tax_value_of_loss(
    loss: float,
    holding_days: int,
    income: float,
    filing: FilingStatus,
    state_rate: float,
) -> float:
    """Estimate the tax dollars saved by realizing this loss."""
    niit = 0.038 if _niit_applicable(income, filing) else 0.0
    if holding_days >= 365:
        rate = _qualified_rate(income, filing) + state_rate + niit
    else:
        rate = _ordinary_rate(income, filing) + state_rate + niit
    return loss * rate


def _wash_sale_risk(candidate: HarvestingCandidate) -> bool:
    """
    Heuristic flag: if holding period is very short (< 30 days),
    buying a replacement security risks triggering wash-sale rules.
    In production, this would cross-reference actual purchase history.
    """
    return candidate.holding_period_days < _WASH_SALE_WINDOW


async def identify_harvesting_opportunities(
    request: HarvestingRequest,
) -> HarvestingResponse:
    """Analyze candidates and return actionable harvesting opportunities."""
    opportunities: List[HarvestingOpportunity] = []
    total_loss = 0.0
    total_savings = 0.0
    wash_sale_warnings: List[str] = []

    # Approximate state rate (reuse calculator constant)
    from app.tax.calculator import _state_rate
    state_rate = _state_rate(request.state_code)

    for candidate in request.candidates:
        # Sheltered accounts — no benefit
        if candidate.account_type != AccountType.TAXABLE:
            opportunities.append(
                HarvestingOpportunity(
                    symbol=candidate.symbol,
                    unrealized_loss=0.0,
                    tax_savings_estimated=0.0,
                    holding_period_days=candidate.holding_period_days,
                    long_term=candidate.holding_period_days >= 365,
                    wash_sale_risk=False,
                    action="HOLD",
                    rationale=(
                        f"Account type {candidate.account_type} — "
                        "tax-loss harvesting provides no benefit in sheltered accounts."
                    ),
                )
            )
            continue

        unrealized = candidate.cost_basis - candidate.current_value

        if unrealized <= 0:
            # Gain position — skip
            continue

        if unrealized < _MIN_HARVEST_LOSS:
            opportunities.append(
                HarvestingOpportunity(
                    symbol=candidate.symbol,
                    unrealized_loss=round(unrealized, 2),
                    tax_savings_estimated=0.0,
                    holding_period_days=candidate.holding_period_days,
                    long_term=candidate.holding_period_days >= 365,
                    wash_sale_risk=False,
                    action="MONITOR",
                    rationale=(
                        f"Loss of ${unrealized:.2f} is below the ${_MIN_HARVEST_LOSS:.0f} "
                        "minimum threshold for cost-effective harvesting."
                    ),
                )
            )
            continue

        ws_risk = request.wash_sale_check and _wash_sale_risk(candidate)
        savings = _tax_value_of_loss(
            unrealized,
            candidate.holding_period_days,
            request.annual_income,
            request.filing_status,
            state_rate,
        )

        action = "HARVEST_NOW" if not ws_risk else "REVIEW_WASH_SALE"
        rationale_parts = [
            f"Unrealized loss of ${unrealized:,.2f} qualifies for harvesting.",
            f"Estimated tax savings: ${savings:,.2f}.",
            "Long-term loss." if candidate.holding_period_days >= 365 else "Short-term loss (higher tax value).",
        ]
        if ws_risk:
            msg = (
                f"{candidate.symbol}: Position held for only {candidate.holding_period_days} days. "
                "Purchasing a substantially identical security within 30 days before/after sale "
                "triggers the wash-sale rule and disallows the loss."
            )
            wash_sale_warnings.append(msg)
            rationale_parts.append("⚠ Wash-sale risk — review replacement security carefully.")

        total_loss += unrealized
        total_savings += savings

        opportunities.append(
            HarvestingOpportunity(
                symbol=candidate.symbol,
                unrealized_loss=round(unrealized, 2),
                tax_savings_estimated=round(savings, 2),
                holding_period_days=candidate.holding_period_days,
                long_term=candidate.holding_period_days >= 365,
                wash_sale_risk=ws_risk,
                action=action,
                rationale=" ".join(rationale_parts),
            )
        )

    return HarvestingResponse(
        total_harvestable_losses=round(total_loss, 2),
        total_estimated_tax_savings=round(total_savings, 2),
        opportunities=opportunities,
        wash_sale_warnings=wash_sale_warnings,
        notes=[
            "Tax savings are estimates; actual savings depend on your full tax picture.",
            "Consult a tax advisor before executing any harvesting transactions.",
            "This service proposes only — no trades are executed automatically.",
        ],
    )
