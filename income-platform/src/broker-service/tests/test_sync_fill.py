"""Tests for POST /broker/positions/sync-fill endpoint."""
import os
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client_with_mock_db():
    """Return a TestClient with get_db and verify_token overridden."""
    from app.main import app
    from app.database import get_db
    from app.auth import verify_token

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    def override_verify_token():
        return "test-token"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_token] = override_verify_token
    yield TestClient(app), mock_db
    app.dependency_overrides.clear()


def _make_fetchone(qty=None, avg_cost=None):
    """Build a mock fetchone() return value (None for new position, row for existing)."""
    if qty is None:
        return None
    row = MagicMock()
    row.__getitem__ = lambda self, i: (qty if i == 0 else avg_cost)
    # Support positional access: existing[0], existing[1]
    row.__bool__ = lambda self: True
    # Use a simple tuple-like object
    return (qty, avg_cost)


def test_sync_fill_new_position(client_with_mock_db):
    """A brand-new position is created with the fill data."""
    client, mock_db = client_with_mock_db

    # fetchone returns None → new position
    mock_db.execute.return_value.fetchone.return_value = None

    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000001",
        "ticker": "RVT",
        "filled_qty": 20.0,
        "avg_fill_price": 18.42,
        "filled_at": "2026-03-30T10:00:00Z",
        "proposal_id": "42",
        "order_id": "abc123",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "RVT"
    assert data["total_shares"] == 20.0
    assert abs(data["new_avg_cost"] - 18.42) < 0.01
    assert data["is_new_position"] is True
    assert data["portfolio_id"] == "a1b2c3d4-0000-0000-0000-000000000001"
    assert mock_db.commit.called


def test_sync_fill_new_position_optional_fields_absent(client_with_mock_db):
    """Endpoint works without optional proposal_id / order_id / broker_ref."""
    client, mock_db = client_with_mock_db
    mock_db.execute.return_value.fetchone.return_value = None

    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000003",
        "ticker": "MAIN",
        "filled_qty": 5.0,
        "avg_fill_price": 25.00,
        "filled_at": "2026-03-30T12:00:00Z",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_new_position"] is True
    assert data["total_shares"] == 5.0


def test_sync_fill_weighted_average(client_with_mock_db):
    """Existing position gets weighted-average cost basis update."""
    client, mock_db = client_with_mock_db

    # Existing: 10 shares at $18.00
    mock_db.execute.return_value.fetchone.return_value = (10.0, 18.00)

    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000002",
        "ticker": "RVT",
        "filled_qty": 10.0,
        "avg_fill_price": 19.00,
        "filled_at": "2026-03-30T11:00:00Z",
    })

    assert resp.status_code == 200
    data = resp.json()
    # Weighted avg: (10 * 18.00 + 10 * 19.00) / 20 = 18.50
    assert abs(data["new_avg_cost"] - 18.50) < 0.01
    assert data["total_shares"] == 20.0
    assert data["is_new_position"] is False
    assert data["ticker"] == "RVT"
    assert mock_db.commit.called


def test_sync_fill_ticker_uppercased(client_with_mock_db):
    """Ticker is stored and returned uppercase regardless of input case."""
    client, mock_db = client_with_mock_db
    mock_db.execute.return_value.fetchone.return_value = None

    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000004",
        "ticker": "rvt",
        "filled_qty": 5.0,
        "avg_fill_price": 18.00,
        "filled_at": "2026-03-30T09:00:00Z",
    })

    assert resp.status_code == 200
    assert resp.json()["ticker"] == "RVT"


def test_sync_fill_missing_required_field(client_with_mock_db):
    """Missing required field returns 422 Unprocessable Entity."""
    client, _ = client_with_mock_db

    resp = client.post("/broker/positions/sync-fill", json={
        "portfolio_id": "a1b2c3d4-0000-0000-0000-000000000005",
        # missing ticker, filled_qty, avg_fill_price, filled_at
    })

    assert resp.status_code == 422
