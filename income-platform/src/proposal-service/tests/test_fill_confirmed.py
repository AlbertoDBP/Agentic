"""Tests for POST /proposals/{id}/fill-confirmed endpoint."""
import pytest
from datetime import datetime, timezone
from tests.conftest import Proposal, TestingSessionLocal


def _create_proposal(status: str = "executed_aligned") -> int:
    db = TestingSessionLocal()
    try:
        p = Proposal(
            ticker="RVT",
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id
    finally:
        db.close()


def test_fill_confirmed_transitions_to_executed_filled(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 20.0,
            "avg_fill_price": 18.42,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "filled",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed_filled"


def test_fill_confirmed_partial_fill(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 14.0,
            "avg_fill_price": 18.42,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "partially_filled",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "partially_filled"


def test_fill_confirmed_cancelled(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 0.0,
            "avg_fill_price": 0.0,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "cancelled",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_fill_confirmed_rejects_invalid_status(client, auth_headers):
    pid = _create_proposal("executed_aligned")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={
            "filled_qty": 5.0,
            "avg_fill_price": 18.0,
            "filled_at": "2026-03-30T10:00:00Z",
            "status": "blah",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_fill_confirmed_404_on_missing(client, auth_headers):
    resp = client.post(
        "/proposals/9999/fill-confirmed",
        json={"filled_qty": 1.0, "avg_fill_price": 10.0,
              "filled_at": "2026-03-30T10:00:00Z", "status": "filled"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_fill_confirmed_rejects_pending_proposal(client, auth_headers):
    pid = _create_proposal("pending")
    resp = client.post(
        f"/proposals/{pid}/fill-confirmed",
        json={"filled_qty": 1.0, "avg_fill_price": 10.0,
              "filled_at": "2026-03-30T10:00:00Z", "status": "filled"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
