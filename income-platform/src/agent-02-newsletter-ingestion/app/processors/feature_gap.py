"""
Agent 02 — Newsletter Ingestion Service
Processor: Feature Gap Detection + Resolution

detect_feature_gaps — called during Pass 2 to log unknown metrics
resolve_feature_gaps — called during Intelligence Flow to classify + register metrics
"""
import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    from app.config import settings as _settings
    _client = Anthropic(api_key=_settings.anthropic_api_key)
except Exception:
    _client = None

_CLASSIFY_PROMPT = """You are a financial data engineer. Given an analyst-cited metric name and asset class,
determine how it could be obtained.

Return ONLY valid JSON (no markdown fences):
{
  "category": "fetchable|derived|external",
  "source": "fmp|polygon|yfinance|derived|null",
  "fetch_config": {"endpoint": "/api/...", "field": "field_name"} or null,
  "computation_rule": "formula using stored fields" or null,
  "rationale": "one sentence explanation"
}

fetchable: available from FMP, Polygon, or yfinance APIs
derived: can be computed from data already stored in platform_shared.features_historical
external: requires a new data source not currently connected

Common income investment metrics:
- FFO_coverage, FFO_per_share: fetchable via FMP /financials endpoint
- NAV_discount: fetchable via FMP /etf/nav endpoint for ETFs/CEFs
- NII_coverage, NII_per_share: fetchable via FMP for BDCs
- dividend_coverage, payout_ratio: derived from EPS/DPS already stored
- yield_spread: derived from current_yield minus treasury_yield
- price_to_NAV: derived from price / NAV"""


def detect_feature_gaps(
    db: Session,
    article_id: int,
    analyst_id: int,
    metrics_cited: list[str],
    asset_class: Optional[str],
) -> int:
    """
    Log metrics that are not in feature_registry.
    Returns count of new gaps logged.
    """
    gaps_logged = 0
    for metric in metrics_cited:
        if not metric:
            continue
        # Check if metric exists in registry (name or alias)
        row = db.execute(text("""
            SELECT id FROM platform_shared.feature_registry
            WHERE feature_name = :name
               OR aliases::text ILIKE :like_name
            LIMIT 1
        """), {"name": metric, "like_name": f'%"{metric}"%'}).fetchone()

        if row:
            continue  # already known

        # Upsert into gap log
        db.execute(text("""
            INSERT INTO platform_shared.feature_gap_log
                (metric_name_raw, asset_class, article_id, analyst_id, occurrence_count)
            VALUES (:metric, :asset_class, :article_id, :analyst_id, 1)
            ON CONFLICT (metric_name_raw, asset_class)
            DO UPDATE SET occurrence_count = feature_gap_log.occurrence_count + 1
        """), {
            "metric": metric,
            "asset_class": asset_class,
            "article_id": article_id,
            "analyst_id": analyst_id,
        })
        gaps_logged += 1

    if gaps_logged > 0:
        db.commit()
        logger.debug(f"Article {article_id}: {gaps_logged} feature gaps logged")

    return gaps_logged


def classify_gap_category(metric_name: str, asset_class: Optional[str]) -> dict:
    """
    Use Haiku to classify a feature gap as fetchable, derived, or external.
    Returns classification dict. Returns {"category": "external"} on failure.
    """
    if _client is None:
        return {"category": "external", "source": None, "fetch_config": None, "computation_rule": None}

    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"{_CLASSIFY_PROMPT}\n\nMetric: {metric_name}\nAsset class: {asset_class or 'unknown'}",
            }],
        )
        result = json.loads(response.content[0].text.strip())
        if result.get("category") not in ("fetchable", "derived", "external"):
            result["category"] = "external"
        return result
    except Exception as e:
        logger.warning(f"Gap classification failed for '{metric_name}': {e}")
        return {"category": "external", "source": None, "fetch_config": None, "computation_rule": None}


def resolve_feature_gaps(db: Session) -> dict:
    """
    Process all pending feature_gap_log entries.
    Auto-registers Category 1 (fetchable) and Category 2 (derived) in feature_registry
    with validation_status='pending'. Category 3 remains unregistered.
    Returns summary dict.
    """
    pending = db.execute(text("""
        SELECT id, metric_name_raw, asset_class, occurrence_count
        FROM platform_shared.feature_gap_log
        WHERE resolution_status = 'pending'
        ORDER BY occurrence_count DESC
        LIMIT 50
    """)).fetchall()

    resolved = 0
    for row in pending:
        gap_id, metric_name, asset_class, _ = row

        classification = classify_gap_category(metric_name, asset_class)
        category = classification.get("category", "external")

        if category == "external":
            db.execute(text("""
                UPDATE platform_shared.feature_gap_log
                SET resolution_status = 'resolved_external'
                WHERE id = :gap_id
            """), {"gap_id": gap_id})
            db.commit()
            logger.info(f"Gap '{metric_name}': classified external — flagged for human review")
            continue

        # Category 1 or 2 — write to feature_registry (inactive, pending validation)
        status_key = "resolved_fetchable" if category == "fetchable" else "resolved_derived"
        try:
            db.execute(text("""
                INSERT INTO platform_shared.feature_registry
                    (feature_name, category, source, asset_classes,
                     fetch_config, computation_rule, is_active, validation_status)
                VALUES
                    (:name, :category, :source,
                     CAST(:asset_classes AS JSONB),
                     CAST(:fetch_config AS JSONB), :computation_rule,
                     FALSE, 'pending')
                ON CONFLICT (feature_name) DO NOTHING
            """), {
                "name": metric_name,
                "category": category,
                "source": classification.get("source"),
                "asset_classes": json.dumps([asset_class] if asset_class else []),
                "fetch_config": json.dumps(classification.get("fetch_config")),
                "computation_rule": classification.get("computation_rule"),
            })
            db.execute(text("""
                UPDATE platform_shared.feature_gap_log
                SET resolution_status = :status, resolved_at = NOW()
                WHERE id = :gap_id
            """), {"status": status_key, "gap_id": gap_id})
            db.commit()
            resolved += 1
            logger.info(f"Gap '{metric_name}': {category} — registered in feature_registry (pending validation)")
        except Exception as e:
            logger.warning(f"Failed to register gap '{metric_name}': {e}")

    return {"pending_processed": len(pending), "resolved": resolved}
