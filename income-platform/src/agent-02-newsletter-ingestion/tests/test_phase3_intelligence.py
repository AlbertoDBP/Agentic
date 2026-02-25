"""
Agent 02 — Newsletter Ingestion Service
Tests: Phase 3 — Intelligence Flow unit tests

Organized by component:
  - TestFMPClient          FMP client helpers (mocked httpx)
  - TestStaleness          S-curve decay + sweep logic (mocked DB)
  - TestBacktest           Outcome labelling + accuracy update (mocked DB + FMP)
  - TestPhilosophy         LLM and K-Means synthesis (mocked clients)
  - TestConsensus          Weighted score computation
  - TestIntelligenceAPI    /flows/intelligence/trigger endpoint
"""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from app.models.schemas import FlowStatus


# ── FMP Client Tests ──────────────────────────────────────────────────────────

class TestFMPClient:

    def test_safe_float_converts_numeric_string(self):
        from app.clients.fmp_client import _safe_float
        assert _safe_float("12.34") == pytest.approx(12.34)

    def test_safe_float_returns_none_for_none(self):
        from app.clients.fmp_client import _safe_float
        assert _safe_float(None) is None

    def test_safe_float_returns_none_for_invalid(self):
        from app.clients.fmp_client import _safe_float
        assert _safe_float("not-a-number") is None

    def test_date_str_formats_correctly(self):
        from app.clients.fmp_client import _date_str
        dt = datetime(2025, 3, 15, 10, 0, tzinfo=timezone.utc)
        assert _date_str(dt) == "2025-03-15"

    def test_fetch_price_at_date_returns_closest_after_target(self):
        from app.clients import fmp_client
        mock_data = {
            "historical": [
                {"date": "2025-01-16", "close": 55.00},  # first trading day after target
                {"date": "2025-01-17", "close": 56.00},
                {"date": "2025-01-15", "close": 54.00},  # exact target (if market open)
            ]
        }
        target = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)
        with patch("app.clients.fmp_client._get", return_value=mock_data):
            price = fmp_client.fetch_price_at_date("O", target)
        # Should return price on or immediately after target date
        assert price == pytest.approx(54.00)  # 2025-01-15 >= target

    def test_fetch_price_at_date_handles_list_response(self):
        from app.clients import fmp_client
        # FMP sometimes returns a plain list
        mock_data = [
            {"date": "2025-02-01", "close": 60.00},
        ]
        target = datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)
        with patch("app.clients.fmp_client._get", return_value=mock_data):
            price = fmp_client.fetch_price_at_date("MAIN", target)
        assert price == pytest.approx(60.00)

    def test_fetch_price_at_date_returns_none_when_no_data(self):
        from app.clients import fmp_client
        with patch("app.clients.fmp_client._get", return_value=None):
            price = fmp_client.fetch_price_at_date("XYZ", datetime.now(timezone.utc))
        assert price is None

    def test_fetch_price_at_date_returns_none_for_empty_history(self):
        from app.clients import fmp_client
        with patch("app.clients.fmp_client._get", return_value={"historical": []}):
            price = fmp_client.fetch_price_at_date("XYZ", datetime.now(timezone.utc))
        assert price is None

    def test_fetch_price_t30_t90_skips_future_dates(self):
        from app.clients import fmp_client
        # Published 15 days ago — T+30 and T+90 are both in the future
        published_at = datetime.now(timezone.utc) - timedelta(days=15)
        with patch("app.clients.fmp_client.fetch_price_at_date") as mock_fetch:
            price_t30, price_t90 = fmp_client.fetch_price_at_t30_t90("O", published_at)
        # Neither fetch should be called
        mock_fetch.assert_not_called()
        assert price_t30 is None
        assert price_t90 is None

    def test_fetch_price_t30_t90_fetches_t30_when_ready(self):
        from app.clients import fmp_client
        # Published 35 days ago → T+30 ready, T+90 still future
        published_at = datetime.now(timezone.utc) - timedelta(days=35)
        with patch("app.clients.fmp_client.fetch_price_at_date", return_value=42.0) as mock_fetch:
            price_t30, price_t90 = fmp_client.fetch_price_at_t30_t90("O", published_at)
        assert price_t30 == pytest.approx(42.0)
        assert price_t90 is None  # T+90 still future
        assert mock_fetch.call_count == 1  # only T+30 fetched

    def test_detect_dividend_cut_no_cut(self):
        from app.clients import fmp_client
        # Stable dividends — no cut
        all_divs = [
            {"date": "2025-01-10", "dividend": 0.25},
            {"date": "2024-10-10", "dividend": 0.25},
            {"date": "2024-07-10", "dividend": 0.25},
            {"date": "2024-04-10", "dividend": 0.25},
        ]
        published = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with patch("app.clients.fmp_client.fetch_dividends_in_window", return_value=all_divs):
            cut_occurred, cut_at = fmp_client.detect_dividend_cut("O", published)
        assert cut_occurred is False
        assert cut_at is None

    def test_detect_dividend_cut_detects_reduction(self):
        from app.clients import fmp_client
        # Baseline 0.25, then cut to 0.10 (>10% reduction)
        all_divs = [
            {"date": "2024-07-10", "dividend": 0.25},  # pre-publish baseline
            {"date": "2024-10-10", "dividend": 0.25},
            {"date": "2025-02-10", "dividend": 0.10},  # cut after publish date
        ]
        published = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with patch("app.clients.fmp_client.fetch_dividends_in_window", return_value=all_divs):
            cut_occurred, cut_at = fmp_client.detect_dividend_cut("XYZ", published)
        assert cut_occurred is True
        assert cut_at is not None

    def test_detect_dividend_cut_returns_false_on_no_dividends(self):
        from app.clients import fmp_client
        published = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with patch("app.clients.fmp_client.fetch_dividends_in_window", return_value=[]):
            cut_occurred, cut_at = fmp_client.detect_dividend_cut("XYZ", published)
        assert cut_occurred is False

    def test_fetch_ratios_extracts_coverage_and_debt_equity(self):
        from app.clients import fmp_client
        mock_data = [
            {
                "interestCoverageRatio": 3.5,
                "debtEquityRatio": 0.8,
                "peRatio": 15.2,
            }
        ]
        with patch("app.clients.fmp_client._get", return_value=mock_data):
            result = fmp_client.fetch_ratios("O")
        assert result is not None
        assert result["interest_coverage_ratio"] == pytest.approx(3.5)
        assert result["debt_equity_ratio"] == pytest.approx(0.8)

    def test_fetch_ratios_returns_none_on_api_failure(self):
        from app.clients import fmp_client
        with patch("app.clients.fmp_client._get", return_value=None):
            result = fmp_client.fetch_ratios("MISSING")
        assert result is None


