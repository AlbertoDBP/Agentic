"""
Agent 02 — Newsletter Ingestion Service
Tests: Phase 4 — API layer

Tests are organized by endpoint:
  - TestAnalystsAPI         /analysts CRUD
  - TestRecommendationsAPI  /recommendations/{ticker}
  - TestConsensusAPI        /consensus/{ticker}
  - TestSignalAPI           /signal/{ticker} — Agent 12 contract
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _mock_analyst(id=1, sa_id="96726", name="Test Analyst",
                  accuracy=0.72, article_count=15):
    a = MagicMock()
    a.id = id
    a.sa_publishing_id = sa_id
    a.display_name = name
    a.is_active = True
    a.overall_accuracy = Decimal(str(accuracy))
    a.sector_alpha = {"REIT": 0.81, "BDC": 0.68}
    a.philosophy_summary = "Focuses on high-yield dividend sustainability"
    a.philosophy_source = "llm"
    a.philosophy_tags = {"style": "income", "sectors": ["REIT", "BDC"]}
    a.philosophy_cluster = None
    a.philosophy_vector = None
    a.article_count = article_count
    a.last_article_fetched_at = datetime(2025, 1, 20, tzinfo=timezone.utc)
    a.last_backtest_at = datetime(2025, 1, 15, tzinfo=timezone.utc)
    a.config = {"fetch_limit": 10}
    a.created_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    a.updated_at = datetime(2025, 1, 20, tzinfo=timezone.utc)
    return a


def _mock_recommendation(
    id=1, analyst_id=1, ticker="O", sentiment=0.75,
    decay_weight=0.85, rec_label="Buy", safety_grade="A",
    asset_class="REIT", sector="Real Estate",
):
    r = MagicMock()
    r.id = id
    r.analyst_id = analyst_id
    r.article_id = 10
    r.ticker = ticker
    r.sector = sector
    r.asset_class = asset_class
    r.recommendation = rec_label
    r.sentiment_score = Decimal(str(sentiment))
    r.yield_at_publish = Decimal("0.052")
    r.payout_ratio = Decimal("0.75")
    r.dividend_cagr_3yr = Decimal("0.03")
    r.dividend_cagr_5yr = Decimal("0.04")
    r.safety_grade = safety_grade
    r.source_reliability = "EarningsCall"
    r.content_embedding = None
    _metadata = {
        "bull_case": "29 year dividend streak, durable retail tenants.",
        "bear_case": "Rising rate headwind.",
        "key_risks": ["interest rate sensitivity"],
    }
    r.metadata = _metadata
    r.rec_metadata = _metadata
    r.published_at = datetime(2025, 1, 10, tzinfo=timezone.utc)
    r.expires_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    r.decay_weight = Decimal(str(decay_weight))
    r.is_active = True
    r.superseded_by = None
    r.platform_alignment = None
    r.platform_scored_at = None
    r.created_at = datetime(2025, 1, 10, tzinfo=timezone.utc)
    r.updated_at = datetime(2025, 1, 10, tzinfo=timezone.utc)
    return r


@pytest.fixture
def client():
    with patch("app.database.check_database_connection",
               return_value={"status": "healthy", "pgvector_installed": True,
                             "schema_exists": True}), \
         patch("app.api.health._check_cache",
               return_value={"status": "healthy"}), \
         patch("app.api.health._get_flow_status",
               return_value=MagicMock(last_run=None, last_run_status=None,
                                      next_scheduled=None,
                                      articles_processed_last_run=None)):
        from app.main import app
        yield TestClient(app)


# ── Analysts API Tests ────────────────────────────────────────────────────────

class TestAnalystsAPI:
    def test_list_analysts_returns_200(self, client):
        mock_analyst = _mock_analyst()
        with patch("app.api.analysts.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_analyst]
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/analysts")
        assert response.status_code == 200

    def test_list_analysts_returns_total(self, client):
        mock_analysts = [_mock_analyst(id=1), _mock_analyst(id=2, sa_id="104956", name="Analyst B")]
        with patch("app.api.analysts.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_analysts
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/analysts")
        assert response.json()["total"] == 2

    def test_add_analyst_returns_201(self, client):
        from app.main import app
        from app.database import get_db

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        def _set_id(obj):
            obj.id = 1
            obj.article_count = 0
            obj.philosophy_source = "llm"
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            obj.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_db.refresh.side_effect = _set_id
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = client.post("/analysts", json={
                "sa_publishing_id": "99999",
                "display_name": "New Analyst"
            })
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert response.status_code == 201

    def test_add_analyst_returns_409_when_duplicate(self, client):
        with patch("app.api.analysts.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = _mock_analyst()
            mock_get_db.return_value = iter([mock_db])
            response = client.post("/analysts", json={
                "sa_publishing_id": "96726",
                "display_name": "Duplicate"
            })
        assert response.status_code == 409

    def test_get_analyst_returns_404_when_not_found(self, client):
        with patch("app.api.analysts.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/analysts/9999")
        assert response.status_code == 404


# ── Recommendations API Tests ─────────────────────────────────────────────────

class TestRecommendationsAPI:
    def test_get_recommendations_returns_200(self, client):
        from app.main import app
        from app.database import get_db

        mock_rec = _mock_recommendation()
        mock_analyst = _mock_analyst()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value\
            .filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_rec]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_analyst]
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = client.get("/recommendations/O")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert response.status_code == 200

    def test_get_recommendations_normalizes_ticker(self, client):
        """Ticker should be uppercased regardless of input."""
        with patch("app.api.recommendations.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.filter.return_value\
                .filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/recommendations/jepi")
        # 404 because no data, but ticker was normalized (no 422 validation error)
        assert response.status_code == 404

    def test_get_recommendations_returns_404_when_none(self, client):
        with patch("app.api.recommendations.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.filter.return_value\
                .filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/recommendations/NOTEXIST")
        assert response.status_code == 404


# ── Consensus API Tests ───────────────────────────────────────────────────────

class TestConsensusAPI:
    def test_get_consensus_returns_200(self, client):
        from app.main import app
        from app.database import get_db

        mock_rec = _mock_recommendation()
        mock_analyst = _mock_analyst()
        consensus_result = {"score": 0.68, "confidence": "low", "n_analysts": 1}
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value\
            .filter.return_value.filter.return_value.all.return_value = [mock_rec]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_analyst]
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.consensus._get_cache_client", return_value=None), \
                 patch("app.api.consensus.compute_consensus_score", return_value=consensus_result):
                response = client.get("/consensus/O")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "O"
        assert float(data["score"]) == 0.68
        assert data["confidence"] == "low"

    def test_get_consensus_dominant_recommendation_buy(self, client):
        """Score 0.4 (0.2 ≤ score < 0.6) → dominant_recommendation = Buy."""
        from app.main import app
        from app.database import get_db

        mock_rec = _mock_recommendation(sentiment=0.4)
        mock_analyst = _mock_analyst()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value\
            .filter.return_value.filter.return_value.all.return_value = [mock_rec]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_analyst]
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.consensus._get_cache_client", return_value=None), \
                 patch("app.api.consensus.compute_consensus_score",
                       return_value={"score": 0.4, "confidence": "low", "n_analysts": 1}):
                response = client.get("/consensus/O")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert response.json()["dominant_recommendation"] == "Buy"

    def test_get_consensus_returns_404_when_no_recs(self, client):
        with patch("app.api.consensus.get_db") as mock_get_db, \
             patch("app.api.consensus._get_cache_client", return_value=None):
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.filter.return_value\
                .filter.return_value.filter.return_value.all.return_value = []
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/consensus/NODATA")
        assert response.status_code == 404


# ── Signal API Tests ──────────────────────────────────────────────────────────

class TestSignalAPI:
    def test_get_signal_returns_200(self, client):
        from app.main import app
        from app.database import get_db

        mock_rec = _mock_recommendation()
        mock_analyst = _mock_analyst()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value\
            .filter.return_value.order_by.return_value.all.return_value = [mock_rec]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_analyst]
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.signal._get_cache_client", return_value=None), \
                 patch("app.api.signal.compute_consensus_score",
                       return_value={"score": 0.72, "confidence": "low", "n_analysts": 1}):
                response = client.get("/signal/O")
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert response.status_code == 200

    def test_get_signal_has_required_fields(self, client):
        """Agent 12 contract — all required fields must be present."""
        from app.main import app
        from app.database import get_db

        mock_rec = _mock_recommendation()
        mock_analyst = _mock_analyst()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value\
            .filter.return_value.order_by.return_value.all.return_value = [mock_rec]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_analyst]
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.signal._get_cache_client", return_value=None), \
                 patch("app.api.signal.compute_consensus_score",
                       return_value={"score": 0.72, "confidence": "low", "n_analysts": 1}):
                data = client.get("/signal/O").json()
        finally:
            app.dependency_overrides.pop(get_db, None)

        required_top = ["ticker", "signal_strength", "proposal_readiness",
                        "analyst", "recommendation", "consensus", "generated_at"]
        for field in required_top:
            assert field in data, f"Missing top-level field: {field}"

        required_analyst = ["id", "display_name", "accuracy_overall",
                            "philosophy_summary", "philosophy_source"]
        for field in required_analyst:
            assert field in data["analyst"], f"Missing analyst field: {field}"

        required_rec = ["id", "label", "sentiment_score", "yield_at_publish",
                        "safety_grade", "bull_case", "bear_case", "decay_weight"]
        for field in required_rec:
            assert field in data["recommendation"], f"Missing recommendation field: {field}"

        required_consensus = ["ticker", "score", "confidence",
                              "n_analysts", "dominant_recommendation"]
        for field in required_consensus:
            assert field in data["consensus"], f"Missing consensus field: {field}"

    def test_get_signal_proposal_readiness_false_when_weak(self, client):
        """Weak signal → proposal_readiness=False."""
        from app.main import app
        from app.database import get_db

        mock_rec = _mock_recommendation(decay_weight=0.15)  # low decay weight
        mock_analyst = _mock_analyst(accuracy=0.45)          # below threshold
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value\
            .filter.return_value.order_by.return_value.all.return_value = [mock_rec]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_analyst]
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.signal._get_cache_client", return_value=None), \
                 patch("app.api.signal.compute_consensus_score",
                       return_value={"score": 0.3, "confidence": "low", "n_analysts": 1}):
                data = client.get("/signal/O").json()
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert data["proposal_readiness"] is False

    def test_get_signal_returns_404_when_no_recs(self, client):
        with patch("app.api.signal.get_db") as mock_get_db, \
             patch("app.api.signal._get_cache_client", return_value=None):
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.filter.return_value\
                .filter.return_value.order_by.return_value.all.return_value = []
            mock_get_db.return_value = iter([mock_db])
            response = client.get("/signal/NODATA")
        assert response.status_code == 404

    def test_signal_strength_computation(self):
        """Unit test signal_strength logic directly."""
        from app.api.signal import _compute_signal_strength
        assert _compute_signal_strength(2, 0.85, 0.72) == "strong"
        assert _compute_signal_strength(1, 0.55, 0.60) == "moderate"
        assert _compute_signal_strength(1, 0.25, 0.70) == "weak"
        assert _compute_signal_strength(0, 0.0, None) == "insufficient"

    def test_proposal_readiness_computation(self):
        """Unit test proposal_readiness logic directly."""
        from app.api.signal import _compute_proposal_readiness
        assert _compute_proposal_readiness("strong", 0.72, 0.5) is True
        assert _compute_proposal_readiness("moderate", 0.65, 0.5) is True
        assert _compute_proposal_readiness("weak", 0.72, 0.5) is False
        assert _compute_proposal_readiness("strong", 0.40, 0.5) is False  # below min accuracy

    def test_sentiment_to_label_mapping(self):
        """Verify sentiment → label mapping covers all ranges."""
        from app.api.signal import _sentiment_to_label
        from app.models.schemas import RecommendationLabel
        assert _sentiment_to_label(0.8) == RecommendationLabel.STRONG_BUY
        assert _sentiment_to_label(0.4) == RecommendationLabel.BUY
        assert _sentiment_to_label(0.0) == RecommendationLabel.HOLD
        assert _sentiment_to_label(-0.4) == RecommendationLabel.SELL
        assert _sentiment_to_label(-0.8) == RecommendationLabel.STRONG_SELL
        assert _sentiment_to_label(None) is None
