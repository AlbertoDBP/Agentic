"""
Agent 08 — Rebalancing Engine

Algorithm:
  1. Load positions + constraints + income metrics from DB (via portfolio_reader)
  2. Score all positions via Agent 03 (concurrent, asyncio.Semaphore)
  3. Detect violations in priority order:
     VETO (score < 70)  ->  action=SELL
     OVERWEIGHT (weight > max_position_pct)  ->  action=TRIM
     BELOW_GRADE (grade < min_income_score_grade)  ->  action=SELL or REDUCE
  4. Build ADD proposals if capital_to_deploy > 0 (highest-scored positions under max_weight)
  5. For TRIM/SELL proposals: call Agent 05 for tax-harvest impact (concurrent)
  6. Sort proposals by priority; truncate to max_proposals
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.rebalancer import portfolio_reader
from app.rebalancer.scoring_client import score_ticker
from app.rebalancer.tax_client import get_harvest_impact

logger = logging.getLogger(__name__)

# Grade ordering for constraint comparison
_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


@dataclass
class RebalanceEngineResult:
    portfolio_value: float
    actual_income_annual: Optional[float]
    target_income_annual: Optional[float]
    income_gap_annual: Optional[float]
    violations_count: int
    violations_summary: dict
    proposals: list[dict]  # List of RebalanceProposal-shaped dicts
    tax_impact_total_savings: Optional[float]


async def run_rebalance(
    portfolio_id: str,
    include_tax_impact: bool = True,
    max_proposals: int = 20,
    cash_override: Optional[float] = None,
) -> RebalanceEngineResult:
    """Run full rebalancing analysis for a portfolio."""

    # 1. Load data
    positions = await portfolio_reader.get_positions(portfolio_id)
    portfolio = await portfolio_reader.get_portfolio(portfolio_id)
    constraints = await portfolio_reader.get_constraints(portfolio_id)
    metrics = await portfolio_reader.get_latest_income_metrics(portfolio_id)

    if not positions:
        return RebalanceEngineResult(
            portfolio_value=0.0,
            actual_income_annual=None,
            target_income_annual=None,
            income_gap_annual=None,
            violations_count=0,
            violations_summary={"count": 0},
            proposals=[],
            tax_impact_total_savings=None,
        )

    portfolio_value = float(portfolio.get("total_value") or 0.0) if portfolio else 0.0
    capital_to_deploy = float(
        cash_override if cash_override is not None
        else (portfolio.get("capital_to_deploy") or 0.0) if portfolio
        else 0.0
    )

    actual_income = float(metrics.get("actual_income_annual") or 0.0) if metrics else None
    target_income = float(metrics.get("target_income_annual") or 0.0) if metrics else None
    income_gap = float(metrics.get("income_gap_annual") or 0.0) if metrics else None

    # 2. Score all positions concurrently
    sem = asyncio.Semaphore(settings.rebalance_concurrency)

    async def _score_with_sem(pos: dict) -> tuple[dict, Optional[dict]]:
        async with sem:
            score = await score_ticker(pos["symbol"])
        return pos, score

    scored_pairs = await asyncio.gather(*[_score_with_sem(p) for p in positions])

    # 3. Identify violations and build proposals
    max_pos_pct = float(constraints.get("max_position_pct") or 100.0) if constraints else 100.0
    min_grade_str = (constraints.get("min_income_score_grade") or "B") if constraints else "B"
    min_grade_val = _GRADE_ORDER.get(min_grade_str, 3)

    proposals = []
    violation_count = 0
    hhs_tier_counts: dict[str, int] = {"UNSAFE": 0, "CONCERN": 0, "WATCH": 0, "GOOD": 0, "STRONG": 0}

    for pos, score_data in scored_pairs:
        symbol = pos["symbol"]
        current_value = float(pos.get("current_value") or 0.0)
        weight_pct = float(pos.get("portfolio_weight_pct") or 0.0)
        cost_basis = float(pos.get("avg_cost_basis") or 0.0) * float(pos.get("quantity") or 0.0)
        acquired = pos.get("acquired_date")

        if score_data is None:
            # Skip if Agent 03 unavailable
            continue

        total_score = float(score_data.get("total_score", 0.0))
        grade = score_data.get("grade", "F")
        grade_val = _GRADE_ORDER.get(grade, 0)
        recommendation = score_data.get("recommendation", "")
        commentary = score_data.get("score_commentary")
        chowder_signal = score_data.get("chowder_signal")

        hhs_score_val = score_data.get("hhs_score")
        hhs_score_f = float(hhs_score_val) if hhs_score_val is not None else None
        hhs_status = score_data.get("hhs_status")
        unsafe_flag = score_data.get("unsafe_flag")   # bool or None
        ies_score_val = score_data.get("ies_score")
        ies_score_f = float(ies_score_val) if ies_score_val is not None else None
        # ies_calculated: None means key absent (legacy scores) — treat as True with fallback gate
        _ies_calc_raw = score_data.get("ies_calculated", None)
        ies_calculated = bool(_ies_calc_raw) if _ies_calc_raw is not None else None
        yield_pct = float(pos.get("yield_on_value") or 0.0)

        # Track HHS tier for violations_summary
        if hhs_status in hhs_tier_counts:
            hhs_tier_counts[hhs_status] += 1

        proposal = None

        # Priority 0 — UNSAFE (new: above VETO)
        if unsafe_flag is True:
            proposal = {
                "symbol": symbol,
                "action": "SELL",
                "priority": 0,
                "reason": (
                    f"UNSAFE holding — HHS Durability pillar at or below safety threshold. "
                    f"HHS: {f'{hhs_score_f:.0f}' if hhs_score_f is not None else '?'}. "
                    f"Immediate review required."
                ),
                "violation_type": "UNSAFE",
                "current_value": current_value,
                "current_weight_pct": weight_pct,
                "proposed_weight_pct": 0.0,
                "estimated_trade_value": -current_value,
                "income_score": total_score,
                "income_grade": grade,
                "score_commentary": commentary,
                "chowder_signal": chowder_signal,
                "hhs_score": hhs_score_f,
                "hhs_status": hhs_status,
                "unsafe_flag": unsafe_flag,
                "ies_score": ies_score_f,
                "ies_calculated": ies_calculated,
                "income_contribution_est": None,
                "tax_impact": None,
                "_acquired": acquired,
                "_cost_basis": cost_basis,
            }
            violation_count += 1

        # Priority 1 — VETO (unchanged condition)
        elif total_score < settings.quality_gate_threshold:
            proposal = {
                "symbol": symbol,
                "action": "SELL",
                "priority": 1,
                "reason": (
                    f"Quality gate VETO — score {total_score:.0f} ({grade}) "
                    f"is below threshold {settings.quality_gate_threshold:.0f}. "
                    f"Platform recommendation: {recommendation}."
                ),
                "violation_type": "VETO",
                "current_value": current_value,
                "current_weight_pct": weight_pct,
                "proposed_weight_pct": 0.0,
                "estimated_trade_value": -current_value,
                "income_score": total_score,
                "income_grade": grade,
                "score_commentary": commentary,
                "chowder_signal": chowder_signal,
                "hhs_score": hhs_score_f,
                "hhs_status": hhs_status,
                "unsafe_flag": unsafe_flag,
                "ies_score": ies_score_f,
                "ies_calculated": ies_calculated,
                "income_contribution_est": None,
                "tax_impact": None,
                "_acquired": acquired,
                "_cost_basis": cost_basis,
            }
            violation_count += 1

        # Priority 2 — OVERWEIGHT (unchanged condition)
        elif weight_pct > max_pos_pct:
            excess_pct = weight_pct - max_pos_pct
            trim_value = -(portfolio_value * excess_pct / 100.0)
            proposal = {
                "symbol": symbol,
                "action": "TRIM",
                "priority": 2,
                "reason": (
                    f"Position overweight — {weight_pct:.1f}% exceeds "
                    f"max_position_pct {max_pos_pct:.1f}%. "
                    f"Trim to reduce by {excess_pct:.1f}%."
                ),
                "violation_type": "OVERWEIGHT",
                "current_value": current_value,
                "current_weight_pct": weight_pct,
                "proposed_weight_pct": max_pos_pct,
                "estimated_trade_value": trim_value,
                "income_score": total_score,
                "income_grade": grade,
                "score_commentary": commentary,
                "chowder_signal": chowder_signal,
                "hhs_score": hhs_score_f,
                "hhs_status": hhs_status,
                "unsafe_flag": unsafe_flag,
                "ies_score": ies_score_f,
                "ies_calculated": ies_calculated,
                "income_contribution_est": None,
                "tax_impact": None,
                "_acquired": acquired,
                "_cost_basis": cost_basis,
            }
            violation_count += 1

        # Priority 3 — BELOW_GRADE (unchanged condition)
        elif grade_val < min_grade_val:
            proposal = {
                "symbol": symbol,
                "action": "SELL",
                "priority": 3,
                "reason": (
                    f"Income grade {grade} is below minimum required {min_grade_str}. "
                    f"Score: {total_score:.0f}. Consider replacing with higher-grade position."
                ),
                "violation_type": "BELOW_GRADE",
                "current_value": current_value,
                "current_weight_pct": weight_pct,
                "proposed_weight_pct": 0.0,
                "estimated_trade_value": -current_value,
                "income_score": total_score,
                "income_grade": grade,
                "score_commentary": commentary,
                "chowder_signal": chowder_signal,
                "hhs_score": hhs_score_f,
                "hhs_status": hhs_status,
                "unsafe_flag": unsafe_flag,
                "ies_score": ies_score_f,
                "ies_calculated": ies_calculated,
                "income_contribution_est": None,
                "tax_impact": None,
                "_acquired": acquired,
                "_cost_basis": cost_basis,
            }
            violation_count += 1

        # Priority 4 — ADD (IES-gated when IES data present, else legacy score >= 70 gate)
        else:
            # ies_calculated=None means legacy score (no HHS/IES fields) — use old total_score gate
            ies_gate_pass = (
                ies_calculated is True
                and ies_score_f is not None
                and ies_score_f >= 70.0
            ) if ies_calculated is not None else (total_score >= 70.0)
            if (
                ies_gate_pass
                and weight_pct < max_pos_pct
                and capital_to_deploy > 0
            ):
                add_value = min(
                    capital_to_deploy * 0.25,
                    portfolio_value * (max_pos_pct / 100.0) - current_value,
                )
                if add_value > 0:
                    income_contribution_est = round(add_value * (yield_pct / 100.0), 2)
                    gap_str = ""
                    if income_gap and income_gap < 0 and income_contribution_est > 0:
                        gap_close_pct = (income_contribution_est / abs(income_gap)) * 100
                        gap_str = f" — closes ~{gap_close_pct:.0f}% of ${abs(income_gap):.0f} annual income gap"
                    proposal = {
                        "symbol": symbol,
                        "action": "ADD",
                        "priority": 4,
                        "reason": (
                            f"Good entry timing — "
                            + (f"IES {ies_score_f:.0f}, " if ies_score_f is not None else "")
                            + f"score {total_score:.0f} ({grade}), "
                            f"currently {weight_pct:.1f}% — room to add up to {max_pos_pct:.1f}%{gap_str}."
                        ),
                        "violation_type": "DEPLOY_CAPITAL",
                        "current_value": current_value,
                        "current_weight_pct": weight_pct,
                        "proposed_weight_pct": min(
                            weight_pct + add_value / portfolio_value * 100, max_pos_pct
                        ),
                        "estimated_trade_value": add_value,
                        "income_score": total_score,
                        "income_grade": grade,
                        "score_commentary": commentary,
                        "chowder_signal": chowder_signal,
                        "hhs_score": hhs_score_f,
                        "hhs_status": hhs_status,
                        "unsafe_flag": unsafe_flag,
                        "ies_score": ies_score_f,
                        "ies_calculated": ies_calculated,
                        "income_contribution_est": income_contribution_est,
                        "tax_impact": None,
                        "_acquired": acquired,
                        "_cost_basis": cost_basis,
                    }

        if proposal:
            proposals.append(proposal)

    # 4. Enrich TRIM/SELL proposals with tax impact
    if include_tax_impact:
        tax_sem = asyncio.Semaphore(5)

        async def _tax_enrich(p: dict) -> dict:
            if p["action"] not in ("TRIM", "SELL"):
                return p
            async with tax_sem:
                impact = await get_harvest_impact(
                    symbol=p["symbol"],
                    current_value=p["current_value"],
                    cost_basis=p["_cost_basis"],
                    acquired_date=p["_acquired"],
                )
            if impact:
                p["tax_impact"] = {
                    "unrealized_gain_loss": float(impact.get("unrealized_loss", 0.0)),
                    "estimated_tax_savings": float(impact.get("tax_savings_estimated", 0.0)),
                    "long_term": bool(impact.get("long_term", False)),
                    "wash_sale_risk": bool(impact.get("wash_sale_risk", False)),
                    "action": impact.get("action", "HOLD"),
                }
            return p

        proposals = list(await asyncio.gather(*[_tax_enrich(p) for p in proposals]))

    # 5. Sort by priority, then by score (lower score = higher urgency within same priority)
    proposals.sort(key=lambda p: (
        p["priority"],
        -(p.get("income_contribution_est") or 0.0) if p["priority"] == 4 else (p.get("income_score") or 100.0),
    ))

    # 6. Remove internal keys before returning
    for p in proposals:
        p.pop("_acquired", None)
        p.pop("_cost_basis", None)

    # Truncate to max_proposals
    proposals = proposals[:max_proposals]

    # Total tax savings
    total_savings = None
    savings_list = [
        p["tax_impact"]["estimated_tax_savings"]
        for p in proposals
        if p.get("tax_impact") and p["tax_impact"].get("estimated_tax_savings", 0) > 0
    ]
    if savings_list:
        total_savings = sum(savings_list)

    return RebalanceEngineResult(
        portfolio_value=portfolio_value,
        actual_income_annual=actual_income,
        target_income_annual=target_income,
        income_gap_annual=income_gap,
        violations_count=violation_count,
        violations_summary={
            "count": violation_count,
            "unsafe": sum(1 for p in proposals if p.get("violation_type") == "UNSAFE"),
            "veto": sum(1 for p in proposals if p.get("violation_type") == "VETO"),
            "overweight": sum(1 for p in proposals if p.get("violation_type") == "OVERWEIGHT"),
            "below_grade": sum(1 for p in proposals if p.get("violation_type") == "BELOW_GRADE"),
            "deploy_capital": sum(1 for p in proposals if p.get("violation_type") == "DEPLOY_CAPITAL"),
            "hhs_tiers": hhs_tier_counts,
        },
        proposals=proposals,
        tax_impact_total_savings=total_savings,
    )
