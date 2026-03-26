"""
Agent 02 — Newsletter Ingestion Service
Processor: Pass 2 — Analyst Framework Extraction (Claude Sonnet)

extract_frameworks(markdown, pass1_signals, article_sa_id) -> list[dict]

Receives article markdown + Pass 1 ticker signals.
Returns one ArticleFramework dict per ticker analyzed.
Returns [] on any failure — Pass 1 is unaffected.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_CHARS = 18_000

try:
    from anthropic import Anthropic
    from app.config import settings as _settings
    _client = Anthropic(api_key=_settings.anthropic_api_key)
except Exception:
    _client = None

_FRAMEWORK_PROMPT = """You are an income investment research analyst. \
Analyze how the analyst evaluated each investment in this article.

You are given the article text AND the structured signals already extracted (Pass 1).
Use Pass 1 signals to understand what the analyst concluded.
Your job is to determine HOW they evaluated it: what metrics, thresholds, and reasoning.

Return ONLY valid JSON (no markdown fences): a JSON array, one object per ticker.

Each object:
{
  "ticker": "TICKER",
  "valuation_metrics_cited": ["FFO_coverage", "NAV_discount"],
  "thresholds_identified": {"NAV_discount": ">15%", "FFO_coverage": ">=1.2x"},
  "reasoning_structure": "bottom_up",
  "conviction_level": "high",
  "catalysts": ["fed_pause", "portfolio_quality_improving"],
  "price_guidance_type": "none",
  "price_guidance_value": null,
  "risk_factors_cited": ["rising_defaults"],
  "macro_factors": ["rate_environment_stabilizing"],
  "evaluation_narrative": "One paragraph: how this analyst evaluated this specific ticker."
}

reasoning_structure values: top_down | bottom_up | catalyst_driven | value_driven
conviction_level: high | medium | low — infer from language intensity and certainty, not position sizing
price_guidance_type: explicit_target | implied_yield | implied_nav | none
price_guidance_value: null if type=none, else {"type": "...", "value": 0.085, "implied_price": 20.50}

Only include tickers where the article provides actual analysis. Use [] if none found.
Use snake_case for metric names (e.g. FFO_coverage, NAV_discount, yield_spread, payout_ratio)."""


def extract_frameworks(
    markdown: str,
    pass1_signals: dict,
    article_sa_id: str,
) -> list[dict]:
    """
    Pass 2: Extract analyst evaluation frameworks using Claude Sonnet.

    Returns a list of validated ArticleFramework dicts (one per ticker).
    Returns [] on any failure — never raises.
    """
    if _client is None:
        logger.warning("Framework extractor: Anthropic client not initialized")
        return []

    truncated = markdown[:_MAX_CHARS]
    pass1_json = json.dumps(pass1_signals, indent=2)[:3_000]

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{_FRAMEWORK_PROMPT}\n\n"
                        f"## Pass 1 Signals (already extracted):\n{pass1_json}\n\n"
                        f"## Article:\n{truncated}"
                    ),
                }
            ],
        )
        raw = response.content[0].text.strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            logger.warning(f"Article {article_sa_id}: Pass 2 returned non-list JSON")
            return []
    except json.JSONDecodeError as e:
        logger.warning(f"Article {article_sa_id}: Pass 2 JSON parse failed: {e}")
        return []
    except Exception as e:
        logger.warning(f"Article {article_sa_id}: Pass 2 extraction failed: {e}")
        return []

    validated = []
    for fw in parsed:
        result = validate_framework(fw)
        if result:
            validated.append(result)

    logger.info(f"Article {article_sa_id}: Pass 2 extracted {len(validated)} frameworks")
    return validated


def validate_framework(fw: dict) -> Optional[dict]:
    """Validate and normalize a raw framework dict. Returns None if invalid."""
    if not isinstance(fw, dict):
        return None
    if not fw.get("ticker"):
        return None

    # Normalize with defaults
    return {
        "ticker": str(fw["ticker"]).upper(),
        "valuation_metrics_cited": fw.get("valuation_metrics_cited") or [],
        "thresholds_identified": fw.get("thresholds_identified") or {},
        "reasoning_structure": fw.get("reasoning_structure") or "bottom_up",
        "conviction_level": fw.get("conviction_level") or "medium",
        "catalysts": fw.get("catalysts") or [],
        "price_guidance_type": fw.get("price_guidance_type") or "none",
        "price_guidance_value": fw.get("price_guidance_value"),
        "risk_factors_cited": fw.get("risk_factors_cited") or [],
        "macro_factors": fw.get("macro_factors") or [],
        "evaluation_narrative": fw.get("evaluation_narrative") or "",
    }
