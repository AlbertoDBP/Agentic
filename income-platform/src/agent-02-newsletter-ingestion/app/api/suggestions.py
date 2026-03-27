"""
Agent 02 — Newsletter Ingestion Service
API: Analyst suggestions read endpoints + TTL configuration

GET /suggestions/analysts     List analysts with ≥1 active non-expired suggestion
GET /suggestions/ttl-config   Get configured TTL per asset class
PUT /suggestions/ttl-config   Update TTL config (upsert all rows)
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class TtlConfigItem(BaseModel):
    asset_class: str
    ttl_days: int = Field(..., ge=1, description="TTL in days (minimum 1)")


@router.get("/analysts")
def get_suggestion_analysts(db: Session = Depends(get_db)):
    """
    Return distinct analysts who have at least one active, non-expired suggestion.
    Used to populate the analyst filter dropdown on the Scanner page.
    """
    rows = db.execute(text("""
        SELECT DISTINCT a.id, a.display_name, a.overall_accuracy
        FROM platform_shared.analyst_suggestions s
        JOIN platform_shared.analysts a ON a.id = s.analyst_id
        WHERE s.is_active = TRUE
          AND s.expires_at > NOW()
        ORDER BY a.display_name
    """)).fetchall()
    return [{"id": r[0], "display_name": r[1], "overall_accuracy": r[2]} for r in rows]


@router.get("/ttl-config")
def get_ttl_config(db: Session = Depends(get_db)):
    """Return current TTL configuration for all asset classes."""
    rows = db.execute(text(
        "SELECT asset_class, ttl_days "
        "FROM platform_shared.suggestion_ttl_config "
        "ORDER BY CASE WHEN asset_class = '_default' THEN 0 ELSE 1 END, asset_class"
    )).fetchall()
    return [{"asset_class": r[0], "ttl_days": r[1]} for r in rows]


@router.put("/ttl-config")
def update_ttl_config(payload: List[TtlConfigItem], db: Session = Depends(get_db)):
    """
    Upsert TTL configuration rows.
    Accepts list of {asset_class, ttl_days}.
    Use asset_class = '_default' to set the global fallback.
    """
    if not payload:
        raise HTTPException(status_code=422, detail="Payload must not be empty")
    for item in payload:
        db.execute(text("""
            INSERT INTO platform_shared.suggestion_ttl_config (asset_class, ttl_days, updated_at)
            VALUES (:ac, :days, NOW())
            ON CONFLICT (asset_class) DO UPDATE
            SET ttl_days = EXCLUDED.ttl_days, updated_at = NOW()
        """), {"ac": item.asset_class, "days": item.ttl_days})
    db.commit()
    logger.info("Updated TTL config: %d rows", len(payload))
    return {"updated": len(payload)}
