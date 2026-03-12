"""
Agent 06 — Scenario Simulation Service
Tests: API endpoints — 6 tests.
"""
import os
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import jwt
from fastapi.testclient import TestClient

from app.main import app

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

_TEST_TOKEN = jwt.encode(
    {"sub": "test"},
    os.environ["JWT_SECRET"],
    algorithm="HS256",
)
AUTH = {"Authorization": f"Bearer {_TEST_TOKEN}"}

client = TestClient(app)


# ── Fixtures / helpers ────────────────────────────────────────────────────────

SAMPLE_POSITIONS = [
    {
        "symbol": "O",
        "current_value": 10000.0,
        "annual_income": 500.0,
        "quantity": 100,
        "yield_on_value": 5.0,
        "portfolio_weight_pct": 100.0,
        "avg_cost_basis": 100.0,
        "portfolio_id": "00000000-0000-0000-0000-000000000001",
    }
]

SAMPLE_ASSET_CLASSES = {"O": "EQUITY_REIT"}


# 1. GET /health returns 200
def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


# 2. GET /scenarios/library returns 5 scenarios
def test_library_returns_5_scenarios():
    resp = client.get("/scenarios/library", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 5


# 3. POST /scenarios/stress-test with empty portfolio returns 422
@patch("app.api.scenarios.portfolio_reader.get_positions", new_callable=AsyncMock)
@patch("app.api.scenarios.portfolio_reader.get_asset_classes", new_callable=AsyncMock)
def test_stress_test_empty_portfolio_422(mock_ac, mock_pos):
    mock_pos.return_value = []
    mock_ac.return_value = {}
    resp = client.post("/scenarios/stress-test", headers=AUTH, json={
        "portfolio_id": "00000000-0000-0000-0000-000000000001",
        "scenario_type": "RATE_HIKE_200BPS",
    })
    assert resp.status_code == 422


# 4. POST /scenarios/income-projection with empty portfolio returns 422
@patch("app.api.scenarios.portfolio_reader.get_positions", new_callable=AsyncMock)
def test_income_projection_empty_portfolio_422(mock_pos):
    mock_pos.return_value = []
    resp = client.post("/scenarios/income-projection", headers=AUTH, json={
        "portfolio_id": "00000000-0000-0000-0000-000000000001",
        "horizon_months": 12,
    })
    assert resp.status_code == 422


# 5. POST /scenarios/stress-test with unknown scenario_type returns 422
@patch("app.api.scenarios.portfolio_reader.get_positions", new_callable=AsyncMock)
@patch("app.api.scenarios.portfolio_reader.get_asset_classes", new_callable=AsyncMock)
def test_stress_test_unknown_scenario_422(mock_ac, mock_pos):
    mock_pos.return_value = SAMPLE_POSITIONS
    mock_ac.return_value = SAMPLE_ASSET_CLASSES
    resp = client.post("/scenarios/stress-test", headers=AUTH, json={
        "portfolio_id": "00000000-0000-0000-0000-000000000001",
        "scenario_type": "NONEXISTENT_SCENARIO",
    })
    assert resp.status_code == 422


# 6. POST /scenarios/vulnerability returns ranked list
@patch("app.api.scenarios.portfolio_reader.get_positions", new_callable=AsyncMock)
@patch("app.api.scenarios.portfolio_reader.get_asset_classes", new_callable=AsyncMock)
def test_vulnerability_returns_rankings(mock_ac, mock_pos):
    mock_pos.return_value = SAMPLE_POSITIONS
    mock_ac.return_value = SAMPLE_ASSET_CLASSES
    resp = client.post("/scenarios/vulnerability", headers=AUTH, json={
        "portfolio_id": "00000000-0000-0000-0000-000000000001",
        "scenario_types": ["RATE_HIKE_200BPS", "MARKET_CORRECTION_20"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "rankings" in data
    assert len(data["rankings"]) >= 1
    assert "rank" in data["rankings"][0]
    assert "worst_scenario" in data["rankings"][0]
