"""Tests for Agent 02 suggestions endpoints."""
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Set required env vars before any app imports trigger Settings()
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APIDOJO_SA_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("FMP_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")


def make_app():
    """Build a minimal FastAPI app with just the suggestions router."""
    from fastapi import FastAPI
    from app.api.suggestions import router
    app = FastAPI()
    app.include_router(router, prefix="/suggestions")
    return app


def mock_db():
    """Return a mock Session."""
    return MagicMock()


@patch("app.api.suggestions.get_db")
def test_get_suggestion_analysts_returns_list(mock_get_db):
    """GET /suggestions/analysts returns a list of analyst dicts."""
    from app.database import get_db as real_get_db
    db = mock_db()
    db.execute.return_value.fetchall.return_value = [
        (1, "Brad Thomas", 0.72),
        (2, "Rida Morwa",  0.68),
    ]
    app = make_app()
    app.dependency_overrides[real_get_db] = lambda: db
    client = TestClient(app)
    resp = client.get("/suggestions/analysts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["display_name"] == "Brad Thomas"
    assert data[0]["overall_accuracy"] == 0.72
    app.dependency_overrides.pop(real_get_db, None)


@patch("app.api.suggestions.get_db")
def test_get_ttl_config_returns_list(mock_get_db):
    """GET /suggestions/ttl-config returns list of {asset_class, ttl_days}."""
    from app.database import get_db as real_get_db
    db = mock_db()
    db.execute.return_value.fetchall.return_value = [
        ("_default", 45),
        ("BDC", 45),
        ("CEF", 30),
    ]
    app = make_app()
    app.dependency_overrides[real_get_db] = lambda: db
    client = TestClient(app)
    resp = client.get("/suggestions/ttl-config")
    assert resp.status_code == 200
    data = resp.json()
    assert {"asset_class": "_default", "ttl_days": 45} in data
    assert {"asset_class": "CEF", "ttl_days": 30} in data
    app.dependency_overrides.pop(real_get_db, None)


@patch("app.api.suggestions.get_db")
def test_put_ttl_config_calls_upsert(mock_get_db):
    """PUT /suggestions/ttl-config upserts each row and commits."""
    from app.database import get_db as real_get_db
    db = mock_db()
    app = make_app()
    app.dependency_overrides[real_get_db] = lambda: db
    client = TestClient(app)
    payload = [{"asset_class": "_default", "ttl_days": 60}, {"asset_class": "BDC", "ttl_days": 50}]
    resp = client.put("/suggestions/ttl-config", json=payload)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2
    assert db.execute.call_count == 2
    db.commit.assert_called_once()
    app.dependency_overrides.pop(real_get_db, None)


@patch("app.api.suggestions.get_db")
def test_put_ttl_config_rejects_zero_days(mock_get_db):
    """PUT /suggestions/ttl-config rejects ttl_days < 1."""
    from app.database import get_db as real_get_db
    db = mock_db()
    app = make_app()
    app.dependency_overrides[real_get_db] = lambda: db
    client = TestClient(app)
    resp = client.put("/suggestions/ttl-config", json=[{"asset_class": "BDC", "ttl_days": 0}])
    assert resp.status_code == 422
    app.dependency_overrides.pop(real_get_db, None)
