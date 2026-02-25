"""
Agent 02 — Newsletter Ingestion Service
Client: APIDojo Seeking Alpha API wrapper

CONFIRMED API SHAPE (current — updated 2026):
  List (category): GET /articles/v2/list
  Params:          category={cat}, page={n}, size=20
  Note:            Author filter params are ignored — filter client-side by
                   relationships.author.data.id == sa_author_id
  Categories:      dividends, income-investing, closed-end-funds, reits

  Detail endpoint: GET /analysis/v2/get-details
  Params:          id={article_id}
  Response:        {"data": {"attributes": {"content": "<html>...", "title": "..."}}}
  Note:            Returns FULL content (19k+ chars). accessToken header unlocks paywalled.

  Author IDs are numeric strings (e.g. Rida Morwa = "96726").
  The author.id in article relationships matches sa_publishing_id exactly.
"""
import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = f"https://{settings.apidojo_sa_host}"


def _build_headers() -> dict:
    headers = {
        "X-RapidAPI-Key": settings.apidojo_sa_api_key,
        "X-RapidAPI-Host": settings.apidojo_sa_host,
    }
    if getattr(settings, "sa_access_token", None):
        headers["accessToken"] = settings.sa_access_token
    return headers


_last_call_times: list[float] = []


def _rate_limit():
    now = time.time()
    window = 60.0
    global _last_call_times
    _last_call_times = [t for t in _last_call_times if now - t < window]
    if len(_last_call_times) >= settings.sa_calls_per_minute:
        sleep_for = window - (now - _last_call_times[0]) + 0.1
        logger.debug(f"Rate limit reached — sleeping {sleep_for:.1f}s")
        time.sleep(sleep_for)
    _last_call_times.append(time.time())


def _normalize_article(item: dict) -> dict:
    """
    Normalize raw SA article item from list endpoint.
    Raw: {"id": "4768423", "attributes": {"title": "...", "publishOn": "..."}}
    Returns flat dict for use throughout the pipeline.
    """
    attrs = item.get("attributes", {})
    return {
        "id": str(item.get("id", "")),
        "title": attrs.get("title", ""),
        "published_date": attrs.get("publishOn", ""),
        "url": f"https://seekingalpha.com/article/{item.get('id', '')}",
    }


def fetch_articles_by_author(
    sa_author_id: str,
    limit: int = None,
    until_article_id: Optional[str] = None,
) -> list[dict]:
    """
    Fetch recent articles for a given SA analyst by author ID.

    APIDojo /articles/v2/list does not support author filtering as of 2026.
    Workaround: fetch income-relevant category pages and filter client-side by
    relationships.author.data.id == sa_author_id. Scans up to MAX_SCAN_PAGES
    pages per category before moving on.

    Args:
        sa_author_id: SA numeric author ID (equals relationships.author.data.id)
        limit: max articles to return
        until_article_id: stop when this article ID is encountered (dedup boundary)
    """
    limit = limit or settings.sa_fetch_limit_per_analyst

    INCOME_CATEGORIES = ["dividends", "income-investing", "closed-end-funds", "reits"]
    MAX_SCAN_PAGES = 3   # 60 articles per category before moving on
    PAGE_SIZE = 20

    seen_ids: set[str] = set()
    articles: list[dict] = []

    for category in INCOME_CATEGORIES:
        if len(articles) >= limit:
            break
        pages_without_match = 0

        for page in range(1, MAX_SCAN_PAGES + 1):
            if len(articles) >= limit:
                break
            try:
                _rate_limit()
                with httpx.Client(timeout=settings.sa_request_timeout) as client:
                    response = client.get(
                        f"{_BASE_URL}/articles/v2/list",
                        headers=_build_headers(),
                        params={"category": category, "page": page, "size": PAGE_SIZE},
                    )
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"SA list error ({category} p{page}): {e.response.status_code}")
                break
            except Exception as e:
                logger.error(f"SA list unexpected error ({category} p{page}): {e}")
                break

            raw_items = data.get("data", [])
            if not raw_items:
                break

            found_in_page = 0
            for item in raw_items:
                rel_author = (item.get("relationships", {})
                              .get("author", {})
                              .get("data", {})
                              .get("id", ""))
                if rel_author != sa_author_id:
                    continue
                article_id = str(item.get("id", ""))
                if article_id in seen_ids:
                    continue
                if until_article_id and article_id == until_article_id:
                    logger.debug(f"Hit known article {article_id} — stopping fetch")
                    logger.info(f"Fetched {len(articles)} articles for author {sa_author_id}")
                    return articles
                seen_ids.add(article_id)
                articles.append(_normalize_article(item))
                found_in_page += 1
                if len(articles) >= limit:
                    break

            if found_in_page == 0:
                pages_without_match += 1
                if pages_without_match >= 2:
                    break  # author unlikely to appear deeper in this category
            else:
                pages_without_match = 0

            time.sleep(1)  # polite pause between pages

    logger.info(f"Fetched {len(articles)} articles for author {sa_author_id}")
    return articles


def fetch_article_detail(sa_article_id: str) -> Optional[dict]:
    """
    Fetch full article content (HTML) for a given article ID.

    Uses /analysis/v2/get-details (confirmed working 2026, returns full HTML).
    Response: {"data": {"attributes": {"content": "<html>", "title": "...", "publishOn": "..."}}}

    Returns normalized dict: {"content": "<html>", "title": "...", "published_date": "..."}
    or None on failure.
    """
    try:
        _rate_limit()
        with httpx.Client(timeout=settings.sa_request_timeout) as client:
            response = client.get(
                f"{_BASE_URL}/analysis/v2/get-details",
                headers=_build_headers(),
                params={"id": sa_article_id},
            )
            response.raise_for_status()
            data = response.json()

        attrs = data.get("data", {}).get("attributes", {})
        content = attrs.get("content", "")

        if not content:
            logger.warning(f"Article {sa_article_id}: empty content from /analysis/v2/get-details")
            return None

        logger.debug(f"Fetched detail for article {sa_article_id} ({len(content)} chars)")
        return {
            "content": content,
            "title": attrs.get("title", ""),
            "published_date": attrs.get("publishOn", ""),
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"SA detail HTTP error for article {sa_article_id}: "
                     f"{e.response.status_code} — {e.response.text[:200]}")
    except httpx.TimeoutException:
        logger.error(f"SA detail timeout for article {sa_article_id}")
    except Exception as e:
        logger.error(f"SA detail unexpected error for article {sa_article_id}: {e}")

    return None


def build_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_published_at(raw_date: str) -> Optional[datetime]:
    """Parse SA publishOn string to timezone-aware datetime."""
    if not raw_date:
        return None
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        logger.warning(f"Could not parse date: {raw_date}")
        return None
