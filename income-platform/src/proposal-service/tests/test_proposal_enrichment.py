"""Tests for proposal enrichment: zone_status computation and field mapping."""
import pytest
from unittest.mock import MagicMock, patch


# ── Zone status pure function ─────────────────────────────────────────────────

def test_zone_below_entry():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(40.0, 44.0, 47.0)
    assert status == "BELOW_ENTRY"
    assert pct < 0

def test_zone_in_zone():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(45.5, 44.0, 47.0)
    assert status == "IN_ZONE"
    assert pct > 0

def test_zone_above_entry():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(50.0, 44.0, 47.0)
    assert status == "ABOVE_ENTRY"

def test_zone_unknown_when_no_price():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(None, 44.0, 47.0)
    assert status == "UNKNOWN"
    assert pct is None

def test_zone_unknown_when_no_entry():
    from app.api.proposals import _compute_zone
    status, pct = _compute_zone(45.0, None, None)
    assert status == "UNKNOWN"


# ── Enrichment field mapping in _proposal_to_response ─────────────────────────

def test_proposal_to_response_with_enrichment():
    """_proposal_to_response maps enrichment dict fields onto ProposalResponse."""
    from app.api.proposals import _proposal_to_response
    from app.models import Proposal
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    p = Proposal(
        id=1, ticker="MAIN", status="pending",
        entry_price_low=44.0, entry_price_high=47.0,
        platform_score=72.0, analyst_recommendation="BUY",
        analyst_yield_estimate=0.071, platform_yield_estimate=0.068,
        platform_income_grade="A-", analyst_safety_grade="B+",
        created_at=now, updated_at=now,
    )
    enrichment = {
        "current_price": 45.5,
        "week52_high": 52.0,
        "week52_low": 38.0,
        "nav_value": None,
        "nav_discount_pct": None,
        "valuation_yield_score": 80.0,
        "financial_durability_score": 71.0,
        "technical_entry_score": 58.0,
    }
    resp = _proposal_to_response(p, enrichment=enrichment)
    assert resp.current_price == 45.5
    assert resp.zone_status == "IN_ZONE"
    assert resp.valuation_yield_score == 80.0
    assert resp.financial_durability_score == 71.0
    assert resp.week52_high == 52.0

def test_proposal_to_response_without_enrichment():
    """When enrichment is None, market fields default to None, zone_status to UNKNOWN."""
    from app.api.proposals import _proposal_to_response
    from app.models import Proposal
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    p = Proposal(id=2, ticker="TEST", status="pending", created_at=now, updated_at=now)
    resp = _proposal_to_response(p, enrichment=None)
    assert resp.current_price is None
    assert resp.zone_status == "UNKNOWN"
    assert resp.valuation_yield_score is None

def test_enrich_proposals_called_once_for_batch(client, auth_headers):
    """_enrich_proposals is called exactly once regardless of how many proposals are returned.

    Uses conftest fixtures: client (TestClient), auth_headers (Bearer JWT).
    The conftest's autouse clean_db fixture wipes proposals between tests.
    Seed two proposals directly via the DB session from conftest.TestingSessionLocal.
    """
    from unittest.mock import patch
    from conftest import TestingSessionLocal, Proposal as TestProposal
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()
    try:
        for ticker in ["MAIN", "ARCC"]:
            db.add(TestProposal(ticker=ticker, status="pending", created_at=now, updated_at=now))
        db.commit()
    finally:
        db.close()

    with patch("app.api.proposals._enrich_proposals", return_value={}) as mock_enrich:
        resp = client.get("/proposals?status=pending", headers=auth_headers)
        assert resp.status_code == 200
        assert mock_enrich.call_count == 1
        called_tickers = set(mock_enrich.call_args[0][1])
        assert "MAIN" in called_tickers
        assert "ARCC" in called_tickers
