# src/opportunity-scanner-service/app/scanner/analyst_ideas.py
"""
Agent 07 — Opportunity Scanner Service
Analyst Ideas: reads active analyst_suggestions from platform_shared.

Agent 02 is NOT called at runtime — data is read directly from the shared DB.
"""
import logging
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

_SUGGESTION_COLUMNS = [
    "ticker", "asset_class", "recommendation", "sentiment_score",
    "analyst_id", "analyst_name", "analyst_accuracy", "analyst_sector_alpha",
    "price_guidance_type", "price_guidance_value", "staleness_weight",
    "sourced_at", "expires_at", "article_framework_id",
]


def fetch_active_suggestions(
    conn,
    min_staleness_weight: float = 0.3,
    asset_classes: Optional[list[str]] = None,
    analyst_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Query platform_shared.analyst_suggestions joined with analysts.
    Returns list of suggestion dicts ready for scoring by the scan engine.
    """
    query = """
        SELECT
            s.ticker,
            s.asset_class,
            s.recommendation,
            s.sentiment_score,
            s.analyst_id,
            a.display_name          AS analyst_name,
            a.overall_accuracy      AS analyst_accuracy,
            a.sector_alpha          AS analyst_sector_alpha,
            s.price_guidance_type,
            s.price_guidance_value,
            s.staleness_weight,
            s.sourced_at,
            s.expires_at,
            s.article_framework_id
        FROM platform_shared.analyst_suggestions s
        JOIN platform_shared.analysts a ON a.id = s.analyst_id
        WHERE s.is_active = TRUE
          AND s.expires_at > NOW()
          AND s.staleness_weight >= :staleness_weight
    """
    params: dict = {"staleness_weight": min_staleness_weight}

    if asset_classes:
        query += " AND s.asset_class = ANY(:asset_classes)"
        params["asset_classes"] = asset_classes

    if analyst_ids:
        query += " AND s.analyst_id = ANY(:analyst_ids)"
        params["analyst_ids"] = analyst_ids

    query += " ORDER BY s.staleness_weight DESC, s.sourced_at DESC"

    rows = conn.execute(text(query), params).fetchall()
    result = []
    for row in rows:
        row_dict = dict(zip(_SUGGESTION_COLUMNS, row))
        result.append(row_dict)

    logger.info(f"Fetched {len(result)} active analyst suggestions")
    return result


def build_analyst_context(suggestion_row: dict) -> dict:
    """Build the analyst context dict attached to scan results."""
    return {
        "analyst_id": suggestion_row.get("analyst_id"),
        "analyst_name": suggestion_row.get("analyst_name"),
        "analyst_accuracy": suggestion_row.get("analyst_accuracy"),
        "analyst_sector_alpha": suggestion_row.get("analyst_sector_alpha"),
        "price_guidance_type": suggestion_row.get("price_guidance_type"),
        "price_guidance_value": suggestion_row.get("price_guidance_value"),
        "staleness_weight": suggestion_row.get("staleness_weight"),
        "sourced_at": suggestion_row.get("sourced_at"),
        "recommendation": suggestion_row.get("recommendation"),
    }
