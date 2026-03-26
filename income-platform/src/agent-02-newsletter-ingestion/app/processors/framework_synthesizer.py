"""
Agent 02 — Newsletter Ingestion Service
Processor: Framework Synthesizer (Intelligence Flow stage)

synthesize_analyst_frameworks(db, analyst_id) -> dict

Aggregates article_frameworks per analyst × asset_class into
analyst_framework_profiles. Called during Intelligence Flow.
"""
import json
import logging
from collections import Counter
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    from app.config import settings as _settings
    _llm_client = Anthropic(api_key=_settings.anthropic_api_key)
except Exception:
    _llm_client = None


def compute_metric_frequency(frameworks: list[dict]) -> dict:
    """
    Return {metric_name: frequency} where frequency = occurrences / total articles.
    """
    if not frameworks:
        return {}
    total = len(frameworks)
    counter: Counter = Counter()
    for fw in frameworks:
        for metric in (fw.get("valuation_metrics_cited") or []):
            counter[metric] += 1
    return {m: round(count / total, 6) for m, count in counter.items()}


def compute_consistency_score(frameworks: list[dict]) -> float:
    """
    Percentage of articles that share BOTH:
      - The modal reasoning_structure
      - All three of the top-3 most frequent valuation_metrics_cited
    """
    if not frameworks:
        return 0.0

    # Find modal reasoning structure
    reasoning_counter: Counter = Counter(
        fw.get("reasoning_structure") for fw in frameworks if fw.get("reasoning_structure")
    )
    if not reasoning_counter:
        return 0.0
    modal_reasoning = reasoning_counter.most_common(1)[0][0]

    # Find top-3 metrics
    metric_freq = compute_metric_frequency(frameworks)
    top3 = set(sorted(metric_freq, key=metric_freq.get, reverse=True)[:3])

    # Count articles that match both
    matching = 0
    for fw in frameworks:
        has_modal = fw.get("reasoning_structure") == modal_reasoning
        article_metrics = set(fw.get("valuation_metrics_cited") or [])
        has_top3 = top3.issubset(article_metrics) if top3 else True
        if has_modal and has_top3:
            matching += 1

    return round(matching / len(frameworks), 4)


def synthesize_analyst_frameworks(db: Session, analyst_id: int) -> dict:
    """
    Aggregate all article_frameworks for this analyst into
    analyst_framework_profiles (one row per asset_class).
    Returns summary dict.
    """
    # Get all distinct asset_classes for this analyst via their recommendations
    asset_classes_result = db.execute(text("""
        SELECT DISTINCT r.asset_class
        FROM platform_shared.analyst_recommendations r
        WHERE r.analyst_id = :analyst_id
          AND r.asset_class IS NOT NULL
    """), {"analyst_id": analyst_id}).fetchall()

    asset_classes = [row[0] for row in asset_classes_result]
    profiles_updated = 0

    for asset_class in asset_classes:
        rows = db.execute(text("""
            SELECT
                af.valuation_metrics_cited,
                af.thresholds_identified,
                af.reasoning_structure,
                af.conviction_level,
                af.catalysts,
                af.evaluation_narrative
            FROM platform_shared.article_frameworks af
            JOIN platform_shared.analyst_recommendations r
                ON r.article_id = af.article_id
                AND r.analyst_id = af.analyst_id
                AND r.ticker = af.ticker
            WHERE af.analyst_id = :analyst_id
              AND r.asset_class = :asset_class
        """), {"analyst_id": analyst_id, "asset_class": asset_class}).fetchall()

        if not rows:
            continue

        frameworks = [
            {
                "valuation_metrics_cited": row[0] or [],
                "thresholds_identified": row[1] or {},
                "reasoning_structure": row[2],
                "conviction_level": row[3],
                "catalysts": row[4] or [],
                "evaluation_narrative": row[5] or "",
            }
            for row in rows
        ]

        metric_frequency = compute_metric_frequency(frameworks)
        consistency_score = compute_consistency_score(frameworks)

        reasoning_counter: Counter = Counter(
            fw["reasoning_structure"] for fw in frameworks if fw["reasoning_structure"]
        )
        preferred_reasoning = reasoning_counter.most_common(1)[0][0] if reasoning_counter else None

        threshold_agg: dict = {}
        for fw in frameworks:
            for metric, val in (fw["thresholds_identified"] or {}).items():
                threshold_agg.setdefault(metric, []).append(str(val))

        narratives = [fw["evaluation_narrative"] for fw in frameworks if fw["evaluation_narrative"]]
        framework_summary = _synthesize_summary(analyst_id, asset_class, narratives)

        db.execute(text("""
            INSERT INTO platform_shared.analyst_framework_profiles
                (analyst_id, asset_class, metric_frequency, typical_thresholds,
                 preferred_reasoning_style, consistency_score,
                 article_count, framework_summary, synthesized_at)
            VALUES
                (:analyst_id, :asset_class,
                 CAST(:metric_freq AS JSONB), CAST(:thresholds AS JSONB),
                 :reasoning, :consistency, :article_count, :summary, NOW())
            ON CONFLICT (analyst_id, asset_class) DO UPDATE SET
                metric_frequency          = EXCLUDED.metric_frequency,
                typical_thresholds        = EXCLUDED.typical_thresholds,
                preferred_reasoning_style = EXCLUDED.preferred_reasoning_style,
                consistency_score         = EXCLUDED.consistency_score,
                article_count             = EXCLUDED.article_count,
                framework_summary         = EXCLUDED.framework_summary,
                synthesized_at            = NOW()
        """), {
            "analyst_id": analyst_id,
            "asset_class": asset_class,
            "metric_freq": json.dumps(metric_frequency),
            "thresholds": json.dumps(threshold_agg),
            "reasoning": preferred_reasoning,
            "consistency": float(consistency_score),
            "article_count": len(frameworks),
            "summary": framework_summary,
        })
        db.commit()
        profiles_updated += 1
        logger.info(f"Analyst {analyst_id} / {asset_class}: framework profile synthesized ({len(frameworks)} articles)")

    return {"analyst_id": analyst_id, "profiles_updated": profiles_updated}


def _synthesize_summary(analyst_id: int, asset_class: str, narratives: list[str]) -> Optional[str]:
    """Call Sonnet to produce a concise framework summary from evaluation narratives."""
    if not narratives or _llm_client is None:
        return None
    try:
        combined = "\n\n---\n\n".join(narratives[:20])
        response = _llm_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    f"Based on these analyst evaluation narratives for {asset_class} investments, "
                    f"write a concise 2-3 sentence summary of this analyst's evaluation framework: "
                    f"what metrics they prioritize, what thresholds they use, and their reasoning style.\n\n"
                    f"{combined}"
                ),
            }],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Framework summary synthesis failed for analyst {analyst_id} / {asset_class}: {e}")
        return None
