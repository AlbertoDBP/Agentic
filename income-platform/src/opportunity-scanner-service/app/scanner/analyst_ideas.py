# src/opportunity-scanner-service/app/scanner/analyst_ideas.py
"""
Agent 07 — Opportunity Scanner Service
Analyst Ideas: reads analyst_suggestions from platform_shared.

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
    "sourced_at", "expires_at", "article_framework_id", "is_active",
]


def fetch_active_suggestions(
    conn,
    min_staleness_weight: float = 0.3,
    asset_classes: Optional[list] = None,
    analyst_ids: Optional[list] = None,
    include_history: bool = False,
) -> list:
    """
    Query platform_shared.analyst_suggestions joined with analysts.
    When include_history=False (default): only is_active=TRUE rows.
    When include_history=True: all rows within TTL window (active + historical).
    Each result dict includes is_proposed + proposed_at from proposal_drafts.
    """
    active_filter = "" if include_history else "AND s.is_active = TRUE"

    query = f"""
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
            s.article_framework_id,
            s.is_active
        FROM platform_shared.analyst_suggestions s
        JOIN platform_shared.analysts a ON a.id = s.analyst_id
        WHERE s.expires_at > NOW()
          AND s.staleness_weight >= :staleness_weight
          {active_filter}
    """
    params: dict = {"staleness_weight": min_staleness_weight}

    if asset_classes:
        query += " AND s.asset_class = ANY(:asset_classes)"
        params["asset_classes"] = asset_classes

    if analyst_ids:
        query += " AND s.analyst_id = ANY(:analyst_ids)"
        params["analyst_ids"] = analyst_ids

    query += " ORDER BY s.is_active DESC, s.staleness_weight DESC, s.sourced_at DESC"

    rows = conn.execute(text(query), params).fetchall()
    result = []
    for row in rows:
        row_dict = dict(zip(_SUGGESTION_COLUMNS, row))
        row_dict.setdefault("is_active", True)
        result.append(row_dict)

    # Annotate is_proposed + proposed_at from proposal_drafts
    if result:
        tickers_in_result = [r["ticker"] for r in result]
        proposed_rows = conn.execute(text("""
            SELECT elem->>'ticker'   AS ticker,
                   MAX(pd.created_at) AS proposed_at
            FROM platform_shared.proposal_drafts pd,
                 jsonb_array_elements(pd.tickers) elem
            WHERE pd.status IN ('DRAFT', 'PENDING', 'ACCEPTED')
              AND elem->>'ticker' = ANY(:tickers)
            GROUP BY elem->>'ticker'
        """), {"tickers": tickers_in_result}).fetchall()
        proposed_map: dict = {r[0]: str(r[1]) for r in proposed_rows}
        for row_dict in result:
            row_dict["is_proposed"] = row_dict["ticker"] in proposed_map
            row_dict["proposed_at"] = proposed_map.get(row_dict["ticker"])

    logger.info("Fetched %d analyst suggestions (include_history=%s)", len(result), include_history)
    return result


def build_analyst_context(suggestion_row: dict) -> dict:
    """Build the analyst_context dict attached to each ScanItem."""
    return {
        "analyst_id":           suggestion_row.get("analyst_id"),
        "analyst_name":         suggestion_row.get("analyst_name"),
        "analyst_accuracy":     suggestion_row.get("analyst_accuracy"),
        "analyst_sector_alpha": suggestion_row.get("analyst_sector_alpha"),
        "price_guidance_type":  suggestion_row.get("price_guidance_type"),
        "price_guidance_value": suggestion_row.get("price_guidance_value"),
        "staleness_weight":     suggestion_row.get("staleness_weight"),
        "sourced_at":           str(suggestion_row["sourced_at"]) if suggestion_row.get("sourced_at") else None,
        "recommendation":       suggestion_row.get("recommendation"),
        "is_active":            bool(suggestion_row.get("is_active", True)),
        "is_proposed":          bool(suggestion_row.get("is_proposed", False)),
        "proposed_at":          suggestion_row.get("proposed_at"),
    }
