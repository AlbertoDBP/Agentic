"""
Agent 10 — NAV Erosion Monitor
Tests: API endpoints — 35 tests.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

from app.database import get_db
from app.main import app
from app.models import NavAlert

_SECRET = os.environ["JWT_SECRET"]
_TOKEN = jwt.encode({"sub": "test"}, _SECRET, algorithm="HS256")
AUTH = {"Authorization": f"Bearer {_TOKEN}"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _override_db(db_mock):
    def _dep():
        yield db_mock
    return _dep


def _make_alert_mock(
    alert_id=1,
    symbol="PDI",
    alert_type="NAV_EROSION",
    severity="WARNING",
    resolved_at=None,
):
    a = MagicMock(spec=NavAlert)
    a.id = alert_id
    a.symbol = symbol
    a.alert_type = alert_type
    a.severity = severity
    a.details = {"erosion_rate_30d": -0.07}
    a.score_at_alert = 62.0
    a.erosion_rate_used = -0.07
    a.threshold_used = -0.05
    a.resolved_at = resolved_at
    a.created_at = "2026-03-12T00:00:00+00:00"
    a.updated_at = "2026-03-12T00:00:00+00:00"
    return a


def _make_db_mock(alerts=None, get_result=None):
    """Build a mock SQLAlchemy Session."""
    db = MagicMock()
    mock_alerts = alerts if alerts is not None else []

    # Chain: db.query(...).filter(...).all() or .first() or .order_by(...).limit(...).all()
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = mock_alerts
    q.first.return_value = mock_alerts[0] if mock_alerts else None

    # db.get() for single-item lookup
    db.get = MagicMock(return_value=get_result)

    def _refresh(obj):
        obj.resolved_at = datetime.now(timezone.utc).isoformat()

    db.refresh = MagicMock(side_effect=_refresh)
    return db


# ── Class 1: GET /health ──────────────────────────────────────────────────────

class TestHealth:
    """5 tests."""

    def test_health_returns_200(self):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = TestClient(app).get("/health")
        assert resp.status_code == 200

    def test_health_no_auth_required(self):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = TestClient(app).get("/health")
        assert resp.status_code != 403

    def test_health_agent_id_is_10(self):
        with patch("app.api.health.check_db_health", return_value=True):
            data = TestClient(app).get("/health").json()
        assert data["agent_id"] == 10

    def test_health_db_connected(self):
        with patch("app.api.health.check_db_health", return_value=True):
            data = TestClient(app).get("/health").json()
        assert data["database"] == "connected"

    def test_health_db_unavailable(self):
        with patch("app.api.health.check_db_health", return_value=False):
            data = TestClient(app).get("/health").json()
        assert data["database"] == "unavailable"


# ── Class 2: Auth enforcement ─────────────────────────────────────────────────

class TestAuth:
    """7 tests."""

    def test_scan_no_auth_returns_403(self):
        resp = TestClient(app).post("/monitor/scan")
        assert resp.status_code == 403

    def test_scan_invalid_token_returns_401(self):
        resp = TestClient(app).post(
            "/monitor/scan",
            headers={"Authorization": "Bearer bad.token.here"},
        )
        assert resp.status_code == 401

    def test_alerts_no_auth_returns_403(self):
        resp = TestClient(app).get("/monitor/alerts")
        assert resp.status_code == 403

    def test_alerts_invalid_token_returns_401(self):
        resp = TestClient(app).get(
            "/monitor/alerts",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401

    def test_alerts_symbol_no_auth_returns_403(self):
        resp = TestClient(app).get("/monitor/alerts/PDI")
        assert resp.status_code == 403

    def test_resolve_no_auth_returns_403(self):
        resp = TestClient(app).post("/monitor/alerts/1/resolve")
        assert resp.status_code == 403

    def test_valid_token_passes_auth(self):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch(
                "app.api.monitor.snapshot_reader.get_recent_snapshots",
                new_callable=AsyncMock,
                return_value=[],
            ), patch(
                "app.api.monitor.snapshot_reader.get_income_scores",
                new_callable=AsyncMock,
                return_value={},
            ):
                resp = TestClient(app).post("/monitor/scan", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code != 403


# ── Class 3: POST /monitor/scan ───────────────────────────────────────────────

class TestScan:
    """10 tests."""

    def _do_scan(self, dry_run=False, snapshots=None, scores=None, alerts=None):
        db = _make_db_mock(alerts=alerts or [])
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch(
                "app.api.monitor.snapshot_reader.get_recent_snapshots",
                new_callable=AsyncMock,
                return_value=snapshots or [],
            ), patch(
                "app.api.monitor.snapshot_reader.get_income_scores",
                new_callable=AsyncMock,
                return_value=scores or {},
            ):
                url = f"/monitor/scan?dry_run={str(dry_run).lower()}"
                resp = TestClient(app).post(url, headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp, db

    def test_scan_returns_200(self):
        resp, _ = self._do_scan()
        assert resp.status_code == 200

    def test_scan_returns_symbols_scanned(self):
        data = self._do_scan()[0].json()
        assert "symbols_scanned" in data

    def test_scan_returns_alerts_new(self):
        data = self._do_scan()[0].json()
        assert "alerts_new" in data

    def test_scan_returns_alerts_resolved(self):
        data = self._do_scan()[0].json()
        assert "alerts_resolved" in data

    def test_scan_returns_alerts_list(self):
        data = self._do_scan()[0].json()
        assert isinstance(data["alerts"], list)

    def test_scan_returns_scanned_at(self):
        data = self._do_scan()[0].json()
        assert "scanned_at" in data

    def test_scan_symbols_scanned_count(self):
        snaps = [
            {"symbol": "PDI", "erosion_rate_30d": -0.01, "erosion_rate_90d": -0.02,
             "premium_discount": 0.0},
            {"symbol": "MAIN", "erosion_rate_30d": -0.01, "erosion_rate_90d": -0.02,
             "premium_discount": 0.0},
        ]
        data = self._do_scan(snapshots=snaps)[0].json()
        assert data["symbols_scanned"] == 2

    def test_dry_run_true_does_not_persist(self):
        snaps = [
            {"symbol": "PDI", "erosion_rate_30d": -0.07, "erosion_rate_90d": -0.12,
             "premium_discount": -0.10},
        ]
        resp, db = self._do_scan(dry_run=True, snapshots=snaps)
        assert resp.status_code == 200
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_dry_run_false_commits(self):
        snaps = [
            {"symbol": "PDI", "erosion_rate_30d": -0.07, "erosion_rate_90d": -0.12,
             "premium_discount": 0.0},
        ]
        resp, db = self._do_scan(dry_run=False, snapshots=snaps)
        assert resp.status_code == 200
        db.commit.assert_called()

    def test_alerts_contain_symbol_and_type(self):
        snaps = [
            {"symbol": "PDI", "erosion_rate_30d": -0.07, "erosion_rate_90d": -0.12,
             "premium_discount": 0.0},
        ]
        data = self._do_scan(dry_run=True, snapshots=snaps)[0].json()
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "symbol" in alert
            assert "alert_type" in alert
            assert "severity" in alert


# ── Class 4: GET /monitor/alerts ─────────────────────────────────────────────

class TestListAlerts:
    """6 tests."""

    def _do_list(self, alerts=None, params=""):
        db = _make_db_mock(alerts=alerts or [])
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get(f"/monitor/alerts{params}", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_returns_200(self):
        assert self._do_list().status_code == 200

    def test_returns_alerts_list(self):
        data = self._do_list().json()
        assert isinstance(data["alerts"], list)

    def test_returns_total(self):
        data = self._do_list().json()
        assert "total" in data

    def test_empty_returns_empty_list(self):
        data = self._do_list(alerts=[]).json()
        assert data["alerts"] == []
        assert data["total"] == 0

    def test_filtering_by_severity(self):
        alerts = [_make_alert_mock(severity="CRITICAL")]
        data = self._do_list(alerts=alerts, params="?severity=CRITICAL").json()
        assert data["total"] == 1

    def test_filtering_by_alert_type(self):
        alerts = [_make_alert_mock(alert_type="NAV_EROSION")]
        data = self._do_list(
            alerts=alerts, params="?alert_type=NAV_EROSION"
        ).json()
        assert data["total"] == 1


# ── Class 5: GET /monitor/alerts/{symbol} ─────────────────────────────────────

class TestAlertsForSymbol:
    """4 tests."""

    def _do_get(self, symbol, alerts=None):
        db = _make_db_mock(alerts=alerts or [])
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get(f"/monitor/alerts/{symbol}", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_no_alerts_returns_404(self):
        resp = self._do_get("UNKNOWN", alerts=[])
        assert resp.status_code == 404

    def test_alerts_found_returns_200(self):
        alerts = [_make_alert_mock(symbol="PDI")]
        resp = self._do_get("PDI", alerts=alerts)
        assert resp.status_code == 200

    def test_response_contains_symbol(self):
        alerts = [_make_alert_mock(symbol="PDI")]
        data = self._do_get("PDI", alerts=alerts).json()
        assert "symbol" in data

    def test_response_contains_alerts_list(self):
        alerts = [_make_alert_mock(symbol="PDI")]
        data = self._do_get("PDI", alerts=alerts).json()
        assert isinstance(data["alerts"], list)


# ── Class 6: POST /monitor/alerts/{alert_id}/resolve ─────────────────────────

class TestResolveAlert:
    """3 tests."""

    def _do_resolve(self, alert_id, alert_obj=None):
        db = _make_db_mock(get_result=alert_obj)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).post(
                f"/monitor/alerts/{alert_id}/resolve", headers=AUTH
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_unknown_id_returns_404(self):
        resp = self._do_resolve(999, alert_obj=None)
        assert resp.status_code == 404

    def test_known_id_returns_200(self):
        alert = _make_alert_mock(alert_id=1)
        resp = self._do_resolve(1, alert_obj=alert)
        assert resp.status_code == 200

    def test_response_contains_alert_id(self):
        alert = _make_alert_mock(alert_id=1)
        data = self._do_resolve(1, alert_obj=alert).json()
        assert data["alert_id"] == 1
