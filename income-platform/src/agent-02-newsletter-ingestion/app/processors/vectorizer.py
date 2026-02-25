"""
Agent 02 — Newsletter Ingestion Service
Processor: OpenAI text embeddings

Generates 1536-dim text-embedding-3-small vectors for:
  - Article body (semantic article search)
  - Recommendation theses (thesis similarity)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level OpenAI client — patched in tests
try:
    from openai import OpenAI
    from app.config import settings as _settings
    _client = OpenAI(api_key=_settings.openai_api_key)
except Exception:
    _client = None


def embed_text(text: str) -> Optional[list[float]]:
    """Embed a single text string. Returns None on empty input or API failure."""
    if not text or not text.strip():
        return None
    if not _client:
        logger.warning("OpenAI client not initialized — embeddings disabled")
        return None
    try:
        from app.config import settings
        response = _client.embeddings.create(
            model=settings.embedding_model,
            input=[text],
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def embed_batch(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Embed a list of texts in a single API call.
    Returns a list of embeddings (None entries on failure).
    """
    if not texts:
        return []
    if not _client:
        return [None] * len(texts)
    try:
        from app.config import settings
        response = _client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Batch embedding error: {e}")
        return [None] * len(texts)


def build_recommendation_thesis(data: dict) -> str:
    """
    Build a thesis text string from extracted recommendation fields.
    Used as input to embed_text for thesis-level semantic search.
    """
    parts = []
    rec = data.get("recommendation")
    if rec:
        parts.append(f"Recommendation: {rec}")
    bull = data.get("bull_case")
    if bull:
        parts.append(f"Bull case: {bull}")
    bear = data.get("bear_case")
    if bear:
        parts.append(f"Bear case: {bear}")
    risks = data.get("key_risks") or []
    if risks:
        parts.append(f"Key risks: {', '.join(risks)}")
    return " | ".join(parts)
