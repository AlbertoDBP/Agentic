"""45 API tests for proposal-service endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.proposal_engine.engine import ProposalError, ProposalResult
from tests.conftest import (
    make_entry_price,
    make_score,
    make_signal,
    make_tax_placement,
)
from datetime import datetime, timedelta, timezone


def _make_proposal_result(
    ticker: str = "O",
    alignment: str = "Aligned",
    veto_flags=None,
    entry_method: str = "yield_based",
) -> ProposalResult:
    return ProposalResult(
        ticker=ticker,
        analyst_signal_id=101,
        analyst_id=5,
        platform_score=50.0,
        platform_alignment=alignment,
        veto_flags=veto_flags,
        divergence_notes=None if alignment == "Aligned" else "Divergence detected.",
        analyst_recommendation="Buy",
        analyst_sentiment=0.0,
        analyst_thesis_summary="Strong income generator.",
        analyst_yield_estimate=0.055,
        analyst_safety_grade="A",
        platform_yield_estimate=0.055,
        platform_safety_result={"dividend_coverage": "safe"},
        platform_income_grade="B",
        entry_price_low=52.0,
        entry_price_high=55.0,
        position_size_pct=5.0,
        recommended_account="Roth IRA",
        sizing_rationale="Buy O at or below $55.00",
        status="pending",
        trigger_mode="on_demand",
        trigger_ref_id=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        entry_method=entry_method,
    )


# ---------------------------------------------------------------------------
# Group 1: Health endpoint (5 tests)
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_agent_id_is_12(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.json()["agent_id"] == 12

    def test_health_status_healthy_when_db_ok(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        assert resp.json()["status"] == "healthy"

    def test_health_status_degraded_when_db_down(self, client):
        with patch("app.api.health.check_db_health", return_value=False):
            resp = client.get("/health")
        assert resp.json()["status"] == "degraded"

    def test_health_no_auth_required(self, client):
        with patch("app.api.health.check_db_health", return_value=True):
            resp = client.get("/health")
        # No Authorization header — should still be 200
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group 2: Auth — 401/403 (8 tests)
# ---------------------------------------------------------------------------

class TestAuth:
    def test_proposals_list_requires_auth(self, client):
        resp = client.get("/proposals")
        assert resp.status_code == 403

    def test_proposals_generate_requires_auth(self, client):
        resp = client.post("/proposals/generate", json={"ticker": "O"})
        assert resp.status_code == 403

    def test_proposals_get_by_id_requires_auth(self, client):
        resp = client.get("/proposals/1")
        assert resp.status_code == 403

    def test_proposals_execute_requires_auth(self, client):
        resp = client.post("/proposals/1/execute")
        assert resp.status_code == 403

    def test_proposals_override_requires_auth(self, client):
        resp = client.post("/proposals/1/override", json={"rationale": "x" * 25})
        assert resp.status_code == 403

    def test_proposals_reject_requires_auth(self, client):
        resp = client.post("/proposals/1/reject")
        assert resp.status_code == 403

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/proposals", headers={"Authorization": "Bearer bad.token.here"}
        )
        assert resp.status_code == 401

    def test_malformed_bearer_returns_403(self, client):
        resp = client.get("/proposals", headers={"Authorization": "NotBearer token"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group 3: POST /proposals/generate (12 tests)
# ---------------------------------------------------------------------------

class TestGenerateProposal:
    def _patch_engine(self, result=None, side_effect=None):
        r = result or _make_proposal_result()
        if side_effect:
            return patch(
                "app.api.proposals.run_proposal",
                new=AsyncMock(side_effect=side_effect),
            )
        return patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=r),
        )

    def test_single_ticker_returns_proposal(self, client, auth_headers):
        with self._patch_engine():
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "O"

    def test_single_ticker_has_status_pending(self, client, auth_headers):
        with self._patch_engine():
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.json()["status"] == "pending"

    def test_batch_tickers_returns_list(self, client, auth_headers):
        r1 = _make_proposal_result(ticker="O")
        r2 = _make_proposal_result(ticker="MAIN")
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(side_effect=[r1, r2]),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"tickers": ["O", "MAIN"]},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_batch_tickers_contains_correct_tickers(self, client, auth_headers):
        r1 = _make_proposal_result(ticker="O")
        r2 = _make_proposal_result(ticker="MAIN")
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(side_effect=[r1, r2]),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"tickers": ["O", "MAIN"]},
                headers=auth_headers,
            )
        tickers = [p["ticker"] for p in resp.json()]
        assert "O" in tickers
        assert "MAIN" in tickers

    def test_agent02_failure_returns_503(self, client, auth_headers):
        with self._patch_engine(side_effect=ProposalError("Agent 02 down")):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.status_code == 503

    def test_agent02_failure_error_message(self, client, auth_headers):
        with self._patch_engine(side_effect=ProposalError("Agent 02 down")):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert "Cannot generate proposal" in resp.json()["detail"]

    def test_agent03_failure_proposal_still_generated(self, client, auth_headers):
        # Agent 03 failure → degraded but still returns 200
        result = _make_proposal_result()
        result.platform_score = None
        result.platform_alignment = "Partial"
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.status_code == 200

    def test_agent04_failure_market_fallback_flagged(self, client, auth_headers):
        result = _make_proposal_result(entry_method="market_fallback")
        result.entry_price_low = None
        result.entry_price_high = None
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["entry_method"] == "market_fallback"

    def test_no_ticker_or_tickers_returns_422(self, client, auth_headers):
        resp = client.post(
            "/proposals/generate",
            json={"trigger_mode": "on_demand"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_invalid_trigger_mode_returns_422(self, client, auth_headers):
        resp = client.post(
            "/proposals/generate",
            json={"ticker": "O", "trigger_mode": "invalid_mode"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_proposal_persisted_in_db(self, client, auth_headers):
        with self._patch_engine():
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        proposal_id = resp.json()["id"]
        # Retrieve it
        with patch("app.api.health.check_db_health", return_value=True):
            get_resp = client.get(f"/proposals/{proposal_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == proposal_id

    def test_proposal_has_correct_analyst_recommendation(self, client, auth_headers):
        with self._patch_engine():
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        assert resp.json()["analyst_recommendation"] == "Buy"


# ---------------------------------------------------------------------------
# Group 4: GET /proposals — list + filters (5 tests)
# ---------------------------------------------------------------------------

class TestListProposals:
    def _create_proposal(self, client, auth_headers, ticker="O"):
        result = _make_proposal_result(ticker=ticker)
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            client.post(
                "/proposals/generate",
                json={"ticker": ticker},
                headers=auth_headers,
            )

    def test_empty_list_on_no_proposals(self, client, auth_headers):
        resp = client.get("/proposals", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created_proposals(self, client, auth_headers):
        self._create_proposal(client, auth_headers)
        resp = client.get("/proposals", headers=auth_headers)
        assert len(resp.json()) >= 1

    def test_filter_by_ticker(self, client, auth_headers):
        self._create_proposal(client, auth_headers, ticker="O")
        self._create_proposal(client, auth_headers, ticker="MAIN")
        resp = client.get("/proposals?ticker=O", headers=auth_headers)
        tickers = [p["ticker"] for p in resp.json()]
        assert all(t == "O" for t in tickers)

    def test_filter_by_status(self, client, auth_headers):
        self._create_proposal(client, auth_headers)
        resp = client.get("/proposals?status=pending", headers=auth_headers)
        assert all(p["status"] == "pending" for p in resp.json())

    def test_limit_respected(self, client, auth_headers):
        for _ in range(3):
            self._create_proposal(client, auth_headers)
        resp = client.get("/proposals?limit=2", headers=auth_headers)
        assert len(resp.json()) <= 2


# ---------------------------------------------------------------------------
# Group 5: GET /proposals/{id} (3 tests)
# ---------------------------------------------------------------------------

class TestGetProposal:
    def test_get_existing_proposal(self, client, auth_headers):
        result = _make_proposal_result()
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            gen_resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        pid = gen_resp.json()["id"]
        resp = client.get(f"/proposals/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    def test_get_nonexistent_proposal_returns_404(self, client, auth_headers):
        resp = client.get("/proposals/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_proposal_returns_full_detail(self, client, auth_headers):
        result = _make_proposal_result()
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            gen_resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        pid = gen_resp.json()["id"]
        resp = client.get(f"/proposals/{pid}", headers=auth_headers)
        data = resp.json()
        assert "analyst_recommendation" in data
        assert "platform_alignment" in data
        assert "entry_price_low" in data


# ---------------------------------------------------------------------------
# Group 6: POST /proposals/{id}/execute (6 tests)
# ---------------------------------------------------------------------------

class TestExecuteProposal:
    def _create_proposal(self, client, auth_headers, alignment="Aligned", veto_flags=None):
        result = _make_proposal_result(alignment=alignment, veto_flags=veto_flags)
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        return resp.json()["id"]

    def test_execute_aligned_proposal_succeeds(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers, alignment="Aligned")
        resp = client.post(f"/proposals/{pid}/execute", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed_aligned"

    def test_execute_aligned_sets_decided_at(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        resp = client.post(f"/proposals/{pid}/execute", headers=auth_headers)
        assert resp.json()["decided_at"] is not None

    def test_execute_veto_without_ack_blocked(self, client, auth_headers):
        pid = self._create_proposal(
            client,
            auth_headers,
            alignment="Vetoed",
            veto_flags={"nav_erosion_penalty": 20.0},
        )
        resp = client.post(f"/proposals/{pid}/execute", headers=auth_headers)
        assert resp.status_code == 409

    def test_execute_veto_with_ack_succeeds(self, client, auth_headers):
        pid = self._create_proposal(
            client,
            auth_headers,
            alignment="Vetoed",
            veto_flags={"nav_erosion_penalty": 20.0},
        )
        resp = client.post(
            f"/proposals/{pid}/execute",
            json={"user_acknowledged_veto": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed_aligned"

    def test_execute_nonexistent_proposal_returns_404(self, client, auth_headers):
        resp = client.post("/proposals/99999/execute", headers=auth_headers)
        assert resp.status_code == 404

    def test_execute_already_executed_returns_409(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        client.post(f"/proposals/{pid}/execute", headers=auth_headers)
        resp = client.post(f"/proposals/{pid}/execute", headers=auth_headers)
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Group 7: POST /proposals/{id}/override (4 tests)
# ---------------------------------------------------------------------------

class TestOverrideProposal:
    def _create_proposal(self, client, auth_headers):
        result = _make_proposal_result(alignment="Vetoed", veto_flags={"nav_erosion_penalty": 20.0})
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        return resp.json()["id"]

    def test_override_short_rationale_returns_422(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        resp = client.post(
            f"/proposals/{pid}/override",
            json={"rationale": "too short"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_override_exactly_19_chars_returns_422(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        resp = client.post(
            f"/proposals/{pid}/override",
            json={"rationale": "x" * 19},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_override_with_valid_rationale_succeeds(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        resp = client.post(
            f"/proposals/{pid}/override",
            json={"rationale": "Analyst has superior sector knowledge here."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed_override"

    def test_override_stores_rationale(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        rationale = "I trust the analyst's thesis on this REIT sector."
        resp = client.post(
            f"/proposals/{pid}/override",
            json={"rationale": rationale},
            headers=auth_headers,
        )
        assert resp.json()["override_rationale"] == rationale


# ---------------------------------------------------------------------------
# Group 8: POST /proposals/{id}/reject (2 tests)
# ---------------------------------------------------------------------------

class TestRejectProposal:
    def _create_proposal(self, client, auth_headers):
        result = _make_proposal_result()
        with patch(
            "app.api.proposals.run_proposal",
            new=AsyncMock(return_value=result),
        ):
            resp = client.post(
                "/proposals/generate",
                json={"ticker": "O"},
                headers=auth_headers,
            )
        return resp.json()["id"]

    def test_reject_proposal_succeeds(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        resp = client.post(f"/proposals/{pid}/reject", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_proposal_sets_decided_at(self, client, auth_headers):
        pid = self._create_proposal(client, auth_headers)
        resp = client.post(f"/proposals/{pid}/reject", headers=auth_headers)
        assert resp.json()["decided_at"] is not None
