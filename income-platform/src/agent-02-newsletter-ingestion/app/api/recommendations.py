"""
Agent 02 — Newsletter Ingestion Service
API: Recommendations endpoints

GET /recommendations/{ticker}   All active recommendations for a ticker
                                Ordered by decay_weight desc (strongest signal first)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.models import AnalystRecommendation, Analyst
from app.models.schemas import RecommendationResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{ticker}", tags=["Recommendations"])
def get_recommendations_for_ticker(
    ticker: str,
    active_only: bool = True,
    min_decay_weight: float = Query(0.1, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get all analyst recommendations for a given ticker.

    Returns recommendations ordered by decay_weight descending —
    freshest, highest-weighted signals appear first.

    Args:
        ticker: Stock symbol (case-insensitive)
        active_only: Exclude superseded recommendations (default True)
        min_decay_weight: Minimum decay weight threshold (default 0.1)
        limit: Max results to return
    """
    ticker = ticker.upper().strip()

    query = (
        db.query(AnalystRecommendation)
        .filter(AnalystRecommendation.ticker == ticker)
        .filter(AnalystRecommendation.decay_weight >= min_decay_weight)
    )

    if active_only:
        query = query.filter(AnalystRecommendation.is_active == True)

    recs = query.order_by(desc(AnalystRecommendation.decay_weight)).limit(limit).all()

    if not recs:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendations found for ticker {ticker}"
        )

    # Enrich with analyst display name for convenience
    analyst_ids = {r.analyst_id for r in recs}
    analysts = {
        a.id: a.display_name
        for a in db.query(Analyst).filter(Analyst.id.in_(analyst_ids)).all()
    }

    return {
        "ticker": ticker,
        "total": len(recs),
        "recommendations": [
            {
                **RecommendationResponse.model_validate(r).model_dump(),
                "analyst_name": analysts.get(r.analyst_id, "Unknown"),
            }
            for r in recs
        ],
    }