# ── Staleness Tests ───────────────────────────────────────────────────────────

class TestStaleness:

    def test_compute_decay_weight_fresh_rec_returns_1(self):
        from app.processors.staleness import compute_decay_weight
        published_at = datetime.now(timezone.utc) - timedelta(days=1)
        weight = compute_decay_weight(published_at, aging_days=365, halflife_days=180)
        assert weight > 0.9

    def test_compute_decay_weight_expired_rec_returns_0(self):
        from app.processors.staleness import compute_decay_weight
        published_at = datetime.now(timezone.utc) - timedelta(days=400)
        weight = compute_decay_weight(published_at, aging_days=365, halflife_days=180)
        assert weight == 0.0

    def test_compute_decay_weight_at_halflife_is_approximately_half(self):
        from app.processors.staleness import compute_decay_weight
        halflife = 180
        published_at = datetime.now(timezone.utc) - timedelta(days=halflife)
        weight = compute_decay_weight(
            published_at, aging_days=365, halflife_days=halflife, min_weight=0.0
        )
        # S-curve at inflection point should be ~0.5
        assert 0.45 < weight < 0.55

    def test_compute_decay_weight_respects_min_weight(self):
        from app.processors.staleness import compute_decay_weight
        # 300 days old with min_weight=0.1 — well into decay but floored at 0.1
        published_at = datetime.now(timezone.utc) - timedelta(days=300)
        weight = compute_decay_weight(
            published_at, aging_days=365, halflife_days=180, min_weight=0.1
        )
        assert weight >= 0.1

    def test_compute_decay_weight_handles_naive_datetime(self):
        from app.processors.staleness import compute_decay_weight
        # Naive datetime should not raise — should be treated as UTC
        published_at = datetime.now() - timedelta(days=10)
        weight = compute_decay_weight(published_at)
        assert 0.0 <= weight <= 1.0

    def test_sweep_analyst_staleness_updates_active_recs(self):
        from app.processors.staleness import sweep_analyst_staleness

        mock_rec = MagicMock()
        mock_rec.id = 1
        mock_rec.ticker = "O"
        mock_rec.published_at = datetime.now(timezone.utc) - timedelta(days=90)
        mock_rec.decay_weight = Decimal("1.0")
        mock_rec.is_active = True

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_rec]

        result = sweep_analyst_staleness(db=mock_db, analyst_id=1)

        # Weight should have changed from 1.0 at 90 days
        assert result["updated"] >= 1
        assert result["deactivated"] == 0

    def test_sweep_analyst_staleness_deactivates_expired(self):
        from app.processors.staleness import sweep_analyst_staleness

        mock_rec = MagicMock()
        mock_rec.id = 2
        mock_rec.ticker = "MAIN"
        # Published 400 days ago → past aging_days=365 → should deactivate
        mock_rec.published_at = datetime.now(timezone.utc) - timedelta(days=400)
        mock_rec.decay_weight = Decimal("0.1")
        mock_rec.is_active = True

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_rec]

        result = sweep_analyst_staleness(db=mock_db, analyst_id=1)

        assert result["deactivated"] == 1
        assert mock_rec.is_active is False
        assert mock_rec.decay_weight == 0.0


