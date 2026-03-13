"""
Agent 08 — Rebalancing Service
Tests: API endpoints — 35 tests.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")
os.environ.setdefault("TAX_OPTIMIZATION_URL", "http://agent-05:8005")

from app.database import get_db
from app.main import app
from app.rebalancer.engine import RebalanceEngineResult

_TOKEN = jwt.encode({"sub": "test"}, os.environ["JWT_SECRET"], algorithm="HS256")
AUTH = {"Authorization": f"Bearer {_TOKEN}"}

_PORTFOLIO_ID = str(uuid4())


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _engine_result(portfolio_value: float = 100_000.0, violations: int = 0, proposals=None):
    """Build a minimal RebalanceEngineResult for mocking."""
    if proposals is None:
        proposals = []
    return RebalanceEngineResult(
        portfolio_value=portfolio_value,
        actual_income_annual=5000.0,
        target_income_annual=6000.0,
        income_gap_annual=-1000.0,
        violations_count=violations,
        violations_summary={"count": violations, "veto": 0, "overweight": 0, "below_grade": 0},
        proposals=proposals,
        tax_impact_total_savings=None,
    )


def _make_db_mock(result_id=None):
    """Return a mock Session with add/commit/refresh that sets id and created_at."""
    db = MagicMock()

    def _refresh(obj):
        obj.id = result_id or uuid.uuid4()
        obj.created_at = "2026-03-12T00:00:00+00:00"

    db.refresh = MagicMock(side_effect=_refresh)
    return db


def _override_db(db_mock):
    """FastAPI dependency override factory."""
    def _dep():
        yield db_mock
    return _dep


def _fake_result_row(row_id=None, portfolio_id=None):
    """Construct a mock RebalancingResult ORM row."""
    from app.models import RebalancingResult
    row = MagicMock(spec=RebalancingResult)
    row.id = row_id or uuid.uuid4()
    row.portfolio_id = uuid.UUID(portfolio_id) if portfolio_id else uuid.uuid4()
    row.violations = {"count": 0, "veto": 0, "overweight": 0, "below_grade": 0}
    row.proposals = []
    row.filters = {
        "portfolio_value": 100_000.0,
        "actual_income_annual": 5000.0,
        "target_income_annual": 6000.0,
        "income_gap_annual": -1000.0,
    }
    row.total_tax_savings = None
    row.created_at = "2026-03-12T00:00:00+00:00"
    return row


# ── Class 1: Health endpoint ───────────────────────────────────────────────────

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

    def test_health_returns_agent_id_8(self):
        with patch("app.api.health.check_db_health", return_value=True):
            data = TestClient(app).get("/health").json()
        assert data["agent_id"] == 8

    def test_health_db_connected(self):
        with patch("app.api.health.check_db_health", return_value=True):
            data = TestClient(app).get("/health").json()
        assert data["database"] == "connected"

    def test_health_db_unavailable(self):
        with patch("app.api.health.check_db_health", return_value=False):
            data = TestClient(app).get("/health").json()
        assert data["database"] == "unavailable"


# ── Class 2: POST /rebalance/{portfolio_id} — auth ────────────────────────────

class TestRebalanceAuth:
    """5 tests."""

    def test_post_rebalance_no_auth_returns_403(self):
        resp = TestClient(app).post(
            f"/rebalance/{_PORTFOLIO_ID}", json={}
        )
        assert resp.status_code == 403

    def test_post_rebalance_invalid_token_returns_401(self):
        resp = TestClient(app).post(
            f"/rebalance/{_PORTFOLIO_ID}", json={},
            headers={"Authorization": "Bearer bad.token.here"},
        )
        assert resp.status_code == 401

    def test_post_rebalance_valid_auth_passes(self):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.rebalance.run_rebalance", new_callable=AsyncMock,
                       return_value=_engine_result()):
                resp = TestClient(app).post(
                    f"/rebalance/{_PORTFOLIO_ID}", json={}, headers=AUTH
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code != 403

    def test_get_rebalance_result_no_auth_returns_403(self):
        resp = TestClient(app).get(f"/rebalance/{uuid4()}")
        assert resp.status_code == 403

    def test_get_history_no_auth_returns_403(self):
        resp = TestClient(app).get(f"/rebalance/portfolio/{uuid4()}/history")
        assert resp.status_code == 403


# ── Class 3: POST /rebalance/{portfolio_id} — request validation ──────────────

class TestRebalanceValidation:
    """5 tests."""

    def test_invalid_uuid_portfolio_id_returns_422(self):
        resp = TestClient(app).post("/rebalance/not-a-uuid", json={}, headers=AUTH)
        assert resp.status_code == 422

    def test_max_proposals_zero_returns_422(self):
        resp = TestClient(app).post(
            f"/rebalance/{_PORTFOLIO_ID}",
            json={"max_proposals": 0},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_max_proposals_51_returns_422(self):
        resp = TestClient(app).post(
            f"/rebalance/{_PORTFOLIO_ID}",
            json={"max_proposals": 51},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_invalid_cash_override_type_returns_422(self):
        resp = TestClient(app).post(
            f"/rebalance/{_PORTFOLIO_ID}",
            json={"cash_override": "not-a-number"},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_missing_body_uses_defaults(self):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.rebalance.run_rebalance", new_callable=AsyncMock,
                       return_value=_engine_result()):
                resp = TestClient(app).post(
                    f"/rebalance/{_PORTFOLIO_ID}", json={}, headers=AUTH
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200


# ── Class 4: POST /rebalance/{portfolio_id} — response structure ──────────────

class TestRebalanceResponse:
    """10 tests."""

    def _do_post(self, save: bool = False, **body_kwargs):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.rebalance.run_rebalance", new_callable=AsyncMock,
                       return_value=_engine_result()):
                resp = TestClient(app).post(
                    f"/rebalance/{_PORTFOLIO_ID}?save={str(save).lower()}",
                    json=body_kwargs or {},
                    headers=AUTH,
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_returns_200(self):
        assert self._do_post().status_code == 200

    def test_result_id_in_response(self):
        assert "result_id" in self._do_post().json()

    def test_portfolio_id_in_response(self):
        data = self._do_post().json()
        assert data["portfolio_id"] == _PORTFOLIO_ID

    def test_violations_count_in_response(self):
        assert "violations_count" in self._do_post().json()

    def test_proposals_is_list(self):
        data = self._do_post().json()
        assert isinstance(data["proposals"], list)

    def test_generated_at_in_response(self):
        assert "generated_at" in self._do_post().json()

    def test_save_false_does_not_persist(self):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.rebalance.run_rebalance", new_callable=AsyncMock,
                       return_value=_engine_result()):
                TestClient(app).post(
                    f"/rebalance/{_PORTFOLIO_ID}?save=false",
                    json={},
                    headers=AUTH,
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        db.add.assert_not_called()

    def test_save_true_persists(self):
        db = _make_db_mock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.rebalance.run_rebalance", new_callable=AsyncMock,
                       return_value=_engine_result()):
                TestClient(app).post(
                    f"/rebalance/{_PORTFOLIO_ID}?save=true",
                    json={},
                    headers=AUTH,
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_get_rebalance_not_found_returns_404(self):
        db = MagicMock()
        db.get = MagicMock(return_value=None)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get(f"/rebalance/{uuid4()}", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 404

    def test_get_rebalance_found_returns_200(self):
        row = _fake_result_row()
        db = MagicMock()
        db.get = MagicMock(return_value=row)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = TestClient(app).get(f"/rebalance/{row.id}", headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200


# ── Class 5: GET /rebalance/portfolio/{portfolio_id}/history ──────────────────

class TestPortfolioHistory:
    """10 tests."""

    def _do_history(self, portfolio_id=None, limit=None, rows=None):
        pid = portfolio_id or _PORTFOLIO_ID
        db = MagicMock()
        mock_rows = rows if rows is not None else []
        # Chain: db.query(...).filter(...).order_by(...).limit(...).all()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_rows
        app.dependency_overrides[get_db] = _override_db(db)
        url = f"/rebalance/portfolio/{pid}/history"
        if limit is not None:
            url += f"?limit={limit}"
        try:
            resp = TestClient(app).get(url, headers=AUTH)
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_history_returns_200(self):
        assert self._do_history().status_code == 200

    def test_history_returns_portfolio_id(self):
        data = self._do_history().json()
        assert "portfolio_id" in data

    def test_history_returns_results_list(self):
        data = self._do_history().json()
        assert isinstance(data["results"], list)

    def test_history_returns_total(self):
        data = self._do_history().json()
        assert "total" in data

    def test_history_limit_param_works(self):
        rows = [_fake_result_row() for _ in range(5)]
        data = self._do_history(limit=5, rows=rows).json()
        assert data["total"] == 5

    def test_history_limit_out_of_range_returns_422(self):
        resp = TestClient(app).get(
            f"/rebalance/portfolio/{_PORTFOLIO_ID}/history?limit=0",
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_history_portfolio_id_is_uuid(self):
        data = self._do_history().json()
        # Should parse as UUID without exception
        uuid.UUID(data["portfolio_id"])

    def test_history_empty_returns_empty_list(self):
        data = self._do_history(rows=[]).json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_history_total_count_correct(self):
        rows = [_fake_result_row() for _ in range(3)]
        data = self._do_history(rows=rows).json()
        assert data["total"] == 3

    def test_history_portfolio_id_preserved_in_response(self):
        pid = str(uuid4())
        data = self._do_history(portfolio_id=pid).json()
        assert data["portfolio_id"] == pid
