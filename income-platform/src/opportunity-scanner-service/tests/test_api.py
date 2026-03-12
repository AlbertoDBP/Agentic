"""
Agent 07 — Opportunity Scanner Service
Tests: API endpoints — 35 tests.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")

from app.database import get_db
from app.main import app

_TOKEN = jwt.encode({"sub": "test"}, os.environ["JWT_SECRET"], algorithm="HS256")
AUTH = {"Authorization": f"Bearer {_TOKEN}"}


# ── Shared helpers ────────────────────────────────────────────────────────────

def _scan_item(ticker: str = "O", score: float = 75.0, asset_class: str = "EQUITY_REIT"):
    from app.scanner.engine import ScanItem
    passed = score >= 70.0
    return ScanItem(
        ticker=ticker, score=score, grade="B", recommendation="ACCUMULATE",
        asset_class=asset_class, chowder_signal="ATTRACTIVE", chowder_number=7.5,
        signal_penalty=0.0, rank=1, passed_quality_gate=passed, veto_flag=not passed,
        passed_filters=True, score_details={"valuation_yield_score": 30.0},
    )


def _engine_result(items=None, scanned=1, passed=1, vetoed=0):
    from app.scanner.engine import ScanEngineResult
    items = items if items is not None else [_scan_item()]
    return ScanEngineResult(
        total_scanned=scanned, total_passed=passed, total_vetoed=vetoed,
        items=items, all_items=items,
    )


def _make_db_mock(scan_id=None):
    """Return a mock Session with add/commit/refresh that sets id and created_at."""
    import uuid
    db = MagicMock()

    def _refresh(obj):
        obj.id = scan_id or uuid.uuid4()
        obj.created_at = "2026-03-12T00:00:00+00:00"

    db.refresh = MagicMock(side_effect=_refresh)
    return db


def _override_db(db_mock):
    """FastAPI dependency override factory."""
    def _dep():
        yield db_mock
    return _dep


# ── Class 1: Health endpoint ──────────────────────────────────────────────────

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

    def test_health_returns_agent_id_7(self):
        with patch("app.api.health.check_db_health", return_value=True):
            data = TestClient(app).get("/health").json()
        assert data["agent_id"] == 7

    def test_health_db_connected(self):
        with patch("app.api.health.check_db_health", return_value=True):
            data = TestClient(app).get("/health").json()
        assert data["database"] == "connected"

    def test_health_db_unavailable(self):
        with patch("app.api.health.check_db_health", return_value=False):
            data = TestClient(app).get("/health").json()
        assert data["database"] == "unavailable"


# ── Class 2: POST /scan — auth ────────────────────────────────────────────────

class TestScanAuth:
    """5 tests."""

    def test_scan_no_auth_returns_403(self):
        resp = TestClient(app).post("/scan", json={"tickers": ["O"]})
        assert resp.status_code == 403

    def test_scan_invalid_token_returns_401(self):
        resp = TestClient(app).post(
            "/scan", json={"tickers": ["O"]},
            headers={"Authorization": "Bearer bad.token.here"},
        )
        assert resp.status_code == 401

    def test_scan_valid_auth_passes(self):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.run_scan", new_callable=AsyncMock,
                       return_value=_engine_result()):
                resp = TestClient(app).post("/scan", json={"tickers": ["O"]}, headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code != 403

    def test_universe_no_auth_returns_403(self):
        resp = TestClient(app).get("/universe")
        assert resp.status_code == 403

    def test_scan_by_id_no_auth_returns_403(self):
        resp = TestClient(app).get(f"/scan/{uuid4()}")
        assert resp.status_code == 403


# ── Class 3: POST /scan — request validation ──────────────────────────────────

class TestScanValidation:
    """5 tests."""

    def test_empty_tickers_returns_422(self):
        resp = TestClient(app).post("/scan", json={"tickers": []}, headers=AUTH)
        assert resp.status_code == 422

    def test_missing_tickers_returns_422(self):
        resp = TestClient(app).post("/scan", json={}, headers=AUTH)
        assert resp.status_code == 422

    def test_min_score_above_100_returns_422(self):
        resp = TestClient(app).post(
            "/scan", json={"tickers": ["O"], "min_score": 101.0}, headers=AUTH
        )
        assert resp.status_code == 422

    def test_min_score_negative_returns_422(self):
        resp = TestClient(app).post(
            "/scan", json={"tickers": ["O"], "min_score": -1.0}, headers=AUTH
        )
        assert resp.status_code == 422

    def test_too_many_tickers_returns_422(self):
        tickers = [f"T{i}" for i in range(201)]
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).post("/scan", json={"tickers": tickers}, headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 422


# ── Class 4: POST /scan — response structure ──────────────────────────────────

class TestScanResponse:
    """10 tests."""

    def _do_scan(self, tickers=None, **kwargs):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.run_scan", new_callable=AsyncMock,
                       return_value=_engine_result()):
                resp = TestClient(app).post(
                    "/scan", json={"tickers": tickers or ["O"], **kwargs}, headers=AUTH
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_returns_200(self):
        assert self._do_scan().status_code == 200

    def test_scan_id_in_response(self):
        assert "scan_id" in self._do_scan().json()

    def test_total_scanned_in_response(self):
        assert "total_scanned" in self._do_scan().json()

    def test_total_passed_in_response(self):
        assert "total_passed" in self._do_scan().json()

    def test_total_vetoed_in_response(self):
        assert "total_vetoed" in self._do_scan().json()

    def test_items_is_list(self):
        assert isinstance(self._do_scan().json()["items"], list)

    def test_filters_applied_in_response(self):
        assert "filters_applied" in self._do_scan().json()

    def test_item_has_ticker(self):
        data = self._do_scan().json()
        assert "ticker" in data["items"][0]

    def test_item_has_veto_flag(self):
        data = self._do_scan().json()
        assert "veto_flag" in data["items"][0]

    def test_item_has_rank(self):
        data = self._do_scan().json()
        assert "rank" in data["items"][0]


# ── Class 5: GET /scan/{scan_id} and GET /universe ───────────────────────────

class TestGetScanAndUniverse:
    """10 tests."""

    def _fake_scan_row(self, scan_id=None):
        import uuid
        from app.models import ScanResult
        row = MagicMock(spec=ScanResult)
        row.id = scan_id or uuid.uuid4()
        row.total_scanned = 1
        row.total_passed = 1
        row.total_vetoed = 0
        row.filters = {"min_score": 0.0}
        row.items = [{
            "ticker": "O", "score": 75.0, "grade": "B",
            "recommendation": "ACCUMULATE", "asset_class": "EQUITY_REIT",
            "chowder_signal": None, "chowder_number": None, "signal_penalty": 0.0,
            "rank": 1, "passed_quality_gate": True, "veto_flag": False, "score_details": {},
        }]
        row.created_at = "2026-03-12T00:00:00+00:00"
        return row

    def test_get_scan_not_found_returns_404(self):
        db = MagicMock()
        db.get = MagicMock(return_value=None)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get(f"/scan/{uuid4()}", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 404

    def test_get_scan_invalid_uuid_returns_422(self):
        resp = TestClient(app).get("/scan/not-a-uuid", headers=AUTH)
        assert resp.status_code == 422

    def test_get_scan_found_returns_200(self):
        row = self._fake_scan_row()
        db = MagicMock()
        db.get = MagicMock(return_value=row)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get(f"/scan/{row.id}", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200

    def test_get_scan_returns_scan_id(self):
        import uuid
        sid = uuid.uuid4()
        row = self._fake_scan_row(scan_id=sid)
        db = MagicMock()
        db.get = MagicMock(return_value=row)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            data = TestClient(app).get(f"/scan/{sid}", headers=AUTH).json()
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert data["scan_id"] == str(sid)

    def test_universe_returns_200(self):
        db = MagicMock()
        db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get("/universe", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200

    def test_universe_returns_total(self):
        db = MagicMock()
        db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            data = TestClient(app).get("/universe", headers=AUTH).json()
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert "total" in data

    def test_universe_returns_securities_key(self):
        db = MagicMock()
        db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            data = TestClient(app).get("/universe", headers=AUTH).json()
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert "securities" in data

    def test_universe_active_only_default(self):
        db = MagicMock()
        db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get("/universe", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200

    def test_universe_asset_type_filter(self):
        db = MagicMock()
        db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get("/universe?asset_type=ETF", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200

    def test_universe_limit_param_accepted(self):
        db = MagicMock()
        db.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get("/universe?limit=10", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
