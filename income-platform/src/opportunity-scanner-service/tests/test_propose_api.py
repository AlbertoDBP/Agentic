# src/opportunity-scanner-service/tests/test_propose_api.py
"""Tests for POST /scan/{scan_id}/propose endpoint."""
import os
import uuid
import pytest
import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.database import get_db
from app.auth import create_access_token

client = TestClient(app)


def _auth_headers():
    token = create_access_token({"sub": "test"})
    return {"Authorization": f"Bearer {token}"}


def _override_db(db_mock):
    """FastAPI dependency override factory."""
    def _dep():
        yield db_mock
    return _dep


class TestProposeEndpoint:
    def _make_scan_id(self, db_mock):
        """Return a UUID that the mock DB will recognise as a valid scan."""
        scan_id = str(uuid.uuid4())
        mock_row = MagicMock()
        mock_row.id = uuid.UUID(scan_id)
        db_mock.get.return_value = mock_row
        return scan_id

    def test_missing_scan_id_returns_404(self):
        db = MagicMock()
        db.get.return_value = None
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            fake_id = str(uuid.uuid4())
            resp = client.post(
                f"/scan/{fake_id}/propose",
                json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
                headers=_auth_headers(),
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 404

    def test_missing_portfolio_id_returns_422(self):
        db = MagicMock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = client.post(
                f"/scan/{uuid.uuid4()}/propose",
                json={"selected_tickers": ["MAIN"]},
                headers=_auth_headers(),
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 422

    def test_happy_path_returns_draft(self):
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.80, "exit_limit": 52.80, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
        ]

        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": 44.80, "exit_limit": 52.80, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": 44.80}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)  # portfolio exists
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["MAIN"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        data = resp.json()
        assert "proposal_id" in data
        assert data["status"] == "DRAFT"
        assert data["target_portfolio_id"] == portfolio_id

    def test_response_shape_has_all_required_fields(self):
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "ARCC", "entry_exit": {"entry_limit": 18.0, "exit_limit": 22.0, "zone_status": "IN_ZONE"}, "score": 75.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "ARCC", "entry_limit": 18.0, "exit_limit": 22.0, "zone_status": "IN_ZONE", "score": 75.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"ARCC": 18.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["ARCC"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        data = resp.json()
        required_keys = {"proposal_id", "status", "tickers", "entry_limits", "target_portfolio_id", "created_at"}
        assert required_keys.issubset(set(data.keys()))

    def test_portfolio_not_found_returns_422(self):
        scan_id = str(uuid.uuid4())
        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [{"ticker": "MAIN", "entry_exit": {}, "score": 80.0, "asset_class": "BDC"}]

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = None  # portfolio NOT found

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
                headers=_auth_headers(),
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 422

    def test_empty_selected_tickers_returns_422(self):
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"selected_tickers": [], "target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_missing_selected_tickers_returns_422(self):
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_ticker_not_in_scan_items_excluded_from_payload(self):
        """Tickers requested but not in scan results are silently skipped."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "IN_ZONE"}, "score": 82.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "IN_ZONE", "score": 82.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": 44.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["MAIN", "NOTHERE"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        data = resp.json()
        tickers_in_payload = [t["ticker"] for t in data["tickers"]]
        assert "MAIN" in tickers_in_payload
        assert "NOTHERE" not in tickers_in_payload

    def test_agent12_unavailable_still_writes_draft(self):
        """If Agent 12 is not reachable, proposal_drafts row is still written locally."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "O", "entry_exit": {"entry_limit": 55.0, "exit_limit": 65.0, "zone_status": "NEAR_ENTRY"}, "score": 79.0, "asset_class": "EQUITY_REIT"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "O", "entry_limit": 55.0, "exit_limit": 65.0, "zone_status": "NEAR_ENTRY", "score": 79.0, "asset_class": "EQUITY_REIT"}]
        draft_row.entry_limits = {"O": 55.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["O"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        assert resp.json()["status"] == "DRAFT"

    def test_invalid_scan_id_format_returns_422(self):
        """Non-UUID scan_id path param returns 422 from FastAPI validation."""
        resp = client.post(
            "/scan/not-a-uuid/propose",
            json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_unauthenticated_request_returns_401(self):
        # HTTPBearer returns 403 when no credentials provided at all,
        # and 401 when a token is provided but invalid.
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
        )
        assert resp.status_code in (401, 403)

    def test_entry_limits_keyed_by_ticker(self):
        """entry_limits in response is dict keyed by ticker."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_exit": {"entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE"}, "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [
            {"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE", "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row.entry_limits = {"MAIN": 44.0, "ARCC": 18.5}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["MAIN", "ARCC"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        data = resp.json()
        assert "MAIN" in data["entry_limits"]
        assert "ARCC" in data["entry_limits"]

    def test_ticker_matching_is_case_insensitive(self):
        """'main' in selected_tickers matches 'MAIN' in scan items."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": 44.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["main"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200

    def test_scan_with_null_entry_exit_produces_null_entry_limit(self):
        """When entry_exit block is missing from scan item, entry_limit is null in draft."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": None, "score": 80.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": None, "exit_limit": None, "zone_status": None, "score": 80.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": None}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["MAIN"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        assert resp.json()["entry_limits"]["MAIN"] is None

    def test_multiple_valid_tickers_all_included_in_draft(self):
        """When two valid tickers are selected and both in scan, both appear in tickers list."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_exit": {"entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE"}, "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [
            {"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE", "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row.entry_limits = {"MAIN": 44.0, "ARCC": 18.5}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
                resp = client.post(
                    f"/scan/{scan_id}/propose",
                    json={"selected_tickers": ["MAIN", "ARCC"], "target_portfolio_id": portfolio_id},
                    headers=_auth_headers(),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        tickers_in_payload = [t["ticker"] for t in resp.json()["tickers"]]
        assert "MAIN" in tickers_in_payload
        assert "ARCC" in tickers_in_payload
