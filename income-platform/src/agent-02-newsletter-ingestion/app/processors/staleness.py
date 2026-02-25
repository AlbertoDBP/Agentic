"""
Agent 02 — Newsletter Ingestion Service
Processor: S-curve decay sweeper

Recomputes decay_weight for all active analyst recommendations.
Marks is_active=False for recommendations whose expires_at has passed
(i.e., days_elapsed >= aging_days → decay_weight rounds to 0.0).

S-curve formula (locked in architecture session):
  k = 10 / aging_days
  weight = 1 / (1 + exp(k * (days_elapsed - halflife_days)))
  hard floor: min_weight (never goes below this while is_active=True)
  deactivates when expires_at is passed (decay_weight set to 0.0)

Per-analyst config override: analyst.config may specify {aging_days, aging_halflife_days}.
Falls back to service-level settings.default_aging_* when not set.
"""
import logging
from datetime import datetime, timezone
from math import exp
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Analyst, AnalystRecommendation
from app.config import settings

logger = logging.getLogger(__name__)


def compute_decay_weight(
    published_at: datetime,
    aging_days: int = None,
    halflife_days: int = None,
    min_weight: float = None,
) -> float:
    """
    Compute S-curve decay weight for a recommendation.

    Args:
        published_at:  Publication datetime (timezone-aware UTC).
        aging_days:    Days after which recommendation expires (decay_weight → 0).
                       Defaults to settings.default_aging_days (365).
        halflife_days: S-curve inflection point — half-weight at this many days.
                       Defaults to settings.default_aging_halflife_days (180).
        min_weight:    Hard floor — returned weight never goes below this.
                       Defaults to settings.default_min_decay_weight (0.1).

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 once aging_days is reached.
    """
    aging_days = aging_days or settings.default_aging_days
    halflife_days = halflife_days or settings.default_aging_halflife_days
    min_weight = min_weight if min_weight is not None else settings.default_min_decay_weight

    # Ensure published_at is timezone-aware
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    days_elapsed = (datetime.now(timezone.utc) - published_at).days

    if days_elapsed <= 0:
        return 1.0
    if days_elapsed >= aging_days:
        return 0.0

    k = 10.0 / aging_days
    weight = 1.0 / (1.0 + exp(k * (days_elapsed - halflife_days)))
    return max(weight, min_weight)


def sweep_analyst_staleness(
    db: Session,
    analyst_id: int,
    analyst_config: Optional[dict] = None,
) -> dict:
    """
    Recompute decay_weight for all active recommendations of one analyst.

    Per-analyst config keys (from analyst.config JSONB):
      - aging_days          override service default
      - aging_halflife_days override service default

    Marks is_active=False where compute_decay_weight returns 0.0.

    Returns summary dict: {updated, deactivated}
    """
    config = analyst_config or {}
    aging_days = config.get("aging_days", settings.default_aging_days)
    halflife_days = config.get("aging_halflife_days", settings.default_aging_halflife_days)
    min_weight = settings.default_min_decay_weight

    active_recs = (
        db.query(AnalystRecommendation)
        .filter(
            AnalystRecommendation.analyst_id == analyst_id,
            AnalystRecommendation.is_active == True,
        )
        .all()
    )

    updated = 0
    deactivated = 0

    for rec in active_recs:
        new_weight = compute_decay_weight(
            published_at=rec.published_at,
            aging_days=aging_days,
            halflife_days=halflife_days,
            min_weight=min_weight,
        )

        old_weight = float(rec.decay_weight) if rec.decay_weight is not None else 1.0

        if new_weight == 0.0:
            rec.decay_weight = 0.0
            rec.is_active = False
            deactivated += 1
            updated += 1
            logger.debug(
                f"Deactivated rec {rec.id} ({rec.ticker}): "
                f"aged out at {aging_days} days"
            )
        elif abs(new_weight - old_weight) > 0.0001:
            rec.decay_weight = round(new_weight, 4)
            updated += 1

    logger.info(
        f"Staleness sweep for analyst {analyst_id}: "
        f"{len(active_recs)} recs checked, "
        f"{updated} updated, {deactivated} deactivated"
    )
    return {"updated": updated, "deactivated": deactivated}


def sweep_all_analysts(db: Session) -> dict:
    """
    Run staleness sweep across all active analysts.

    Returns aggregate summary: {analysts_processed, total_updated, total_deactivated}
    """
    analysts = (
        db.query(Analyst)
        .filter(Analyst.is_active == True)
        .all()
    )

    total_updated = 0
    total_deactivated = 0

    for analyst in analysts:
        result = sweep_analyst_staleness(
            db=db,
            analyst_id=analyst.id,
            analyst_config=analyst.config or {},
        )
        total_updated += result["updated"]
        total_deactivated += result["deactivated"]

    logger.info(
        f"Global staleness sweep complete: "
        f"{len(analysts)} analysts, "
        f"{total_updated} recs updated, "
        f"{total_deactivated} deactivated"
    )
    return {
        "analysts_processed": len(analysts),
        "total_updated": total_updated,
        "total_deactivated": total_deactivated,
    }
