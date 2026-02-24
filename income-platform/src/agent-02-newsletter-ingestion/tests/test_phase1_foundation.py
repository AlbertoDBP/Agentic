"""
Agent 02 — Newsletter Ingestion Service
Tests: Phase 1 — Foundation smoke tests

Validates:
  - FastAPI app starts and responds
  - /health endpoint returns expected structure
  - Database connectivity check runs without crashing
  - Schema and model imports are clean
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.models.schemas import FlowStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_healthy():
    """Mock a healthy database response."""
    return {
        "status": "healthy",
        "connectivity": True,
        "pgvector_installed": True,
        "schema_exists": True,
    }


@pytest.fixture
def mock_cache_healthy():
    """Mock a healthy cache response."""
    return {
        "status": "healthy",
        "version": "7.0.0",
    }


@pytest.fixture
def client(mock_db_healthy, mock_cache_healthy):
    """
    TestClient with database and cache checks mocked.
    Allows testing the API layer without a real database.
    """
    flow_status = FlowStatus(
        last_run=None,
        last_run_status=None,
        next_scheduled=None,
        articles_processed_last_run=None,
    )
    with patch("app.database.check_database_connection", return_value=mock_db_healthy), \
         patch("app.api.health._check_cache", return_value=mock_cache_healthy), \
         patch("app.api.health._get_flow_status", return_value=flow_status):
        from app.main import app
        yield TestClient(app)


# ── Root Tests ────────────────────────────────────────────────────────────────

class TestRoot:
    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_service_name(self, client):
        data = client.get("/").json()
        assert data["service"] == "agent-02-newsletter-ingestion"
        assert data["status"] == "running"

    def test_docs_accessible(self, client):
        response = client.get("/docs")
        assert response.status_code == 200


# ── Health Tests ──────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_healthy(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_has_required_fields(self, client):
        data = client.get("/health").json()
        required = ["status", "service", "version", "environment",
                    "database", "cache", "harvester_flow", "intelligence_flow", "timestamp"]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_health_database_healthy(self, client):
        data = client.get("/health").json()
        assert data["database"]["status"] == "healthy"
        assert data["database"]["pgvector_installed"] is True

    def test_health_cache_healthy(self, client):
        data = client.get("/health").json()
        assert data["cache"]["status"] == "healthy"

    def test_health_degraded_when_cache_down(self, mock_db_healthy):
        """Service should report degraded (not unhealthy) when only cache is down."""
        mock_cache_down = {"status": "unhealthy", "error": "Connection refused"}

        flow_status = FlowStatus(last_run=None, last_run_status=None,
                                 next_scheduled=None, articles_processed_last_run=None)
        with patch("app.database.check_database_connection", return_value=mock_db_healthy), \
             patch("app.api.health._check_cache", return_value=mock_cache_down), \
             patch("app.api.health._get_flow_status", return_value=flow_status):
            from app.main import app
            client = TestClient(app)
            data = client.get("/health").json()
            assert data["status"] == "degraded"

    def test_health_unhealthy_when_db_down(self):
        """Service should report unhealthy when database is unavailable."""
        mock_db_down = {"status": "unhealthy", "error": "Connection refused"}
        mock_cache_ok = {"status": "healthy"}

        flow_status = FlowStatus(last_run=None, last_run_status=None,
                                 next_scheduled=None, articles_processed_last_run=None)
        with patch("app.api.health.check_database_connection", return_value=mock_db_down), \
             patch("app.api.health._check_cache", return_value=mock_cache_ok), \
             patch("app.api.health._get_flow_status", return_value=flow_status):
            from app.main import app
            client = TestClient(app)
            data = client.get("/health").json()
            assert data["status"] == "unhealthy"


# ── Model Import Tests ────────────────────────────────────────────────────────

class TestModelImports:
    def test_sqlalchemy_models_import(self):
        from app.models.models import (
            Analyst, AnalystArticle, AnalystRecommendation,
            AnalystAccuracyLog, CreditOverride
        )
        assert Analyst.__tablename__ == "analysts"
        assert AnalystArticle.__tablename__ == "analyst_articles"
        assert AnalystRecommendation.__tablename__ == "analyst_recommendations"
        assert AnalystAccuracyLog.__tablename__ == "analyst_accuracy_log"
        assert CreditOverride.__tablename__ == "credit_overrides"

    def test_pydantic_schemas_import(self):
        from app.models.schemas import (
            AnalystCreate, AnalystResponse, AnalystSignalResponse,
            ConsensusResponse, HealthResponse
        )
        # Basic instantiation test
        create = AnalystCreate(sa_publishing_id="12345", display_name="Test Analyst")
        assert create.sa_publishing_id == "12345"

    def test_config_loads(self):
        """Config should load without crashing (env vars may be missing in test env)."""
        try:
            from app.config import settings
            assert settings.service_name == "agent-02-newsletter-ingestion"
            assert settings.service_port == 8002
        except Exception as e:
            # Expected in CI without .env — just verify it's a validation error, not a code error
            assert "validation" in str(e).lower() or "field required" in str(e).lower()
