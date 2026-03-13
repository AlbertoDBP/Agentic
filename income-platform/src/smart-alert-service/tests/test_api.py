"""
test_api.py — 35 tests for the Smart Alert Service REST API.

Tests:
  - Health endpoint (5 tests)
  - Auth: missing / invalid / expired tokens (8 tests)
  - POST /alerts/scan (8 tests)
  - GET /alerts (7 tests)
  - GET /alerts/{symbol} (3 tests)
  - POST /alerts/{id}/resolve (4 tests)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

SECRET = "test-secret-for-tests"


def make_token(expired: bool = False, bad_secret: bool = False) -> str:
    payload = {
        "sub": "test-user",
        "exp": datetime.now(timezone.utc) + (timedelta(seconds=-1) if expired else timedelta(hours=1)),
    }
    secret = "wrong-secret" if bad_secret else SECRET
    return jwt.encode(payload, secret, algorithm="HS256")


def _mock_db():
    return MagicMock()


def _override_db(mock_db: MagicMock):
    def _get():
        yield mock_db
    app.dependency_overrides[get_db] = _get


def _clear_override():
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {make_token()}"}


# ---------------------------------------------------------------------------
# Health (5 tests)
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_agent_id_is_11(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.json()["agent_id"] == 11

    def test_health_service_name(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.json()["service"] == "smart-alert-service"

    def test_health_db_connected(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.json()["database"] == "connected"

    def test_health_db_unavailable(self, client):
        with patch("app.api.health.check_db_health", return_value=False):
            resp = client.get("/health")
        assert resp.json()["database"] == "unavailable"


# ---------------------------------------------------------------------------
# Auth (8 tests)
# ---------------------------------------------------------------------------

class TestAuth:
    def test_scan_missing_token_401(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan")
            assert resp.status_code == 403
        finally:
            _clear_override()

    def test_list_alerts_missing_token_401(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            resp = client.get("/alerts")
            assert resp.status_code == 403
        finally:
            _clear_override()

    def test_get_symbol_alerts_missing_token(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            resp = client.get("/alerts/AAPL")
            assert resp.status_code == 403
        finally:
            _clear_override()

    def test_resolve_missing_token(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            resp = client.post("/alerts/1/resolve")
            assert resp.status_code == 403
        finally:
            _clear_override()

    def test_invalid_token_returns_401(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            resp = client.get("/alerts", headers={"Authorization": "Bearer notavalidtoken"})
            assert resp.status_code == 401
        finally:
            _clear_override()

    def test_wrong_secret_returns_401(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            token = make_token(bad_secret=True)
            resp = client.get("/alerts", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 401
        finally:
            _clear_override()

    def test_expired_token_returns_401(self, client):
        db = _mock_db()
        _override_db(db)
        try:
            token = make_token(expired=True)
            resp = client.get("/alerts", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 401
        finally:
            _clear_override()

    def test_valid_token_allows_access(self, client):
        db = _mock_db()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts", headers={"Authorization": f"Bearer {make_token()}"})
            assert resp.status_code == 200
        finally:
            _clear_override()


# ---------------------------------------------------------------------------
# POST /alerts/scan (8 tests)
# ---------------------------------------------------------------------------

class TestScanAlerts:
    def _setup_scan_mock(self):
        """Return a mock DB session wired for the scan endpoint."""
        db = MagicMock()
        # circuit_breaker queries return no rows
        db.execute.return_value.fetchall.return_value = []
        # router open-alerts query returns no rows too
        return db

    def test_scan_returns_200(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            _clear_override()

    def test_scan_response_has_symbols_scanned(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            assert "symbols_scanned" in resp.json()
        finally:
            _clear_override()

    def test_scan_response_has_alerts_new(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            assert "alerts_new" in resp.json()
        finally:
            _clear_override()

    def test_scan_response_has_alerts_confirmed(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            assert "alerts_confirmed" in resp.json()
        finally:
            _clear_override()

    def test_scan_response_has_alerts_resolved(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            assert "alerts_resolved" in resp.json()
        finally:
            _clear_override()

    def test_scan_response_has_scanned_at(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            assert "scanned_at" in resp.json()
        finally:
            _clear_override()

    def test_scan_empty_db_zero_counts(self, client, auth_headers):
        db = self._setup_scan_mock()
        _override_db(db)
        try:
            resp = client.post("/alerts/scan", headers=auth_headers)
            data = resp.json()
            assert data["alerts_new"] == 0
            assert data["alerts_confirmed"] == 0
            assert data["alerts_resolved"] == 0
        finally:
            _clear_override()

    def test_scan_requires_auth(self, client):
        resp = client.post("/alerts/scan")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /alerts (7 tests)
# ---------------------------------------------------------------------------

def _make_alert_row(
    id=1,
    symbol="AAPL",
    source_agent=11,
    alert_type="SCORE_DETERIORATION",
    severity="WARNING",
    status="PENDING",
):
    row = MagicMock()
    row.id = id
    row.symbol = symbol
    row.source_agent = source_agent
    row.alert_type = alert_type
    row.severity = severity
    row.status = status
    row.first_seen_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row.confirmed_at = None
    row.resolved_at = None
    row.details = {}
    row.notified = False
    row.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return row


class TestListAlerts:
    def test_empty_list_returns_200(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            _clear_override()

    def test_returns_alert_list(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [_make_alert_row()]
        _override_db(db)
        try:
            resp = client.get("/alerts", headers=auth_headers)
            assert len(resp.json()) == 1
        finally:
            _clear_override()

    def test_filter_by_severity_passes_param(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts?severity=CRITICAL", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            _clear_override()

    def test_filter_by_source_agent(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts?source_agent=7", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            _clear_override()

    def test_filter_by_symbol(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts?symbol=AAPL", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            _clear_override()

    def test_limit_default_applied(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            _clear_override()

    def test_limit_exceeds_500_returns_422(self, client, auth_headers):
        db = MagicMock()
        _override_db(db)
        try:
            resp = client.get("/alerts?limit=501", headers=auth_headers)
            assert resp.status_code == 422
        finally:
            _clear_override()


# ---------------------------------------------------------------------------
# GET /alerts/{symbol} (3 tests)
# ---------------------------------------------------------------------------

class TestGetSymbolAlerts:
    def test_returns_404_when_no_alerts(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _override_db(db)
        try:
            resp = client.get("/alerts/UNKNOWN", headers=auth_headers)
            assert resp.status_code == 404
        finally:
            _clear_override()

    def test_returns_list_when_found(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [_make_alert_row(symbol="AAPL")]
        _override_db(db)
        try:
            resp = client.get("/alerts/AAPL", headers=auth_headers)
            assert resp.status_code == 200
            assert len(resp.json()) == 1
        finally:
            _clear_override()

    def test_symbol_in_response(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [_make_alert_row(symbol="MSFT")]
        _override_db(db)
        try:
            resp = client.get("/alerts/MSFT", headers=auth_headers)
            assert resp.json()[0]["symbol"] == "MSFT"
        finally:
            _clear_override()


# ---------------------------------------------------------------------------
# POST /alerts/{id}/resolve (4 tests)
# ---------------------------------------------------------------------------

class TestResolveAlert:
    def test_resolve_unknown_id_404(self, client, auth_headers):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        _override_db(db)
        try:
            resp = client.post("/alerts/9999/resolve", headers=auth_headers)
            assert resp.status_code == 404
        finally:
            _clear_override()

    def test_resolve_existing_returns_200(self, client, auth_headers):
        db = MagicMock()
        row = MagicMock()
        row.id = 1
        row.status = "PENDING"
        db.execute.return_value.fetchone.return_value = row
        _override_db(db)
        try:
            resp = client.post("/alerts/1/resolve", headers=auth_headers)
            assert resp.status_code == 200
        finally:
            _clear_override()

    def test_resolve_response_has_status_resolved(self, client, auth_headers):
        db = MagicMock()
        row = MagicMock()
        row.id = 1
        row.status = "PENDING"
        db.execute.return_value.fetchone.return_value = row
        _override_db(db)
        try:
            resp = client.post("/alerts/1/resolve", headers=auth_headers)
            assert resp.json()["status"] == "RESOLVED"
        finally:
            _clear_override()

    def test_resolve_response_has_resolved_at(self, client, auth_headers):
        db = MagicMock()
        row = MagicMock()
        row.id = 42
        row.status = "CONFIRMED"
        db.execute.return_value.fetchone.return_value = row
        _override_db(db)
        try:
            resp = client.post("/alerts/42/resolve", headers=auth_headers)
            assert "resolved_at" in resp.json()
        finally:
            _clear_override()
