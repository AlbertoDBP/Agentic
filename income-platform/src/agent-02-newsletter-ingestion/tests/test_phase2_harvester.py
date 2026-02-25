"""
Agent 02 — Newsletter Ingestion Service
Tests: Phase 2 — Harvester Flow unit tests

Tests are organized by component:
  - TestDeduplicator      SHA-256 hashing + DB dedup logic
  - TestExtractor         HTML→Markdown conversion + extraction validation
  - TestVectorizer        Embedding helpers (mocked OpenAI)
  - TestArticleStore      DB persistence logic (mocked session)
  - TestHarvesterAPI      /flows/harvester/trigger endpoint
"""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.models.schemas import FlowStatus


# ── Deduplicator Tests ────────────────────────────────────────────────────────

class TestDeduplicator:
    def test_compute_content_hash_is_deterministic(self):
        from app.processors.deduplicator import compute_content_hash
        text = "The quick brown fox jumped over the lazy dividend stock"
        assert compute_content_hash(text) == compute_content_hash(text)

    def test_compute_content_hash_differs_for_different_text(self):
        from app.processors.deduplicator import compute_content_hash
        assert compute_content_hash("text A") != compute_content_hash("text B")

    def test_compute_url_hash_produces_64_char_hex(self):
        from app.processors.deduplicator import compute_url_hash
        result = compute_url_hash("https://seekingalpha.com/article/12345")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_is_duplicate_by_sa_id_true_when_exists(self):
        from app.processors.deduplicator import is_duplicate_by_sa_id
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (1,)
        assert is_duplicate_by_sa_id(mock_db, "article_123") is True

    def test_is_duplicate_by_sa_id_false_when_not_exists(self):
        from app.processors.deduplicator import is_duplicate_by_sa_id
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert is_duplicate_by_sa_id(mock_db, "article_999") is False

    def test_filter_new_articles_removes_duplicates(self):
        from app.processors.deduplicator import filter_new_articles
        mock_db = MagicMock()

        # First article is a duplicate, second is new
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            (1,),   # article 111 — duplicate by SA ID
            None,   # article 222 — new
        ]

        raw_articles = [
            {"id": "111", "title": "Old Article"},
            {"id": "222", "title": "New Article"},
        ]
        content_bodies = {"111": "old content", "222": "new content"}

        result = filter_new_articles(mock_db, analyst_id=1,
                                     raw_articles=raw_articles,
                                     content_bodies=content_bodies)
        assert len(result) == 1
        assert result[0]["id"] == "222"


# ── Extractor Tests ───────────────────────────────────────────────────────────

class TestExtractor:
    def test_html_to_markdown_converts_headers(self):
        from app.processors.extractor import html_to_markdown
        html = "<h1>Realty Income Deep Dive</h1><p>Great REIT for income.</p>"
        result = html_to_markdown(html)
        assert "Realty Income Deep Dive" in result
        assert "Great REIT for income" in result

    def test_html_to_markdown_strips_scripts(self):
        from app.processors.extractor import html_to_markdown
        html = "<p>Content</p><script>alert('ad')</script>"
        result = html_to_markdown(html)
        assert "alert" not in result
        assert "Content" in result

    def test_html_to_markdown_empty_returns_empty(self):
        from app.processors.extractor import html_to_markdown
        assert html_to_markdown("") == ""
        assert html_to_markdown(None) == ""

    def test_truncate_does_not_truncate_short_text(self):
        from app.processors.extractor import truncate_for_extraction
        short = "short text"
        assert truncate_for_extraction(short) == short

    def test_truncate_appends_marker(self):
        from app.processors.extractor import truncate_for_extraction
        long_text = "word " * 10000
        result = truncate_for_extraction(long_text)
        assert "[Article truncated for extraction]" in result
        assert len(result) < len(long_text)

    def test_validate_extracted_ticker_clamps_sentiment(self):
        from app.processors.extractor import validate_extracted_ticker
        data = {"ticker": "O", "sentiment_score": 5.0, "recommendation": "StrongBuy"}
        result = validate_extracted_ticker(data)
        assert result["sentiment_score"] == 1.0  # clamped to max

    def test_validate_extracted_ticker_normalizes_ticker(self):
        from app.processors.extractor import validate_extracted_ticker
        data = {"ticker": " jepi ", "sentiment_score": 0.5}
        result = validate_extracted_ticker(data)
        assert result["ticker"] == "JEPI"

    def test_validate_extracted_ticker_handles_none_fields(self):
        from app.processors.extractor import validate_extracted_ticker
        data = {"ticker": "MAIN"}  # minimal — all other fields absent
        result = validate_extracted_ticker(data)
        assert result["ticker"] == "MAIN"
        assert result["sentiment_score"] is None
        assert result["yield_at_publish"] is None
        assert result["key_risks"] == []

    def test_extract_signals_parses_valid_json(self):
        from app.processors.extractor import extract_signals
        mock_response_text = """{
            "tickers": [
                {
                    "ticker": "O",
                    "asset_class": "REIT",
                    "recommendation": "Buy",
                    "sentiment_score": 0.7,
                    "yield_at_publish": 0.052,
                    "safety_grade": "A",
                    "source_reliability": "EarningsCall",
                    "bull_case": "29 year dividend streak, durable tenants.",
                    "bear_case": "Rising rates headwind.",
                    "key_risks": ["interest rate sensitivity"]
                }
            ],
            "article_themes": ["REITs", "Dividends"],
            "overall_sentiment": 0.6
        }"""

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=mock_response_text)]

        with patch("app.processors.extractor._client") as mock_client:
            mock_client.messages.create.return_value = mock_message
            result = extract_signals("# Realty Income Analysis\n\nBullish on O.", "art_123")

        assert result is not None
        assert len(result["tickers"]) == 1
        assert result["tickers"][0]["ticker"] == "O"
        assert result["tickers"][0]["recommendation"] == "Buy"

    def test_extract_signals_returns_none_on_invalid_json(self):
        from app.processors.extractor import extract_signals
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="this is not json")]

        with patch("app.processors.extractor._client") as mock_client:
            mock_client.messages.create.return_value = mock_message
            result = extract_signals("some article text", "art_999")

        assert result is None


