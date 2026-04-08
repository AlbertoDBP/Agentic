"""Agent 08 — Rebalancing API endpoints."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RebalancingResult
from app.rebalancer.engine import run_rebalance, RebalanceEngineResult

router = APIRouter()


class TaxImpactSummary(BaseModel):
    unrealized_gain_loss: float
    estimated_tax_savings: float
    long_term: bool
    wash_sale_risk: bool
    action: str  # HARVEST_NOW | MONITOR | HOLD


class RebalanceProposal(BaseModel):
    symbol: str
    action: str                           # TRIM | SELL | ADD | HOLD
    priority: int                         # 1 = highest urgency
    reason: str
    violation_type: Optional[str] = None  # OVERWEIGHT | BELOW_GRADE | VETO | DEPLOY_CAPITAL
    current_value: float
    current_weight_pct: float
    proposed_weight_pct: Optional[float] = None
    estimated_trade_value: float          # positive = buy, negative = sell
    income_score: Optional[float] = None
    income_grade: Optional[str] = None
    score_commentary: Optional[str] = None
    chowder_signal: Optional[str] = None
    hhs_score: Optional[float] = None
    hhs_status: Optional[str] = None
    unsafe_flag: Optional[bool] = None
    ies_score: Optional[float] = None
    ies_calculated: Optional[bool] = None
    income_contribution_est: Optional[float] = None
    tax_impact: Optional[TaxImpactSummary] = None


class RebalanceRequest(BaseModel):
    include_tax_impact: bool = True
    max_proposals: int = Field(default=20, ge=1, le=50)
    cash_override: Optional[float] = None


class RebalanceResponse(BaseModel):
    result_id: str
    portfolio_id: str
    portfolio_value: float
    actual_income_annual: Optional[float] = None
    target_income_annual: Optional[float] = None
    income_gap_annual: Optional[float] = None
    violations_count: int
    violations_summary: dict = {}
    proposals: List[RebalanceProposal]
    tax_impact_total_savings: Optional[float] = None
    generated_at: str


@router.post("/rebalance/{portfolio_id}", response_model=RebalanceResponse)
async def post_rebalance(
    portfolio_id: UUID,
    request: RebalanceRequest,
    save: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> RebalanceResponse:
    """
    Run rebalancing analysis for a portfolio.

    1. Loads positions + constraints via asyncpg
    2. Scores all positions via Agent 03 (concurrent)
    3. Identifies VETO / OVERWEIGHT / BELOW_GRADE violations
    4. Calls Agent 05 for tax-harvest impact on TRIM/SELL proposals
    5. Returns proposals sorted by priority
    6. Persists result when save=True
    """
    result: RebalanceEngineResult = await run_rebalance(
        portfolio_id=str(portfolio_id),
        include_tax_impact=request.include_tax_impact,
        max_proposals=request.max_proposals,
        cash_override=request.cash_override,
    )

    proposals = [RebalanceProposal(**p) for p in result.proposals]
    tax_savings = result.tax_impact_total_savings

    # Optionally persist
    result_id = str(uuid.uuid4())
    if save:
        row = RebalancingResult(
            id=uuid.UUID(result_id),
            portfolio_id=portfolio_id,
            violations=result.violations_summary,
            proposals=[p.model_dump() for p in proposals],
            filters={
                "include_tax_impact": request.include_tax_impact,
                "max_proposals": request.max_proposals,
                "cash_override": request.cash_override,
                "portfolio_value": result.portfolio_value,
                "actual_income_annual": result.actual_income_annual,
                "target_income_annual": result.target_income_annual,
                "income_gap_annual": result.income_gap_annual,
            },
            total_tax_savings=tax_savings,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        result_id = str(row.id)

    return RebalanceResponse(
        result_id=result_id,
        portfolio_id=str(portfolio_id),
        portfolio_value=result.portfolio_value,
        actual_income_annual=result.actual_income_annual,
        target_income_annual=result.target_income_annual,
        income_gap_annual=result.income_gap_annual,
        violations_count=result.violations_count,
        violations_summary=result.violations_summary,
        proposals=proposals,
        tax_impact_total_savings=tax_savings,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/rebalance/{result_id}", response_model=RebalanceResponse)
def get_rebalance_result(result_id: UUID, db: Session = Depends(get_db)) -> RebalanceResponse:
    """Fetch a previously saved rebalancing result by UUID."""
    row = db.get(RebalancingResult, result_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Result {result_id} not found.")
    return _row_to_response(row)


@router.get("/rebalance/portfolio/{portfolio_id}/history")
def get_portfolio_history(
    portfolio_id: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """List recent rebalancing results for a portfolio."""
    from sqlalchemy import desc
    rows = (
        db.query(RebalancingResult)
        .filter(RebalancingResult.portfolio_id == portfolio_id)
        .order_by(desc(RebalancingResult.created_at))
        .limit(limit)
        .all()
    )
    return {
        "portfolio_id": str(portfolio_id),
        "total": len(rows),
        "results": [_row_to_response(r).model_dump() for r in rows],
    }


def _row_to_response(row: RebalancingResult) -> RebalanceResponse:
    proposals = [RebalanceProposal(**p) for p in (row.proposals or [])]
    filters = row.filters or {}
    return RebalanceResponse(
        result_id=str(row.id),
        portfolio_id=str(row.portfolio_id),
        portfolio_value=filters.get("portfolio_value", 0.0),
        actual_income_annual=filters.get("actual_income_annual"),
        target_income_annual=filters.get("target_income_annual"),
        income_gap_annual=filters.get("income_gap_annual"),
        violations_count=row.violations.get("count", 0) if row.violations else 0,
        violations_summary=row.violations or {},
        proposals=proposals,
        tax_impact_total_savings=float(row.total_tax_savings) if row.total_tax_savings else None,
        generated_at=str(row.created_at),
    )
