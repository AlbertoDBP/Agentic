"""
Agent 02 — Newsletter Ingestion Service
API: Knowledge Base endpoints

GET /kb/analyst-context  — enriched analyst context for Agent 12 proposal commentary
GET /analysts/{id}/framework — all framework profiles for an analyst
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_framework_profile(db: Session, analyst_id: int, asset_class: Optional[str]) -> Optional[dict]:
    """Fetch best matching framework profile for analyst + optional asset_class filter."""
    query = """
        SELECT analyst_id, asset_class, metric_frequency, typical_thresholds,
               preferred_reasoning_style, consistency_score, framework_summary, article_count
        FROM platform_shared.analyst_framework_profiles
        WHERE analyst_id = :analyst_id
    """
    params = {"analyst_id": analyst_id}
    if asset_class:
        query += " AND asset_class = :asset_class"
        params["asset_class"] = asset_class
    query += " ORDER BY article_count DESC LIMIT 1"

    row = db.execute(text(query), params).fetchone()
    if not row:
        return None
    return dict(zip(
        ["analyst_id","asset_class","metric_frequency","typical_thresholds",
         "preferred_reasoning_style","consistency_score","framework_summary","article_count"],
        row
    ))


def _get_analyst_profiles(db: Session, analyst_id: int) -> Optional[dict]:
    """Fetch all framework profiles for an analyst."""
    analyst = db.execute(text("""
        SELECT id, display_name FROM platform_shared.analysts WHERE id = :id
    """), {"id": analyst_id}).fetchone()
    if not analyst:
        return None

    rows = db.execute(text("""
        SELECT asset_class, metric_frequency, typical_thresholds,
               preferred_reasoning_style, consistency_score,
               framework_summary, article_count, synthesized_at
        FROM platform_shared.analyst_framework_profiles
        WHERE analyst_id = :analyst_id
        ORDER BY article_count DESC
    """), {"analyst_id": analyst_id}).fetchall()

    return {
        "analyst_id": analyst_id,
        "display_name": analyst[1],
        "profiles": [
            dict(zip(
                ["asset_class","metric_frequency","typical_thresholds",
                 "preferred_reasoning_style","consistency_score",
                 "framework_summary","article_count","synthesized_at"],
                row
            ))
            for row in rows
        ]
    }


@router.get("/kb/analyst-context")
def get_analyst_context(
    analyst_id: int = Query(...),
    ticker: str = Query(...),
    asset_class: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Returns enriched analyst context for a ticker.
    Consumed by Agent 12 for proposal commentary enrichment.
    """
    ticker = ticker.upper()

    analyst_row = db.execute(text("""
        SELECT id, display_name, overall_accuracy, sector_alpha
        FROM platform_shared.analysts WHERE id = :id
    """), {"id": analyst_id}).fetchone()
    if not analyst_row:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")

    profile = _get_framework_profile(db, analyst_id, asset_class)

    framework_row = db.execute(text("""
        SELECT ticker, valuation_metrics_cited, thresholds_identified,
               conviction_level, price_guidance_type, price_guidance_value,
               evaluation_narrative
        FROM platform_shared.article_frameworks
        WHERE analyst_id = :analyst_id AND ticker = :ticker
        ORDER BY extracted_at DESC LIMIT 1
    """), {"analyst_id": analyst_id, "ticker": ticker}).fetchone()

    signal_row = db.execute(text("""
        SELECT sentiment_score, recommendation, decay_weight
        FROM platform_shared.analyst_recommendations
        WHERE analyst_id = :analyst_id AND ticker = :ticker AND is_active = TRUE
        ORDER BY decay_weight DESC LIMIT 1
    """), {"analyst_id": analyst_id, "ticker": ticker}).fetchone()

    if not profile and not framework_row:
        raise HTTPException(
            status_code=404,
            detail=f"No framework data found for analyst {analyst_id} / {ticker}"
        )

    return {
        "analyst": {
            "id": analyst_row[0],
            "display_name": analyst_row[1],
            "overall_accuracy": float(analyst_row[2]) if analyst_row[2] else None,
            "sector_alpha": analyst_row[3],
        },
        "framework_profile": profile,
        "article_framework": dict(zip(
            ["ticker","valuation_metrics_cited","thresholds_identified",
             "conviction_level","price_guidance_type","price_guidance_value","evaluation_narrative"],
            framework_row
        )) if framework_row else None,
        "signal": dict(zip(
            ["sentiment_score","label","decay_weight"], signal_row
        )) if signal_row else None,
    }


@router.get("/analysts/{analyst_id}/framework")
def get_analyst_framework(
    analyst_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Returns all synthesized framework profiles for an analyst."""
    result = _get_analyst_profiles(db, analyst_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Analyst {analyst_id} not found")
    if not result["profiles"]:
        raise HTTPException(
            status_code=404,
            detail=f"No framework profiles synthesized yet for analyst {analyst_id}"
        )
    return result