# ── Backtest Tests ────────────────────────────────────────────────────────────

class TestBacktest:

    def test_compute_outcome_buy_correct(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="Buy",
            price_at_publish=100.0,
            price_at_t30=105.0,   # +5% > 2% threshold
            dividend_cut_occurred=False,
        )
        assert outcome == "Correct"
        assert delta > 0

    def test_compute_outcome_buy_incorrect(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="Buy",
            price_at_publish=100.0,
            price_at_t30=93.0,    # -7% < -5% threshold
            dividend_cut_occurred=False,
        )
        assert outcome == "Incorrect"
        assert delta < 0

    def test_compute_outcome_buy_partial(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="Buy",
            price_at_publish=100.0,
            price_at_t30=101.0,   # +1% — between thresholds
            dividend_cut_occurred=False,
        )
        assert outcome == "Partial"

    def test_compute_outcome_sell_correct_on_price_drop(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="StrongSell",
            price_at_publish=100.0,
            price_at_t30=95.0,    # fell ≥ 2% → correct bear call
            dividend_cut_occurred=False,
        )
        assert outcome == "Correct"

    def test_compute_outcome_hold_correct_when_flat(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="Hold",
            price_at_publish=100.0,
            price_at_t30=102.0,   # +2% < 5% → correct Hold
            dividend_cut_occurred=False,
        )
        assert outcome == "Correct"

    def test_compute_outcome_dividend_cut_overrides_bullish(self):
        from app.processors.backtest import compute_outcome_label
        # Even though price is up, dividend cut makes this Incorrect
        outcome, delta = compute_outcome_label(
            recommendation="StrongBuy",
            price_at_publish=100.0,
            price_at_t30=108.0,
            dividend_cut_occurred=True,
        )
        assert outcome == "Incorrect"

    def test_compute_outcome_inconclusive_on_missing_price(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="Buy",
            price_at_publish=None,
            price_at_t30=None,
            dividend_cut_occurred=False,
        )
        assert outcome == "Inconclusive"
        assert delta == 0.0

    def test_compute_outcome_inconclusive_for_unknown_rec(self):
        from app.processors.backtest import compute_outcome_label
        outcome, delta = compute_outcome_label(
            recommendation="Speculative",
            price_at_publish=100.0,
            price_at_t30=110.0,
            dividend_cut_occurred=False,
        )
        assert outcome == "Inconclusive"

    def test_update_overall_accuracy_correct_increases(self):
        from app.processors.backtest import _update_overall_accuracy, _DELTA_CORRECT
        new_acc = _update_overall_accuracy(0.6, _DELTA_CORRECT)
        assert new_acc > 0.6

    def test_update_overall_accuracy_incorrect_decreases(self):
        from app.processors.backtest import _update_overall_accuracy, _DELTA_INCORRECT
        new_acc = _update_overall_accuracy(0.6, _DELTA_INCORRECT)
        assert new_acc < 0.6

    def test_update_overall_accuracy_clamped_to_unit_interval(self):
        from app.processors.backtest import _update_overall_accuracy, _DELTA_CORRECT, _DELTA_INCORRECT
        # Start at 1.0 — should not exceed 1.0
        new_acc = _update_overall_accuracy(1.0, _DELTA_CORRECT)
        assert 0.0 <= new_acc <= 1.0
        # Start at 0.0 — should not go below 0.0
        new_acc2 = _update_overall_accuracy(0.0, _DELTA_INCORRECT)
        assert 0.0 <= new_acc2 <= 1.0

    def test_update_sector_alpha_creates_new_sector(self):
        from app.processors.backtest import _update_sector_alpha
        result = _update_sector_alpha(None, "REIT", "Correct")
        assert "REIT" in result
        assert result["REIT"] > 0.5  # correct outcome pushes above 0.5

    def test_update_sector_alpha_updates_existing_sector(self):
        from app.processors.backtest import _update_sector_alpha
        existing = {"REIT": 0.65, "MLP": 0.55}
        result = _update_sector_alpha(existing, "REIT", "Incorrect")
        assert result["REIT"] < 0.65  # incorrect pushed it down
        assert result["MLP"] == pytest.approx(0.55)  # unaffected

    def test_backtest_analyst_skips_already_backtested(self):
        from app.processors.backtest import backtest_analyst

        mock_db = MagicMock()

        # already_tested_ids subquery returns rec id 10
        mock_subq = MagicMock()
        mock_db.query.return_value.filter.return_value.subquery.return_value = mock_subq

        # No eligible recs (all already tested)
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = backtest_analyst(db=mock_db, analyst_id=1)
        assert result["backtested"] == 0


