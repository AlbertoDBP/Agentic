"""
Agent 09 — Income Projection Service
Tests: API endpoints — 35 tests.
All tests use FastAPI dependency_overrides to avoid real DB connections.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

import jwt as pyjwt

from app.database import get_db
from app.main import app
from app.projector.engine import ProjectionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRET = "test-secret-for-tests"


def _token(sub: str = "agent-08", expired: bool = False) -> str:
    import time
    exp = int(time.time()) + (-10 if expired else 3600)
    return pyjwt.encode({"sub": sub, "exp": exp}, _SECRET, algorithm="HS256")


def _make_result(
    portfolio_id: str = "pid-1",
    horizon_months: int = 12,
    yield_source: str = "forward",
    total_annual: float = 5400.0,
    positions_included: int = 5,
    positions_missing: int = 1,
) -> ProjectionResult:
    monthly_avg = round(total_annual / 12, 2)
    return ProjectionResult(
        portfolio_id=portfolio_id,
        horizon_months=horizon_months,
        yield_source=yield_source,
        total_projected_annual=total_annual,
        total_projected_monthly_avg=monthly_avg,
        monthly_cashflow=[
            {"month": m, "projected_income": monthly_avg}
            for m in range(1, horizon_months + 1)
        ],
        positions=[
            {
                "symbol": "O",
                "current_value": 10000.0,
                "yield_used_pct": 5.5,
                "projected_annual": 550.0,
                "div_cagr_3y": 3.2,
                "data_source": "features_historical",
            }
        ],
        positions_included=positions_included,
        positions_missing_data=positions_missing,
        computed_at=datetime(2026, 3, 12, 0, 0, 0, tzinfo=timezone.utc),
    )


def _make_db_record(
    portfolio_id: str = "pid-1",
    record_id: int = 1,
    total_annual: float = 5400.0,
    horizon: int = 12,
) -> MagicMock:
    rec = MagicMock()
    rec.id = record_id
    rec.portfolio_id = portfolio_id
    rec.computed_at = datetime(2026, 3, 12, 0, 0, 0, tzinfo=timezone.utc)
    rec.horizon_months = horizon
    rec.total_projected_annual = total_annual
    rec.total_projected_monthly_avg = round(total_annual / 12, 2)
    rec.yield_used = "forward"
    rec.positions_included = 5
    rec.positions_missing_data = 1
    rec.position_detail = []
    rec.metadata_ = {"monthly_cashflow": []}
    return rec


def _make_mock_db(first_result=None, all_results=None):
    """Return a mock Session whose query chain is fully wired."""
    mock_db = MagicMock()
    query_chain = mock_db.query.return_value
    query_chain.filter.return_value = query_chain
    query_chain.order_by.return_value = query_chain
    query_chain.limit.return_value = query_chain
    query_chain.first.return_value = first_result
    query_chain.all.return_value = all_results if all_results is not None else []
    return mock_db


def _override_db(mock_db):
    """Return a FastAPI dependency override function."""
    def _override():
        yield mock_db
    return _override


# ---------------------------------------------------------------------------
# Class 1: Health endpoint (5 tests)
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_200(self):
        with patch("app.api.health.check_db_health", return_value=False):
            with TestClient(app) as c:
                resp = c.get("/health")
        assert resp.status_code == 200

    def test_health_agent_id_is_9(self):
        with patch("app.api.health.check_db_health", return_value=False):
            with TestClient(app) as c:
                resp = c.get("/health")
        assert resp.json()["agent_id"] == 9

    def test_health_status_healthy(self):
        with patch("app.api.health.check_db_health", return_value=False):
            with TestClient(app) as c:
                resp = c.get("/health")
        assert resp.json()["status"] == "healthy"

    def test_health_database_connected_when_db_ok(self):
        with patch("app.api.health.check_db_health", return_value=True):
            with TestClient(app) as c:
                resp = c.get("/health")
        assert resp.json()["database"] == "connected"

    def test_health_database_unavailable_when_db_fails(self):
        with patch("app.api.health.check_db_health", return_value=False):
            with TestClient(app) as c:
                resp = c.get("/health")
        assert resp.json()["database"] == "unavailable"


# ---------------------------------------------------------------------------
# Class 2: Auth checks (8 tests)
# ---------------------------------------------------------------------------

class TestAuth:

    def test_post_projection_missing_token_returns_403(self):
        with TestClient(app) as c:
            resp = c.post("/projection/pid-1")
        assert resp.status_code == 403

    def test_post_projection_invalid_token_returns_401(self):
        with TestClient(app) as c:
            resp = c.post(
                "/projection/pid-1",
                headers={"Authorization": "Bearer not.a.real.token"},
            )
        assert resp.status_code == 401

    def test_post_projection_expired_token_returns_401(self):
        with TestClient(app) as c:
            resp = c.post(
                "/projection/pid-1",
                headers={"Authorization": f"Bearer {_token(expired=True)}"},
            )
        assert resp.status_code == 401

    def test_get_latest_missing_token_returns_403(self):
        with TestClient(app) as c:
            resp = c.get("/projection/pid-1/latest")
        assert resp.status_code == 403

    def test_get_latest_invalid_token_returns_401(self):
        with TestClient(app) as c:
            resp = c.get(
                "/projection/pid-1/latest",
                headers={"Authorization": "Bearer bad.token"},
            )
        assert resp.status_code == 401

    def test_get_history_missing_token_returns_403(self):
        with TestClient(app) as c:
            resp = c.get("/projection/pid-1/history")
        assert resp.status_code == 403

    def test_get_history_invalid_token_returns_401(self):
        with TestClient(app) as c:
            resp = c.get(
                "/projection/pid-1/history",
                headers={"Authorization": "Bearer bad.token"},
            )
        assert resp.status_code == 401

    def test_agent12_token_accepted(self):
        tok = _token(sub="agent-12")
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            with (
                patch("app.api.projection.portfolio_reader.get_portfolio",
                      new_callable=AsyncMock,
                      return_value={"id": "pid-1", "status": "active"}),
                patch("app.api.projection.portfolio_reader.get_positions",
                      new_callable=AsyncMock,
                      return_value=[{"symbol": "O"}]),
                patch("app.api.projection.run_projection",
                      new_callable=AsyncMock,
                      return_value=_make_result()),
            ):
                with TestClient(app) as c:
                    resp = c.post(
                        "/projection/pid-1",
                        headers={"Authorization": f"Bearer {tok}"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Class 3: POST /projection/{portfolio_id} (12 tests)
# ---------------------------------------------------------------------------

class TestPostProjection:

    def _post(
        self,
        portfolio_id: str = "pid-1",
        params: dict | None = None,
        result: ProjectionResult | None = None,
        portfolio_exists: bool = True,
        has_positions: bool = True,
    ):
        tok = _token()
        if result is None:
            result = _make_result(portfolio_id=portfolio_id)
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            with (
                patch("app.api.projection.portfolio_reader.get_portfolio",
                      new_callable=AsyncMock,
                      return_value={"id": portfolio_id, "status": "active"}
                      if portfolio_exists else None),
                patch("app.api.projection.portfolio_reader.get_positions",
                      new_callable=AsyncMock,
                      return_value=[{"symbol": "O"}] if has_positions else []),
                patch("app.api.projection.run_projection",
                      new_callable=AsyncMock,
                      return_value=result),
            ):
                with TestClient(app) as c:
                    resp = c.post(
                        f"/projection/{portfolio_id}",
                        params=params or {},
                        headers={"Authorization": f"Bearer {tok}"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_returns_200_for_valid_request(self):
        assert self._post().status_code == 200

    def test_response_has_portfolio_id(self):
        assert self._post().json()["portfolio_id"] == "pid-1"

    def test_response_has_horizon_months(self):
        assert "horizon_months" in self._post().json()

    def test_response_has_yield_source(self):
        assert "yield_source" in self._post().json()

    def test_response_has_total_projected_annual(self):
        assert "total_projected_annual" in self._post().json()

    def test_response_has_monthly_cashflow_list(self):
        assert isinstance(self._post().json()["monthly_cashflow"], list)

    def test_response_monthly_cashflow_length_matches_horizon(self):
        result = _make_result(horizon_months=12)
        resp = self._post(params={"horizon_months": 12}, result=result)
        assert len(resp.json()["monthly_cashflow"]) == 12

    def test_response_has_positions_list(self):
        assert isinstance(self._post().json()["positions"], list)

    def test_portfolio_not_found_returns_404(self):
        assert self._post(portfolio_exists=False).status_code == 404

    def test_no_active_positions_returns_400(self):
        assert self._post(has_positions=False).status_code == 400

    def test_invalid_yield_source_returns_400(self):
        tok = _token()
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            with (
                patch("app.api.projection.portfolio_reader.get_portfolio",
                      new_callable=AsyncMock,
                      return_value={"id": "pid-1", "status": "active"}),
                patch("app.api.projection.portfolio_reader.get_positions",
                      new_callable=AsyncMock,
                      return_value=[{"symbol": "O"}]),
            ):
                with TestClient(app) as c:
                    resp = c.post(
                        "/projection/pid-1",
                        params={"yield_source": "bad_source"},
                        headers={"Authorization": f"Bearer {tok}"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 400

    def test_horizon_months_above_60_returns_422(self):
        tok = _token()
        with TestClient(app) as c:
            resp = c.post(
                "/projection/pid-1",
                params={"horizon_months": 61},
                headers={"Authorization": f"Bearer {tok}"},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Class 4: GET /projection/{portfolio_id}/latest (5 tests)
# ---------------------------------------------------------------------------

class TestGetLatest:

    def _get(self, portfolio_id: str = "pid-1", db_record=None):
        tok = _token()
        mock_db = _make_mock_db(first_result=db_record)
        app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            with TestClient(app) as c:
                resp = c.get(
                    f"/projection/{portfolio_id}/latest",
                    headers={"Authorization": f"Bearer {tok}"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_returns_404_when_no_history(self):
        assert self._get(db_record=None).status_code == 404

    def test_returns_200_when_record_exists(self):
        assert self._get(db_record=_make_db_record()).status_code == 200

    def test_response_has_portfolio_id(self):
        resp = self._get(db_record=_make_db_record())
        assert "portfolio_id" in resp.json()

    def test_response_has_total_projected_annual(self):
        resp = self._get(db_record=_make_db_record(total_annual=7200.0))
        assert resp.json()["total_projected_annual"] == pytest.approx(7200.0, rel=1e-2)

    def test_response_has_horizon_months(self):
        resp = self._get(db_record=_make_db_record(horizon=24))
        assert resp.json()["horizon_months"] == 24


# ---------------------------------------------------------------------------
# Class 5: GET /projection/{portfolio_id}/history (5 tests)
# ---------------------------------------------------------------------------

class TestGetHistory:

    def _get(self, portfolio_id: str = "pid-1", records: list | None = None):
        tok = _token()
        records = records if records is not None else []
        mock_db = _make_mock_db(all_results=records)
        app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            with TestClient(app) as c:
                resp = c.get(
                    f"/projection/{portfolio_id}/history",
                    headers={"Authorization": f"Bearer {tok}"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        return resp

    def test_returns_200(self):
        assert self._get().status_code == 200

    def test_returns_empty_list_when_no_history(self):
        assert self._get(records=[]).json() == []

    def test_returns_list_with_records(self):
        records = [_make_db_record(record_id=i) for i in range(3)]
        assert len(self._get(records=records).json()) == 3

    def test_history_item_has_id(self):
        records = [_make_db_record(record_id=42)]
        assert self._get(records=records).json()[0]["id"] == 42

    def test_history_item_has_total_projected_annual(self):
        records = [_make_db_record(total_annual=9000.0)]
        assert self._get(records=records).json()[0]["total_projected_annual"] == pytest.approx(
            9000.0, rel=1e-2
        )
