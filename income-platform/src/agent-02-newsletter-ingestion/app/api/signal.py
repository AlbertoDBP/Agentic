"""
Agent 02 — Newsletter Ingestion Service
API: Signal endpoint — Agent 12 contract surface

GET /signal/{ticker}

Returns a complete AnalystSignalResponse consumed by Agent 12 (Proposal Agent).
This is the primary integration point between Agent 02 and the proposal pipeline.

Signal includes:
  - Best analyst recommendation (highest decay_weight × accuracy)
  - Full consensus across all analysts
  - Analyst profile (philosophy, accuracy, sector_alpha)
  - proposal_readiness flag — True when signal meets quality thresholds
  - signal_strength — strong | moderate | weak | insufficient

Cached for 1 hour (cache_ttl_analyst_signal). Use force_refresh=true to bypass.

Agent 12 calls: GET /signal/{ticker}?force_refresh=false
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.models import AnalystRecommendation, Analyst
from app.models.schemas import (
    AnalystSignalResponse, AnalystSignalAnalyst, AnalystSignalRecommendation,
    ConsensusResponse, RecommendationLabel, AssetClass, PhilosophySource,
)
from app.processors.consensus import compute_consensus_score
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_cache_client():
    try:
        import redis
        return redis.from_url(settings.redis_url, socket_timeout=2, decode_responses=True)
    except Exception:
        return None


def _sentiment_to_label(score: Optional[float]) -> Optional[RecommendationLabel]:
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


def _compute_signal_strength(
    n_analysts: int,
    top_decay_weight: float,
    top_analyst_accuracy: Optional[float],
) -> str:
    """
    Compute signal strength label from available data quality.
      strong:       ≥2 analysts, decay_weight ≥ 0.7, accuracy ≥ 0.65
      moderate:     ≥1 analyst,  decay_weight ≥ 0.4
      weak:         ≥1 analyst,  decay_weight < 0.4
      insufficient: no qualifying recommendations
    """
    if n_analysts == 0:
        return "insufficient"
    accuracy = top_analyst_accuracy or 0.5
    if n_analysts >= 2 and top_decay_weight >= 0.7 and accuracy >= 0.65:
        return "strong"
    elif top_decay_weight >= 0.4:
        return "moderate"
    else:
        return "weak"


def _compute_proposal_readiness(
    signal_strength: str,
    top_analyst_accuracy: Optional[float],
    min_accuracy: float,
) -> bool:
    """
    Proposal is ready when signal quality meets thresholds:
      - signal_strength is strong or moderate
      - analyst accuracy meets minimum threshold
    """
    if signal_strength not in ("strong", "moderate"):
        return False
    accuracy = top_analyst_accuracy or 0.0
    return accuracy >= min_accuracy


def _build_thesis_summary(metadata: Optional[dict]) -> Optional[str]:
    """Combine bull_case and bear_case into a 2-sentence thesis summary."""
    if not metadata:
        return None
    parts = []
    if metadata.get("bull_case"):
        parts.append(metadata["bull_case"])
    if metadata.get("bear_case"):
        parts.append(metadata["bear_case"])
    return " ".join(parts) if parts else None


@router.get("/{ticker}", response_model=AnalystSignalResponse, tags=["Signal"])
def get_signal(
    ticker: str,
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Get complete analyst signal for a ticker — consumed by Agent 12.

    Returns the strongest available signal combining:
    - Best individual recommendation (highest decay_weight × analyst accuracy)
    - Weighted consensus across all active analysts
    - Full analyst profile for context

    proposal_readiness=true means Agent 12 can immediately generate a proposal.
    proposal_readiness=false means signal exists but quality thresholds not met.

    404 if no active recommendations exist for ticker.
    """
    ticker = ticker.upper().strip()
    cache_key = f"signal:{ticker}"
    cache_client = _get_cache_client()

    # Cache check
    if not force_refresh and cache_client:
        try:
            cached = cache_client.get(cache_key)
            if cached:
                logger.debug(f"Signal cache hit for {ticker}")
                return AnalystSignalResponse(**json.loads(cached))
        except Exception as e:
            logger.warning(f"Signal cache read failed for {ticker}: {e}")

    # ── Load active recommendations ───────────────────────────────────────────
    recs = (
        db.query(AnalystRecommendation)
        .filter(AnalystRecommendation.ticker == ticker)
        .filter(AnalystRecommendation.is_active == True)
        .filter(AnalystRecommendation.decay_weight >= settings.default_min_decay_weight)
        .order_by(desc(AnalystRecommendation.decay_weight))
        .all()
    )

    if not recs:
        raise HTTPException(
            status_code=404,
            detail=f"No active recommendations found for ticker {ticker}"
        )

    # ── Load analyst profiles ─────────────────────────────────────────────────
    analyst_ids = {r.analyst_id for r in recs}
    analysts_map: dict[int, Analyst] = {
        a.id: a
        for a in db.query(Analyst).filter(Analyst.id.in_(analyst_ids)).all()
    }

    analyst_stats = {
        aid: float(a.overall_accuracy) if a.overall_accuracy else 0.5
        for aid, a in analysts_map.items()
    }

    # ── Select best recommendation ────────────────────────────────────────────
    # Best = highest (decay_weight × analyst_accuracy) combined score
    def rec_score(r):
        acc = analyst_stats.get(r.analyst_id, 0.5)
        return float(r.decay_weight) * acc

    best_rec = max(recs, key=rec_score)
    best_analyst = analysts_map.get(best_rec.analyst_id)

    # ── Compute consensus ─────────────────────────────────────────────────────
    consensus_recs = [r for r in recs if r.sentiment_score is not None]
    consensus_result = compute_consensus_score(consensus_recs, analyst_stats)

    # ── Compute signal metadata ───────────────────────────────────────────────
    top_accuracy = analyst_stats.get(best_rec.analyst_id)
    signal_strength = _compute_signal_strength(
        n_analysts=len(analyst_ids),
        top_decay_weight=float(best_rec.decay_weight),
        top_analyst_accuracy=top_accuracy,
    )
    proposal_readiness = _compute_proposal_readiness(
        signal_strength=signal_strength,
        top_analyst_accuracy=top_accuracy,
        min_accuracy=settings.default_min_accuracy_threshold,
    )

    # ── Build response ────────────────────────────────────────────────────────
    metadata = best_rec.rec_metadata or {}

    analyst_signal = AnalystSignalAnalyst(
        id=best_analyst.id if best_analyst else best_rec.analyst_id,
        display_name=best_analyst.display_name if best_analyst else "Unknown",
        accuracy_overall=best_analyst.overall_accuracy if best_analyst else None,
        sector_alpha=best_analyst.sector_alpha if best_analyst else None,
        philosophy_summary=best_analyst.philosophy_summary if best_analyst else None,
        philosophy_source=(
            PhilosophySource(best_analyst.philosophy_source)
            if best_analyst and best_analyst.philosophy_source
            else PhilosophySource.LLM
        ),
        philosophy_tags=best_analyst.philosophy_tags if best_analyst else None,
    )

    rec_signal = AnalystSignalRecommendation(
        id=best_rec.id,
        label=_sentiment_to_label(float(best_rec.sentiment_score) if best_rec.sentiment_score else None),
        sentiment_score=best_rec.sentiment_score,
        yield_at_publish=best_rec.yield_at_publish,
        payout_ratio=best_rec.payout_ratio,
        safety_grade=best_rec.safety_grade,
        source_reliability=best_rec.source_reliability,
        thesis_summary=_build_thesis_summary(metadata),
        bull_case=metadata.get("bull_case"),
        bear_case=metadata.get("bear_case"),
        published_at=best_rec.published_at,
        decay_weight=best_rec.decay_weight,
    )

    consensus = ConsensusResponse(
        ticker=ticker,
        score=consensus_result.get("score"),
        confidence=consensus_result.get("confidence", "insufficient_data"),
        n_analysts=consensus_result.get("n_analysts", 0),
        n_recommendations=len(consensus_recs),
        dominant_recommendation=_sentiment_to_label(consensus_result.get("score")),
        computed_at=datetime.now(timezone.utc),
    )

    response = AnalystSignalResponse(
        ticker=ticker,
        asset_class=(
            AssetClass(best_rec.asset_class)
            if best_rec.asset_class and best_rec.asset_class in AssetClass._value2member_map_
            else None
        ),
        sector=best_rec.sector,
        signal_strength=signal_strength,
        proposal_readiness=proposal_readiness,
        analyst=analyst_signal,
        recommendation=rec_signal,
        consensus=consensus,
        platform_alignment=best_rec.platform_alignment,
        generated_at=datetime.now(timezone.utc),
    )

    # Cache result
    if cache_client:
        try:
            cache_client.setex(
                cache_key,
                settings.cache_ttl_analyst_signal,
                json.dumps(response.model_dump(), default=str),
            )
        except Exception as e:
            logger.warning(f"Signal cache write failed for {ticker}: {e}")

    logger.info(
        f"Signal generated for {ticker}: strength={signal_strength} "
        f"proposal_ready={proposal_readiness} analysts={len(analyst_ids)}"
    )
    return response