# ── Philosophy Tests ──────────────────────────────────────────────────────────

class TestPhilosophy:

    def _make_analyst(self, article_count=5):
        analyst = MagicMock()
        analyst.id = 1
        analyst.display_name = "Rida Morwa"
        analyst.article_count = article_count
        analyst.philosophy_summary = None
        analyst.philosophy_source = None
        analyst.philosophy_tags = None
        analyst.philosophy_vector = None
        analyst.philosophy_cluster = None
        return analyst

    def _make_article(self, title="Article", tickers=None, embedding=None):
        article = MagicMock()
        article.title = title
        article.published_at = datetime.now(timezone.utc)
        article.tickers_mentioned = tickers or ["O", "MAIN"]
        article.content_embedding = embedding
        return article

    def test_synthesize_llm_parses_response(self):
        from app.processors.philosophy import synthesize_philosophy_llm

        mock_resp_text = """{
            "summary": "Focus on high-yield dividend stocks with stable cash flows.",
            "style": "high-yield",
            "sectors": ["REIT", "BDC"],
            "asset_classes": ["CommonStock"],
            "themes": ["income-growth"]
        }"""

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=mock_resp_text)]

        analyst = self._make_analyst(article_count=5)
        articles = [self._make_article() for _ in range(5)]

        with patch("app.processors.philosophy._client") as mock_client:
            mock_client.messages.create.return_value = mock_message
            result = synthesize_philosophy_llm(analyst, articles)

        assert result.get("philosophy_source") == "llm"
        assert analyst.philosophy_summary is not None
        assert "high-yield" in analyst.philosophy_tags.get("style", "")

    def test_synthesize_llm_handles_invalid_json(self):
        from app.processors.philosophy import synthesize_philosophy_llm

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="not json at all")]

        analyst = self._make_analyst(article_count=5)
        articles = [self._make_article()]

        with patch("app.processors.philosophy._client") as mock_client:
            mock_client.messages.create.return_value = mock_message
            result = synthesize_philosophy_llm(analyst, articles)

        assert result == {}

    def test_synthesize_llm_returns_empty_when_client_unavailable(self):
        from app.processors.philosophy import synthesize_philosophy_llm

        analyst = self._make_analyst()
        articles = [self._make_article()]

        with patch("app.processors.philosophy._client", None):
            result = synthesize_philosophy_llm(analyst, articles)
        assert result == {}

    def test_synthesize_kmeans_with_sufficient_embeddings(self):
        from app.processors.philosophy import synthesize_philosophy_kmeans
        import numpy as np

        k = 3
        analyst = self._make_analyst(article_count=15)
        # 15 articles each with a 1536-dim embedding
        rng = np.random.default_rng(42)
        articles = []
        for i in range(15):
            emb = rng.standard_normal(1536).tolist()
            articles.append(self._make_article(f"Article {i}", embedding=emb))

        result = synthesize_philosophy_kmeans(analyst, articles, k=k)

        assert result.get("philosophy_source") == "kmeans"
        assert analyst.philosophy_vector is not None
        assert len(analyst.philosophy_vector) == 1536

    def test_synthesize_kmeans_fallback_when_fewer_than_k_embeddings(self):
        from app.processors.philosophy import synthesize_philosophy_kmeans
        import numpy as np

        k = 5
        analyst = self._make_analyst(article_count=3)
        rng = np.random.default_rng(7)
        # Only 3 articles with embeddings — less than k=5
        articles = [
            self._make_article(f"A{i}", embedding=rng.standard_normal(1536).tolist())
            for i in range(3)
        ]

        result = synthesize_philosophy_kmeans(analyst, articles, k=k)

        # Falls back to global centroid
        assert result.get("philosophy_source") == "kmeans"
        assert analyst.philosophy_cluster == 0

    def test_synthesize_kmeans_handles_articles_without_embeddings(self):
        from app.processors.philosophy import synthesize_philosophy_kmeans
        import numpy as np

        k = 3
        analyst = self._make_analyst()
        rng = np.random.default_rng(99)
        # Mix of articles with and without embeddings
        articles = []
        for i in range(10):
            emb = rng.standard_normal(1536).tolist() if i < 7 else None
            articles.append(self._make_article(f"Article {i}", embedding=emb))

        result = synthesize_philosophy_kmeans(analyst, articles, k=k)
        assert result.get("philosophy_source") == "kmeans"

    def test_update_analyst_philosophy_routes_to_llm_below_threshold(self):
        from app.processors import philosophy

        mock_db = MagicMock()
        # Analyst with 5 articles (below 20 threshold)
        analyst_mock = MagicMock()
        analyst_mock.id = 1
        analyst_mock.display_name = "Test Analyst"
        analyst_mock.article_count = 5
        mock_db.query.return_value.filter.return_value.first.return_value = analyst_mock
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch.object(philosophy, "synthesize_philosophy_llm", return_value={"philosophy_source": "llm"}) as mock_llm, \
             patch.object(philosophy, "synthesize_philosophy_kmeans", return_value={}) as mock_kmeans:
            philosophy.update_analyst_philosophy(db=mock_db, analyst_id=1)
            mock_llm.assert_called_once()
            mock_kmeans.assert_not_called()

    def test_update_analyst_philosophy_routes_to_kmeans_at_threshold(self):
        from app.processors import philosophy

        mock_db = MagicMock()
        # Analyst with 25 articles (above 20 threshold)
        analyst_mock = MagicMock()
        analyst_mock.id = 1
        analyst_mock.display_name = "Test Analyst"
        analyst_mock.article_count = 25
        mock_db.query.return_value.filter.return_value.first.return_value = analyst_mock
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch.object(philosophy, "synthesize_philosophy_llm", return_value={}) as mock_llm, \
             patch.object(philosophy, "synthesize_philosophy_kmeans", return_value={"philosophy_source": "kmeans"}) as mock_kmeans:
            philosophy.update_analyst_philosophy(db=mock_db, analyst_id=1)
            mock_kmeans.assert_called_once()
            mock_llm.assert_not_called()


