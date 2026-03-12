"""
Tests for GET /health and GET /

Covers:
  - /health returns HTTP 200
  - /health response body contains a 'status' field
  - /health returns 'degraded' when both cache and DB mocks are disconnected
  - /health returns 'healthy' when both dependencies report as connected
  - /health 'database' and 'cache' fields reflect mock state
  - GET / returns 200 with service metadata (no auth required)
  - GET / response contains expected keys: service, version, status, documentation

/health does NOT require authentication (no Depends(verify_token)) — confirmed
by reading main.py line 201–210.  These tests send requests without auth.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# GET / — root endpoint, no auth
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_returns_service_name(self, client):
        body = client.get("/").json()
        assert "service" in body
        assert body["service"] == "market-data-service"

    def test_root_returns_version(self, client):
        body = client.get("/").json()
        assert "version" in body

    def test_root_returns_status_operational(self, client):
        body = client.get("/").json()
        assert body.get("status") == "operational"

    def test_root_returns_documentation_link(self, client):
        body = client.get("/").json()
        assert "documentation" in body


# ---------------------------------------------------------------------------
# GET /health — no auth required
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_has_status_field(self, client):
        body = client.get("/health").json()
        assert "status" in body

    def test_health_status_is_string(self, client):
        body = client.get("/health").json()
        assert isinstance(body["status"], str)

    def test_health_response_has_database_field(self, client):
        body = client.get("/health").json()
        assert "database" in body

    def test_health_response_has_cache_field(self, client):
        body = client.get("/health").json()
        assert "cache" in body

    def test_health_response_has_service_field(self, client):
        """HealthResponse model always includes service='market-data-service'."""
        body = client.get("/health").json()
        assert "service" in body
        assert body["service"] == "market-data-service"

    def test_health_degraded_when_cache_and_db_disconnected(self, client):
        """Default mocks report both cache and DB as disconnected → 'degraded'."""
        body = client.get("/health").json()
        assert body["status"] == "degraded"

    def test_health_database_disconnected_string(self, client):
        body = client.get("/health").json()
        assert body["database"] == "disconnected"

    def test_health_cache_disconnected_string(self, client):
        body = client.get("/health").json()
        assert body["cache"] == "disconnected"

    def test_health_healthy_when_both_connected(self, monkeypatch):
        """Inject mocks that report connected=True and verify status='healthy'."""
        import sys
        _main_mod = sys.modules["main"]

        mock_cache = MagicMock()
        mock_cache.connect    = AsyncMock()
        mock_cache.disconnect = AsyncMock()
        mock_cache.is_connected = AsyncMock(return_value=True)

        mock_db = MagicMock()
        mock_db.connect       = AsyncMock()
        mock_db.disconnect    = AsyncMock()
        mock_db.is_connected  = AsyncMock(return_value=True)
        mock_db.session_factory = None

        mock_mds = MagicMock()
        mock_mds.connect    = AsyncMock()
        mock_mds.disconnect = AsyncMock()

        # Patch constructors so lifespan doesn't touch real infrastructure
        monkeypatch.setattr(_main_mod, "CacheManager",    MagicMock(return_value=mock_cache))
        monkeypatch.setattr(_main_mod, "DatabaseManager", MagicMock(return_value=mock_db))
        monkeypatch.setattr(_main_mod, "PriceService",    MagicMock(return_value=MagicMock()))
        monkeypatch.setattr(_main_mod, "MarketDataService", MagicMock(return_value=mock_mds))

        from fastapi.testclient import TestClient
        with TestClient(_main_mod.app) as tc:
            body = tc.get("/health").json()

        assert body["status"] == "healthy"
        assert body["database"] == "connected"
        assert body["cache"]    == "connected"

    def test_health_database_connected_cache_disconnected_is_degraded(self, monkeypatch):
        """Only one dependency up → 'degraded'."""
        import sys
        _main_mod = sys.modules["main"]

        mock_cache = MagicMock()
        mock_cache.connect    = AsyncMock()
        mock_cache.disconnect = AsyncMock()
        mock_cache.is_connected = AsyncMock(return_value=False)

        mock_db = MagicMock()
        mock_db.connect       = AsyncMock()
        mock_db.disconnect    = AsyncMock()
        mock_db.is_connected  = AsyncMock(return_value=True)
        mock_db.session_factory = None

        mock_mds = MagicMock()
        mock_mds.connect    = AsyncMock()
        mock_mds.disconnect = AsyncMock()

        monkeypatch.setattr(_main_mod, "CacheManager",    MagicMock(return_value=mock_cache))
        monkeypatch.setattr(_main_mod, "DatabaseManager", MagicMock(return_value=mock_db))
        monkeypatch.setattr(_main_mod, "PriceService",    MagicMock(return_value=MagicMock()))
        monkeypatch.setattr(_main_mod, "MarketDataService", MagicMock(return_value=mock_mds))

        from fastapi.testclient import TestClient
        with TestClient(_main_mod.app) as tc:
            body = tc.get("/health").json()

        assert body["status"] == "degraded"
        assert body["database"] == "connected"
        assert body["cache"]    == "disconnected"

    def test_health_no_auth_header_still_returns_200(self, client):
        """Health check endpoint is public — no auth required."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_content_type_is_json(self, client):
        resp = client.get("/health")
        assert "application/json" in resp.headers.get("content-type", "")
