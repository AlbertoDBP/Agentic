"""
Agent 03 — Income Scoring Service
API: Classification Accuracy endpoints (Phase 4 — Detector Confidence Learning).

Endpoints:
  GET  /classification-accuracy/feedback        — recent classification feedback entries
  GET  /classification-accuracy/runs            — historical accuracy rollup runs
  POST /classification-accuracy/rollup          — trigger monthly accuracy rollup (admin)
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.scoring.classification_feedback import (
    classification_feedback_tracker,
    SOURCE_AGENT04,
    SOURCE_MANUAL,
)
from app.models import ClassificationFeedback, ClassifierAccuracyRun

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class FeedbackResponse(BaseModel):
    id: str
    ticker: str
    asset_class_used: str
    source: str
    agent04_class: Optional[str]
    agent04_confidence: Optional[float]
    is_mismatch: Optional[bool]
    captured_at: datetime
    income_score_id: Optional[str]


class AccuracyRunResponse(BaseModel):
    id: str
    period_month: str
    asset_class: Optional[str]
    total_calls: int
    agent04_trusted: int
    manual_overrides: int
    mismatches: int
    accuracy_rate: Optional[float]
    override_rate: Optional[float]
    mismatch_rate: Optional[float]
    computed_at: datetime
    computed_by: Optional[str]


class RollupRequest(BaseModel):
    """Request body for monthly rollup trigger."""
    period_month: str   # "YYYY-MM"
    computed_by: Optional[str] = None


class RollupResponse(BaseModel):
    period_month: str
    runs_created: int
    total_feedback_entries: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _feedback_to_response(f: ClassificationFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=str(f.id),
        ticker=f.ticker,
        asset_class_used=f.asset_class_used,
        source=f.source,
        agent04_class=f.agent04_class,
        agent04_confidence=f.agent04_confidence,
        is_mismatch=f.is_mismatch,
        captured_at=f.captured_at,
        income_score_id=str(f.income_score_id) if f.income_score_id else None,
    )


def _run_to_response(r: ClassifierAccuracyRun) -> AccuracyRunResponse:
    return AccuracyRunResponse(
        id=str(r.id),
        period_month=r.period_month,
        asset_class=r.asset_class,
        total_calls=r.total_calls,
        agent04_trusted=r.agent04_trusted,
        manual_overrides=r.manual_overrides,
        mismatches=r.mismatches,
        accuracy_rate=r.accuracy_rate,
        override_rate=r.override_rate,
        mismatch_rate=r.mismatch_rate,
        computed_at=r.computed_at,
        computed_by=r.computed_by,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/feedback", response_model=list[FeedbackResponse])
def list_feedback(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    source: Optional[str] = Query(None, description="Filter by source (AGENT04 | MANUAL_OVERRIDE)"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return recent classification feedback entries."""
    rows = classification_feedback_tracker.get_recent_feedback(
        db, ticker=ticker, source=source, limit=limit
    )
    return [_feedback_to_response(r) for r in rows]


@router.get("/runs", response_model=list[AccuracyRunResponse])
def list_accuracy_runs(
    period_month: Optional[str] = Query(None, description="Filter by period (YYYY-MM)"),
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return historical classifier accuracy rollup runs."""
    runs = classification_feedback_tracker.get_accuracy_runs(
        db, period_month=period_month, asset_class=asset_class, limit=limit
    )
    return [_run_to_response(r) for r in runs]


@router.post("/rollup", response_model=RollupResponse, status_code=201)
def trigger_rollup(
    req: RollupRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger monthly accuracy rollup for the given period.

    Aggregates ClassificationFeedback rows for the specified calendar month
    into ClassifierAccuracyRun rows (one per asset class + one ALL aggregate).

    Safe to call multiple times — each call creates new rollup rows.
    """
    # Validate period format
    try:
        year, month = req.period_month.split("-")
        assert len(year) == 4 and len(month) == 2
        int(year), int(month)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period_month '{req.period_month}'. Expected format: YYYY-MM",
        )

    # Count feedback entries before rollup
    from datetime import timedelta
    from calendar import monthrange
    y, m = int(year), int(month)
    _, last_day = monthrange(y, m)
    from datetime import timezone
    month_start = datetime(y, m, 1, tzinfo=timezone.utc)
    month_end   = datetime(y, m, last_day, 23, 59, 59, tzinfo=timezone.utc)
    total_entries = (
        db.query(ClassificationFeedback)
        .filter(
            ClassificationFeedback.captured_at >= month_start,
            ClassificationFeedback.captured_at <= month_end,
        )
        .count()
    )

    try:
        runs = classification_feedback_tracker.compute_monthly_rollup(
            db, req.period_month, computed_by=req.computed_by
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Monthly rollup failed for %s: %s", req.period_month, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollup failed: {exc}",
        )

    return RollupResponse(
        period_month=req.period_month,
        runs_created=len(runs),
        total_feedback_entries=total_entries,
    )