# ── Consensus Tests ───────────────────────────────────────────────────────────

class TestConsensus:

    def _make_rec(self, analyst_id, sentiment_score, decay_weight=1.0):
        rec = MagicMock()
        rec.analyst_id = analyst_id
        rec.sentiment_score = Decimal(str(sentiment_score))
        rec.decay_weight = Decimal(str(decay_weight))
        return rec

    def test_compute_consensus_simple_average(self):
        from app.processors.consensus import compute_consensus_score

        recs = [
            self._make_rec(analyst_id=1, sentiment_score=0.8),
            self._make_rec(analyst_id=2, sentiment_score=0.6),
        ]
        analyst_stats = {1: 0.8, 2: 0.7}

        result = compute_consensus_score(recs, analyst_stats)

        assert result["score"] is not None
        # Both analysts pass MIN_ACCURACY threshold
        assert result["n_analysts"] == 2
        # confidence = "low" — only 2 analysts (need >= 3 for high)
        assert result["confidence"] == "low"

    def test_compute_consensus_high_confidence_with_3_analysts(self):
        from app.processors.consensus import compute_consensus_score

        recs = [
            self._make_rec(analyst_id=1, sentiment_score=0.7),
            self._make_rec(analyst_id=2, sentiment_score=0.8),
            self._make_rec(analyst_id=3, sentiment_score=0.6),
        ]
        analyst_stats = {1: 0.75, 2: 0.80, 3: 0.70}

        result = compute_consensus_score(recs, analyst_stats)
        assert result["confidence"] == "high"
        assert result["n_analysts"] == 3

    def test_compute_consensus_excludes_low_accuracy_analysts(self):
        from app.processors.consensus import compute_consensus_score

        recs = [
            self._make_rec(analyst_id=1, sentiment_score=0.9),  # high accuracy
            self._make_rec(analyst_id=2, sentiment_score=-0.5), # low accuracy — excluded
        ]
        analyst_stats = {1: 0.80, 2: 0.40}  # analyst 2 below 0.5 threshold

        result = compute_consensus_score(recs, analyst_stats)
        assert result["n_analysts"] == 1
        # Score should reflect only analyst 1's positive sentiment
        assert result["score"] > 0

    def test_compute_consensus_returns_insufficient_when_all_excluded(self):
        from app.processors.consensus import compute_consensus_score

        recs = [self._make_rec(analyst_id=1, sentiment_score=0.9)]
        analyst_stats = {1: 0.30}  # below threshold

        result = compute_consensus_score(recs, analyst_stats)
        assert result["score"] is None
        assert result["confidence"] == "insufficient_data"
        assert result["n_analysts"] == 0

    def test_compute_consensus_respects_decay_weight(self):
        from app.processors.consensus import compute_consensus_score

        # Same analysts, one very bullish but low decay weight
        recs = [
            self._make_rec(analyst_id=1, sentiment_score=0.9, decay_weight=0.1),
            self._make_rec(analyst_id=2, sentiment_score=0.2, decay_weight=1.0),
        ]
        analyst_stats = {1: 0.80, 2: 0.80}

        result = compute_consensus_score(recs, analyst_stats)
        # Analyst 2's lower score dominates due to higher decay weight
        assert result["score"] is not None
        assert result["score"] < 0.9  # pulled toward 0.2 by decay weighting

    def test_compute_consensus_applies_user_weights(self):
        from app.processors.consensus import compute_consensus_score

        recs = [
            self._make_rec(analyst_id=1, sentiment_score=0.8),
            self._make_rec(analyst_id=2, sentiment_score=0.2),
        ]
        analyst_stats = {1: 0.75, 2: 0.75}
        user_weights = {1: 2.0, 2: 1.0}  # trust analyst 1 twice as much

        result = compute_consensus_score(recs, analyst_stats, user_weights=user_weights)
        # With equal accuracy but analyst 1 double-weighted:
        # numerator = 0.8*0.75*2 + 0.2*0.75*1 = 1.35
        # denominator = 0.75*2 + 0.75*1 = 2.25
        # score = 1.35/2.25 ≈ 0.6
        assert result["score"] == pytest.approx(0.6, abs=0.01)

    def test_compute_consensus_empty_recs_returns_insufficient(self):
        from app.processors.consensus import compute_consensus_score
        result = compute_consensus_score([], {})
        assert result["score"] is None
        assert result["confidence"] == "insufficient_data"

    def test_rebuild_consensus_for_ticker_writes_to_redis(self):
        from app.processors import consensus

        rec = self._make_rec(analyst_id=1, sentiment_score=0.7)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [rec]

        mock_redis = MagicMock()
        with patch.object(consensus, "_redis", mock_redis):
            result = consensus.rebuild_consensus_for_ticker(
                db=mock_db,
                ticker="O",
                analyst_stats={1: 0.75},
            )

        mock_redis.setex.assert_called_once()
        cache_key = mock_redis.setex.call_args[0][0]
        assert cache_key == "consensus:O"
        assert result["ticker"] == "O"