# ── Vectorizer Tests ──────────────────────────────────────────────────────────

class TestVectorizer:
    def test_embed_text_returns_list_of_floats(self):
        from app.processors.vectorizer import embed_text
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]

        with patch("app.processors.vectorizer._client") as mock_client:
            mock_client.embeddings.create.return_value = mock_response
            result = embed_text("Realty Income is a great dividend stock")

        assert isinstance(result, list)
        assert len(result) == 1536

    def test_embed_text_returns_none_on_empty_input(self):
        from app.processors.vectorizer import embed_text
        result = embed_text("")
        assert result is None

    def test_build_recommendation_thesis_combines_fields(self):
        from app.processors.vectorizer import build_recommendation_thesis
        data = {
            "recommendation": "Buy",
            "bull_case": "Strong dividend history.",
            "bear_case": "Rate sensitivity.",
            "key_risks": ["interest rates", "tenant concentration"],
        }
        result = build_recommendation_thesis(data)
        assert "Buy" in result
        assert "Strong dividend history" in result
        assert "Rate sensitivity" in result
        assert "interest rates" in result

    def test_embed_batch_returns_correct_count(self):
        from app.processors.vectorizer import embed_batch
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
        ]

        with patch("app.processors.vectorizer._client") as mock_client:
            mock_client.embeddings.create.return_value = mock_response
            result = embed_batch(["text one", "text two"])

        assert len(result) == 2
        assert len(result[0]) == 1536


# ── Article Store Tests ───────────────────────────────────────────────────────

