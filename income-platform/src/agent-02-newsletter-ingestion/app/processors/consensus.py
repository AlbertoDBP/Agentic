"""
Agent 02 — Newsletter Ingestion Service
Processor: Weighted consensus score builder

Computes a weighted consensus score for each ticker that has at least one
active analyst recommendation. Results are written to Redis cache.

Formula (locked in architecture session):
  weight   = analyst_accuracy * decay_weight * user_weight
  score    = Σ(sentiment_score * weight) / Σ(weight)
  Analysts with overall_accuracy < MIN_ACCURACY are excluded.

Output per ticker:
  {
    "score": 0.62,           # -1.0 to 1.0
    "confidence": "high",    # high (≥3 analysts) | low
    "n_analysts": 3,
    "tickers": ["O", ...]    # passthrough for bulk rebuilds
  }

Cache key: consensus:{ticker}
Cache TTL: settings.cache_ttl_consensus (default 1800s)
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Analyst, AnalystRecommendation
from app.config import settings

logger = logging.getLogger(__name__)

_MIN_ACCURACY = 0.5      # analysts below this are excluded from consensus
_HIGH_CONFIDENCE_N = 3   # minimum analysts for "high" confidence rating

# Module-level Redis client — patched in tests
try:
    import redis as _redis_lib
    _redis = _redis_lib.from_url(settings.redis_url, decode_responses=True)
except Exception:
    _redis = None


def compute_consensus_score(
    recommendations: list[AnalystRecommendation],
    analyst_stats: dict[int, float],
    user_weights: Optional[dict[int, float]] = None,
) -> dict:
    """
    Compute weighted consensus score from a list of active recommendations
    for a single ticker.

    Args:
        recommendations:  Active AnalystRecommendation rows for the ticker.
        analyst_stats:    Dict mapping analyst_id → overall_accuracy (float).
        user_weights:     Optional dict mapping analyst_id → user trust multiplier.
                          Defaults to 1.0 for all analysts.

    Returns:
        {
            "score": float | None,        # weighted sentiment score
            "confidence": str,            # "high" | "low" | "insufficient_data"
            "n_analysts": int,
        }
    """
    user_weights = user_weights or {}
    numerator = 0.0
    denominator = 0.0
    qualifying_analysts = set()

    for rec in recommendations:
        analyst_acc = float(analyst_stats.get(rec.analyst_id, 0.5))

        if analyst_acc < _MIN_ACCURACY:
            continue  # exclude low-accuracy analysts

        decay = float(rec.decay_weight) if rec.decay_weight is not None else 1.0
        sentiment = float(rec.sentiment_score) if rec.sentiment_score is not None else 0.0
        user_mult = float(user_weights.get(rec.analyst_id, 1.0))

        weight = analyst_acc * decay * user_mult
        numerator += sentiment * weight
        denominator += weight
        qualifying_analysts.add(rec.analyst_id)

    n = len(qualifying_analysts)

    if denominator == 0 or n == 0:
        return {"score": None, "confidence": "insufficient_data", "n_analysts": 0}

    score = numerator / denominator
    confidence = "high" if n >= _HIGH_CONFIDENCE_N else "low"

    return {
        "score": round(score, 4),
        "confidence": confidence,
        "n_analysts": n,
    }


def rebuild_consensus_for_ticker(
    db: Session,
    ticker: str,
    analyst_stats: dict[int, float],
    user_weights: Optional[dict[int, float]] = None,
) -> dict:
    """
    Rebuild and cache the consensus score for a single ticker.

    Queries active recommendations for the ticker, computes score, writes to Redis.
    Returns the consensus result dict.
    """
    active_recs = (
        db.query(AnalystRecommendation)
        .filter(
            AnalystRecommendation.ticker == ticker,
            AnalystRecommendation.is_active == True,
        )
        .all()
    )

    result = compute_consensus_score(active_recs, analyst_stats, user_weights)
    result["ticker"] = ticker

    # Write to Redis cache
    if _redis:
        try:
            cache_key = f"consensus:{ticker}"
            _redis.setex(cache_key, settings.cache_ttl_consensus, json.dumps(result))
            logger.debug(f"Cached consensus for {ticker}: score={result.get('score')}")
        except Exception as e:
            logger.warning(f"Redis write failed for consensus:{ticker}: {e}")

    return result


def rebuild_consensus_for_analyst(
    db: Session,
    analyst_id: int,
) -> dict:
    """
    Rebuild consensus scores for all tickers where an analyst has active recs.

    Fetches analyst accuracy stats for all involved analysts and computes
    weighted consensus per ticker.

    Returns:
        {"tickers_rebuilt": int, "results": [...]}
    """
    # Get distinct tickers this analyst has active recs on
    ticker_rows = (
        db.query(AnalystRecommendation.ticker)
        .filter(
            AnalystRecommendation.analyst_id == analyst_id,
            AnalystRecommendation.is_active == True,
        )
        .distinct()
        .all()
    )
    tickers = [row[0] for row in ticker_rows]

    if not tickers:
        logger.info(f"Analyst {analyst_id}: no active tickers — skipping consensus rebuild")
        return {"tickers_rebuilt": 0, "results": []}

    # Load accuracy stats for all analysts who have recs on these tickers
    all_analyst_ids = (
        db.query(AnalystRecommendation.analyst_id)
        .filter(
            AnalystRecommendation.ticker.in_(tickers),
            AnalystRecommendation.is_active == True,
        )
        .distinct()
        .all()
    )
    analyst_id_list = [row[0] for row in all_analyst_ids]

    analysts = (
        db.query(Analyst)
        .filter(Analyst.id.in_(analyst_id_list))
        .all()
    )
    analyst_stats = {
        a.id: float(a.overall_accuracy) if a.overall_accuracy is not None else 0.5
        for a in analysts
    }

    results = []
    for ticker in tickers:
        try:
            result = rebuild_consensus_for_ticker(db, ticker, analyst_stats)
            results.append(result)
        except Exception as e:
            logger.error(f"Consensus rebuild error for {ticker}: {e}")
            continue

    logger.info(
        f"Analyst {analyst_id}: consensus rebuilt for "
        f"{len(results)}/{len(tickers)} tickers"
    )
    return {"tickers_rebuilt": len(results), "results": results}


def rebuild_all_consensus(db: Session) -> dict:
    """
    Full consensus rebuild: recompute scores for all tickers with active recs.

    Used at the end of the Intelligence Flow after staleness sweep and backtest.
    Returns aggregate summary.
    """
    # All tickers with at least one active recommendation
    ticker_rows = (
        db.query(AnalystRecommendation.ticker)
        .filter(AnalystRecommendation.is_active == True)
        .distinct()
        .all()
    )
    all_tickers = [row[0] for row in ticker_rows]

    if not all_tickers:
        logger.info("No active recommendations — consensus rebuild skipped")
        return {"tickers_rebuilt": 0}

    # Preload all analyst accuracy stats in one query
    analysts = db.query(Analyst).filter(Analyst.is_active == True).all()
    analyst_stats = {
        a.id: float(a.overall_accuracy) if a.overall_accuracy is not None else 0.5
        for a in analysts
    }

    rebuilt = 0
    for ticker in all_tickers:
        try:
            rebuild_consensus_for_ticker(db, ticker, analyst_stats)
            rebuilt += 1
        except Exception as e:
            logger.error(f"Full consensus rebuild error for {ticker}: {e}")
            continue

    logger.info(f"Full consensus rebuild complete: {rebuilt}/{len(all_tickers)} tickers")
    return {"tickers_rebuilt": rebuilt, "total_tickers": len(all_tickers)}
