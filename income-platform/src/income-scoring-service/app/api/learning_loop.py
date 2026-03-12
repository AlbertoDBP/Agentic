"""
Agent 03 — Income Scoring Service
API: Learning Loop endpoints (Phase 3).

Endpoints:
  GET  /learning-loop/shadow-portfolio/           — list recent shadow portfolio entries
  POST /learning-loop/populate-outcomes           — batch-populate outcomes (admin)
  POST /learning-loop/review/{asset_class}        — trigger quarterly weight review (admin)
  GET  /learning-loop/reviews                     — list weight review runs
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ShadowPortfolioEntry, WeightReviewRun
from app.scoring.shadow_portfolio import shadow_portfolio_manager
from app.scoring.weight_tuner import quarterly_weight_tuner

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ASSET_CLASSES = {
    "EQUITY_REIT", "MORTGAGE_REIT", "BDC", "COVERED_CALL_ETF",
    "DIVIDEND_STOCK", "BOND", "PREFERRED_STOCK",
}


# ── Pydantic models ───────────────────────────────────────────────────────────

class PopulateOutcomesRequest(BaseModel):
    """Exit prices for PENDING entries. Key = ticker, value = current price."""
    exit_prices: dict[str, float]
    triggered_by: Optional[str] = None


class PopulateOutcomesResponse(BaseModel):
    updated: int
    skipped_no_price: int
    skipped_no_entry_price: int
    total_pending: int


class ReviewRequest(BaseModel):
    triggered_by: Optional[str] = None
    lookback_days: Optional[int] = None  # None = all completed outcomes


class ShadowEntryResponse(BaseModel):
    id: str
    ticker: str
    asset_class: str
    entry_score: float
    entry_grade: str
    entry_recommendation: str
    entry_price: Optional[float]
    entry_date: datetime
    hold_period_days: int
    exit_price: Optional[float]
    exit_date: Optional[datetime]
    actual_return_pct: Optional[float]
    outcome_label: str
    outcome_populated_at: Optional[datetime]


class ReviewRunResponse(BaseModel):
    id: str
    asset_class: str
    triggered_at: datetime
    triggered_by: Optional[str]
    status: str
    outcomes_analyzed: int
    correct_count: int
    incorrect_count: int
    neutral_count: int
    weight_yield_before: Optional[int]
    weight_durability_before: Optional[int]
    weight_technical_before: Optional[int]
    weight_yield_after: Optional[int]
    weight_durability_after: Optional[int]
    weight_technical_after: Optional[int]
    delta_yield: Optional[int]
    delta_durability: Optional[int]
    delta_technical: Optional[int]
    skip_reason: Optional[str]
    completed_at: Optional[datetime]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry_to_response(e: ShadowPortfolioEntry) -> ShadowEntryResponse:
    return ShadowEntryResponse(
        id=str(e.id),
        ticker=e.ticker,
        asset_class=e.asset_class,
        entry_score=e.entry_score,
        entry_grade=e.entry_grade,
        entry_recommendation=e.entry_recommendation,
        entry_price=e.entry_price,
        entry_date=e.entry_date,
        hold_period_days=e.hold_period_days,
        exit_price=e.exit_price,
        exit_date=e.exit_date,
        actual_return_pct=e.actual_return_pct,
        outcome_label=e.outcome_label,
        outcome_populated_at=e.outcome_populated_at,
    )


def _review_to_response(r: WeightReviewRun) -> ReviewRunResponse:
    return ReviewRunResponse(
        id=str(r.id),
        asset_class=r.asset_class,
        triggered_at=r.triggered_at,
        triggered_by=r.triggered_by,
        status=r.status,
        outcomes_analyzed=r.outcomes_analyzed,
        correct_count=r.correct_count,
        incorrect_count=r.incorrect_count,
        neutral_count=r.neutral_count,
        weight_yield_before=r.weight_yield_before,
        weight_durability_before=r.weight_durability_before,
        weight_technical_before=r.weight_technical_before,
        weight_yield_after=r.weight_yield_after,
        weight_durability_after=r.weight_durability_after,
        weight_technical_after=r.weight_technical_after,
        delta_yield=r.delta_yield,
        delta_durability=r.delta_durability,
        delta_technical=r.delta_technical,
        skip_reason=r.skip_reason,
        completed_at=r.completed_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/shadow-portfolio/", response_model=list[ShadowEntryResponse])
def list_shadow_portfolio(
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
    outcome: Optional[str] = Query(None, description="Filter by outcome_label"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List recent shadow portfolio entries."""
    q = db.query(ShadowPortfolioEntry).order_by(ShadowPortfolioEntry.entry_date.desc())
    if asset_class:
        q = q.filter(ShadowPortfolioEntry.asset_class == asset_class.upper())
    if outcome:
        q = q.filter(ShadowPortfolioEntry.outcome_label == outcome.upper())
    return [_entry_to_response(e) for e in q.limit(limit).all()]


@router.post("/populate-outcomes", response_model=PopulateOutcomesResponse)
def populate_outcomes(
    req: PopulateOutcomesRequest,
    db: Session = Depends(get_db),
):
    """
    Populate outcome labels for PENDING shadow portfolio entries past their hold period.

    Provide exit_prices as a dict of {ticker: current_price}.
    Only entries past their 90-day hold period are processed.
    """
    result = shadow_portfolio_manager.populate_outcomes(db, req.exit_prices)
    return PopulateOutcomesResponse(**result)


@router.post("/review/{asset_class}", response_model=ReviewRunResponse, status_code=201)
def trigger_review(
    asset_class: str,
    req: ReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger a quarterly weight review for the given asset class.

    Analyzes completed shadow portfolio outcomes and proposes/applies pillar
    weight adjustments. The review is skipped if fewer than 10 usable outcomes
    (CORRECT + INCORRECT) exist, or if the computed signal is too weak.
    """
    ac = asset_class.upper()
    if ac not in VALID_ASSET_CLASSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown asset class '{ac}'. Valid: {sorted(VALID_ASSET_CLASSES)}",
        )

    since = None
    if req.lookback_days:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=req.lookback_days)

    outcomes = shadow_portfolio_manager.get_completed_outcomes(db, ac, since=since)

    try:
        review = quarterly_weight_tuner.apply_review(
            db, ac, outcomes, triggered_by=req.triggered_by
        )
    except Exception as exc:
        logger.error("Review trigger failed for %s: %s", ac, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {exc}",
        )

    return _review_to_response(review)


@router.get("/reviews", response_model=list[ReviewRunResponse])
def list_reviews(
    asset_class: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List recent weight review runs."""
    q = db.query(WeightReviewRun).order_by(WeightReviewRun.triggered_at.desc())
    if asset_class:
        q = q.filter(WeightReviewRun.asset_class == asset_class.upper())
    return [_review_to_response(r) for r in q.limit(limit).all()]