# ── Intelligence Flow API Tests ───────────────────────────────────────────────

class TestIntelligenceAPI:

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

    def test_trigger_intelligence_returns_200(self, client):
        with patch("app.api.flows._run_intelligence"):
            response = client.post("/flows/intelligence/trigger", json={})
        assert response.status_code == 200

    def test_trigger_intelligence_response_body(self, client):
        with patch("app.api.flows._run_intelligence"):
            response = client.post("/flows/intelligence/trigger", json={})
        data = response.json()
        assert data["triggered"] is True
        assert data["flow_name"] == "intelligence_flow"
        assert "message" in data

    def test_trigger_intelligence_with_analyst_ids(self, client):
        with patch("app.api.flows._run_intelligence") as mock_run:
            response = client.post(
                "/flows/intelligence/trigger",
                json={"analyst_ids": [1, 2]},
            )
        data = response.json()
        assert data["triggered"] is True
        assert "analysts [1, 2]" in data["message"]

    def test_trigger_intelligence_no_longer_returns_501(self, client):
        """Regression: Phase 2 returned 501. Phase 3 must return 200."""
        with patch("app.api.flows._run_intelligence"):
            response = client.post("/flows/intelligence/trigger", json={})
        assert response.status_code != 501

    def test_harvester_trigger_still_works_after_phase3(self, client):
        """Confirm Phase 2 endpoint is unaffected by Phase 3 changes."""
        with patch("app.api.flows._run_harvester"):
            response = client.post("/flows/harvester/trigger", json={})
        assert response.status_code == 200
        assert response.json()["triggered"] is True
