"""Nightly analyst feature promotion from feature_gap_log."""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PROMOTION_THRESHOLD = 2  # occurrence_count >= 2


def run_promotion(db: Session) -> dict:
    """
    Promote qualifying feature_gap_log entries to field_requirements.
    New entries: required=FALSE, source='analyst_promoted', fetch_source_primary=NULL.
    """
    candidates = db.execute(text("""
        SELECT metric_name_raw, asset_class, id, occurrence_count
        FROM platform_shared.feature_gap_log
        WHERE occurrence_count >= :threshold
          AND resolution_status = 'pending'
          AND asset_class IS NOT NULL
    """), {"threshold": PROMOTION_THRESHOLD}).fetchall()

    promoted = 0
    skipped = 0

    for row in candidates:
        # Check not already in field_requirements
        existing = db.execute(
            text("SELECT id FROM platform_shared.field_requirements "
                 "WHERE asset_class = :ac AND field_name = :fn"),
            {"ac": row.asset_class, "fn": row.metric_name_raw},
        ).fetchone()

        if existing:
            skipped += 1
            continue

        db.execute(
            text("""
                INSERT INTO platform_shared.field_requirements
                    (asset_class, field_name, required, source, promoted_from_gap_id)
                VALUES (:ac, :fn, FALSE, 'analyst_promoted', :gap_id)
                ON CONFLICT (asset_class, field_name) DO NOTHING
            """),
            {"ac": row.asset_class, "fn": row.metric_name_raw, "gap_id": row.id},
        )
        # Mark gap log entry as promoted
        db.execute(
            text("UPDATE platform_shared.feature_gap_log "
                 "SET resolution_status='promoted' WHERE id=:id"),
            {"id": row.id},
        )
        promoted += 1

    db.commit()
    logger.info(f"Promotion complete: {promoted} promoted, {skipped} already present")
    return {"promoted": promoted, "skipped": skipped}
