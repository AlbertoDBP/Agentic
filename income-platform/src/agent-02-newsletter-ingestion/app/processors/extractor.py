"""
Agent 02 — Newsletter Ingestion Service
Processor: HTML→Markdown conversion + Claude Haiku signal extraction

Two responsibilities:
  1. html_to_markdown   — strips ads/scripts, converts to plain Markdown
  2. extract_signals    — calls Claude Haiku to extract structured income signals
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_EXTRACTION_CHARS = 15_000
_TRUNCATION_MARKER = "[Article truncated for extraction]"

# Module-level Anthropic client — patched in tests
try:
    from anthropic import Anthropic
    from app.config import settings as _settings
    _client = Anthropic(api_key=_settings.anthropic_api_key)
except Exception:
    _client = None

_EXTRACTION_PROMPT = """You are an income investment analyst assistant. \
Extract structured investment signals from the article below.

Return ONLY valid JSON (no markdown fences) with this exact structure:
{
  "tickers": [
    {
      "ticker": "TICKER",
      "asset_class": "CommonStock|REIT|MLP|BDC|Preferred|CEF|ETF",
      "recommendation": "StrongBuy|Buy|Hold|Sell|StrongSell",
      "sentiment_score": 0.7,
      "yield_at_publish": 0.052,
      "payout_ratio": 0.85,
      "dividend_cagr_3yr": 0.05,
      "dividend_cagr_5yr": null,
      "safety_grade": "A",
      "source_reliability": "EarningsCall|10K|10Q|PressRelease|Commentary",
      "bull_case": "...",
      "bear_case": "...",
      "key_risks": ["risk1", "risk2"]
    }
  ],
  "article_themes": ["REITs", "Dividends"],
  "overall_sentiment": 0.5
}

Only include tickers explicitly analyzed. Use null for fields you cannot determine."""


def html_to_markdown(html: str) -> str:
    """Convert HTML article body to Markdown, stripping scripts/styles/ads."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        import markdownify
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        return markdownify.markdownify(str(soup), heading_style="ATX").strip()
    except ImportError:
        # Fallback: regex-based tag stripping
        import html as html_lib
        text = re.sub(r"<script[^>]*>.*?</script>", "", html,
                      flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text,
                      flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return html_lib.unescape(text).strip()


def truncate_for_extraction(text: str, max_chars: int = _MAX_EXTRACTION_CHARS) -> str:
    """Truncate text to fit within Claude's extraction window."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n{_TRUNCATION_MARKER}"


def extract_signals(markdown: str, sa_article_id: str) -> Optional[dict]:
    """
    Call Claude Haiku to extract structured income signals from Markdown.
    Returns parsed dict or None on failure.
    """
    if not _client:
        logger.error("Anthropic client not initialized — check ANTHROPIC_API_KEY")
        return None

    truncated = truncate_for_extraction(markdown)
    try:
        from app.config import settings
        response = _client.messages.create(
            model=settings.extraction_model,
            max_tokens=settings.extraction_max_tokens,
            messages=[{
                "role": "user",
                "content": f"{_EXTRACTION_PROMPT}\n\nARTICLE:\n{truncated}",
            }],
        )
        raw_text = response.content[0].text.strip()
        # Strip markdown code fences if model adds them
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        return json.loads(raw_text)

    except json.JSONDecodeError as e:
        logger.warning(f"Article {sa_article_id}: extraction returned invalid JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Article {sa_article_id}: extraction error: {e}")
        return None


def validate_extracted_ticker(data: dict) -> dict:
    """
    Normalise and validate a single ticker dict from Claude extraction output.
    - Strips/uppercases ticker symbol
    - Clamps sentiment_score to [-1.0, 1.0]
    - Ensures key_risks is always a list
    - Returns None for fields absent from input
    """
    ticker = str(data.get("ticker", "")).strip().upper()

    sentiment = data.get("sentiment_score")
    if sentiment is not None:
        try:
            sentiment = float(sentiment)
            sentiment = max(-1.0, min(1.0, sentiment))
        except (TypeError, ValueError):
            sentiment = None

    yield_val = data.get("yield_at_publish")
    if yield_val is not None:
        try:
            yield_val = float(yield_val)
        except (TypeError, ValueError):
            yield_val = None

    key_risks = data.get("key_risks")
    if not isinstance(key_risks, list):
        key_risks = []

    return {
        "ticker": ticker,
        "asset_class": data.get("asset_class"),
        "recommendation": data.get("recommendation"),
        "sentiment_score": sentiment,
        "yield_at_publish": yield_val,
        "payout_ratio": data.get("payout_ratio"),
        "dividend_cagr_3yr": data.get("dividend_cagr_3yr"),
        "dividend_cagr_5yr": data.get("dividend_cagr_5yr"),
        "safety_grade": data.get("safety_grade"),
        "source_reliability": data.get("source_reliability"),
        "bull_case": data.get("bull_case"),
        "bear_case": data.get("bear_case"),
        "key_risks": key_risks,
    }
