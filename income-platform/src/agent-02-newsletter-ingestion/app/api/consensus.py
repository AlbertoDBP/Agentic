"""
Agent 02 — Newsletter Ingestion Service
API: Consensus endpoint

GET /consensus/{ticker}   Weighted consensus score for a ticker

Calls the consensus processor directly — always computes fresh
from current active recommendations and analyst accuracy stats.
Results are cached in Redis for 30 minutes.
"""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AnalystRecommendation, Analyst
from app.models.schemas import ConsensusResponse, RecommendationLabel
from app.processors.consensus import compute_consensus_score
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_cache_client():
    """Redis client for consensus caching. Returns None if unavailable."""
    try:
        import redis
        return redis.from_url(settings.redis_url, socket_timeout=2, decode_responses=True)
    except Exception:
        return None


def _sentiment_to_label(score: float) -> str:
    """Map consensus sentiment score to dominant recommendation label."""
    if score is None:
        return None
    if score >= 0.6:
        return RecommendationLabel.STRONG_BUY
    elif score >= 0.2:
        return RecommendationLabel.BUY
    elif score >= -0.2:
        return RecommendationLabel.HOLD
    elif score >= -0.6:
        return RecommendationLabel.SELL
    else:
        return RecommendationLabel.STRONG_SELL


@router.get("/{ticker}", response_model=ConsensusResponse, tags=["Consensus"])
def get_consensus(
    ticker: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
):
    """
    Get weighted consensus score for a ticker.

    Consensus is computed from all active recommendations weighted by:
      analyst_accuracy × decay_weight × user_weight (default 1.0)

    Result is cached for 30 minutes. Use force_refresh=true to bypass cache.

    Returns score in range -1.0 (strong sell) to 1.0 (strong buy).
    confidence: high (≥3 analysts) | low (<3 analysts) | insufficient_data
    """
    ticker = ticker.upper().strip()
    cache_key = f"consensus:{ticker}"
    cache_client = _get_cache_client()

    # Check cache first (unless force refresh)
    if not force_refresh and cache_client:
        try:
            cached = cache_client.get(cache_key)
            if cached:
                logger.debug(f"Consensus cache hit for {ticker}")
                return ConsensusResponse(**json.loads(cached))
        except Exception as e:
            logger.warning(f"Cache read failed for {ticker}: {e}")

    # Load active recommendations
    recs = (
        db.query(AnalystRecommendation)
        .filter(AnalystRecommendation.ticker == ticker)
        .filter(AnalystRecommendation.is_active == True)
        .filter(AnalystRecommendation.decay_weight >= settings.default_min_decay_weight)
        .filter(AnalystRecommendation.sentiment_score.isnot(None))
        .all()
    )

    if not recs:
        raise HTTPException(
            status_code=404,
            detail=f"No active recommendations found for ticker {ticker}"
        )

    # Load analyst accuracy stats
    analyst_ids = {r.analyst_id for r in recs}
    analyst_stats = {
        a.id: float(a.overall_accuracy) if a.overall_accuracy else 0.5
        for a in db.query(Analyst).filter(Analyst.id.in_(analyst_ids)).all()
    }

    # Compute consensus
    result = compute_consensus_score(recs, analyst_stats)

    response = ConsensusResponse(
        ticker=ticker,
        score=result.get("score"),
        confidence=result.get("confidence", "insufficient_data"),
        n_analysts=result.get("n_analysts", 0),
        n_recommendations=len(recs),
        dominant_recommendation=_sentiment_to_label(result.get("score")),
        computed_at=datetime.now(timezone.utc),
    )

    # Cache result
    if cache_client:
        try:
            cache_client.setex(
                cache_key,
                settings.cache_ttl_consensus,
                json.dumps(response.model_dump(), default=str),
            )
        except Exception as e:
            logger.warning(f"Cache write failed for {ticker}: {e}")

    return response