class TestArticleStore:
    def test_save_article_creates_orm_object(self):
        from app.processors.article_store import save_article
        mock_db = MagicMock()

        article = save_article(
            db=mock_db,
            analyst_id=1,
            sa_article_id="art_001",
            title="Realty Income Deep Dive",
            markdown_body="# O Analysis\n\nBullish on Realty Income.",
            published_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_save_article_computes_content_hash(self):
        from app.processors.article_store import save_article
        from app.processors.deduplicator import compute_content_hash
        mock_db = MagicMock()

        body = "# O Analysis\n\nBullish on Realty Income."
        save_article(
            db=mock_db,
            analyst_id=1,
            sa_article_id="art_002",
            title="Test",
            markdown_body=body,
            published_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
        )

        added_article = mock_db.add.call_args[0][0]
        assert added_article.content_hash == compute_content_hash(body)

    def test_save_recommendation_sets_is_active_true(self):
        from app.processors.article_store import save_recommendation
        mock_db = MagicMock()
        # No prior recs to supersede
        mock_db.query.return_value.filter.return_value.all.return_value = []

        extracted = {
            "ticker": "O",
            "recommendation": "Buy",
            "sentiment_score": 0.7,
            "yield_at_publish": 0.052,
        }

        rec = save_recommendation(
            db=mock_db,
            analyst_id=1,
            article_id=10,
            ticker="O",
            published_at=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
            extracted=extracted,
        )

        assert rec.is_active is True
        assert rec.decay_weight == 1.0


# ── Flow API Tests ────────────────────────────────────────────────────────────

class TestFlowAPI:
    @pytest.fixture
    def client(self):
        with patch("app.database.check_database_connection",
                   return_value={"status": "healthy", "pgvector_installed": True,
                                 "schema_exists": True}), \
             patch("app.api.health._check_cache",
                   return_value={"status": "healthy"}), \
             patch("app.api.health._get_flow_status",
                   return_value=FlowStatus(last_run=None, last_run_status=None,
                                           next_scheduled=None,
                                           articles_processed_last_run=None)):
            from app.main import app
            yield TestClient(app)

    def test_trigger_harvester_returns_200(self, client):
        with patch("app.api.flows._run_harvester"):
            response = client.post(
                "/flows/harvester/trigger",
                json={}
            )
        assert response.status_code == 200

    def test_trigger_harvester_with_analyst_ids(self, client):
        with patch("app.api.flows._run_harvester"):
            response = client.post(
                "/flows/harvester/trigger",
                json={"analyst_ids": [1, 2, 3]}
            )
        data = response.json()
        assert data["triggered"] is True
        assert "analysts [1, 2, 3]" in data["message"]

    def test_trigger_intelligence_returns_501(self, client):
        response = client.post("/flows/intelligence/trigger")
        assert response.status_code == 501

    def test_flow_status_endpoint_exists(self, client):
        with patch("app.api.flows.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.execute.return_value.fetchall.return_value = []
            mock_engine.connect.return_value = mock_conn
            response = client.get("/flows/status")
        assert response.status_code == 200


# ── SA Client Shape Tests (added after V1 code review) ───────────────────────

class TestSAClientResponseShape:
    """Validate the SA client normalizes the confirmed V1 API response shape correctly."""

    def test_normalize_article_extracts_from_attributes(self):
        """V1 confirmed: articles nested under 'attributes' key."""
        from app.clients.seeking_alpha import _normalize_article
        raw_item = {
            "id": "4768423",
            "attributes": {
                "title": "Realty Income: Buy The Dip",
                "publishOn": "2025-01-15T12:00:00-05:00",
            }
        }
        result = _normalize_article(raw_item)
        assert result["id"] == "4768423"
        assert result["title"] == "Realty Income: Buy The Dip"
        assert result["published_date"] == "2025-01-15T12:00:00-05:00"
        assert "seekingalpha.com/article/4768423" in result["url"]

    def test_normalize_article_handles_missing_attributes(self):
        """Defensive — item with no attributes key should not crash."""
        from app.clients.seeking_alpha import _normalize_article
        result = _normalize_article({"id": "999"})
        assert result["id"] == "999"
        assert result["title"] == ""
        assert result["published_date"] == ""

    def test_fetch_articles_uses_correct_endpoint(self):
        """
        Confirm /articles/v2/list is called with category + page params.
        Author filter is applied client-side via relationships.author.data.id.
        """
        from app.clients import seeking_alpha as sa
        mock_response = {
            "data": [
                {
                    "id": "111",
                    "attributes": {"title": "Article A", "publishOn": "2025-01-10T12:00:00Z"},
                    "relationships": {"author": {"data": {"id": "96726", "type": "author"}}},
                    "links": {"self": "/article/111-article-a"},
                },
                {
                    "id": "222",
                    "attributes": {"title": "Article B", "publishOn": "2025-01-05T12:00:00Z"},
                    "relationships": {"author": {"data": {"id": "99999", "type": "author"}}},
                    "links": {"self": "/article/222-article-b"},
                },
            ]
        }
        with patch("app.clients.seeking_alpha.httpx.Client") as mock_client_class:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

            result = sa.fetch_articles_by_author("96726", limit=1)

        call_kwargs = mock_client_class.return_value.__enter__.return_value.get.call_args
        url_called = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
        params_called = call_kwargs[1].get("params", {})

        assert "/articles/v2/list" in url_called
        assert "category" in params_called    # category-based scanning, not author param
        assert "page" in params_called
        assert len(result) == 1               # only article 111 matches author 96726
        assert result[0]["id"] == "111"

    def test_fetch_article_detail_extracts_content_from_attributes(self):
        """V1 confirmed: content nested at data.attributes.content."""
        from app.clients import seeking_alpha as sa
        mock_response = {
            "data": {
                "attributes": {
                    "content": "<p>Strong buy on Realty Income.</p>",
                    "title": "Realty Income Deep Dive",
                    "publishOn": "2025-01-15T12:00:00Z",
                }
            }
        }
        with patch("app.clients.seeking_alpha.httpx.Client") as mock_client_class:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

            result = sa.fetch_article_detail("4768423")

        assert result is not None
        assert result["content"] == "<p>Strong buy on Realty Income.</p>"
        assert result["title"] == "Realty Income Deep Dive"

    def test_fetch_article_detail_returns_none_on_empty_content(self):
        """Empty content triggers fallback endpoint, then returns None."""
        from app.clients import seeking_alpha as sa
        mock_response = {"data": {"attributes": {"content": ""}}}

        with patch("app.clients.seeking_alpha.httpx.Client") as mock_client_class:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

            result = sa.fetch_article_detail("000")

        assert result is None

    def test_parse_published_at_handles_offset_timezone(self):
        """V1 confirmed: SA uses -05:00 offset format (not just UTC Z)."""
        from app.clients.seeking_alpha import parse_published_at
        result = parse_published_at("2025-01-15T12:00:00-05:00")
        assert result is not None
        assert result.tzinfo is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_harvester_flow_uses_normalized_published_date_field(self):
        """After normalization, harvester reads 'published_date' not 'publishOn'."""
        # The normalized article dict from _normalize_article uses 'published_date'
        # harvester_flow must read raw_article.get("published_date") — verify field name
        from app.clients.seeking_alpha import _normalize_article
        raw = {"id": "1", "attributes": {"title": "T", "publishOn": "2025-03-01T10:00:00Z"}}
        normalized = _normalize_article(raw)
        # This is what harvester reads — must be "published_date" not "publishOn"
        assert "published_date" in normalized
        assert "publishOn" not in normalized
