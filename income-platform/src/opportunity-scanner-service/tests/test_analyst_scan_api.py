"""Tests for analyst_ideas scan path and position_overrides in propose."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.scanner import router, ScanRequest, ProposeRequest


app = FastAPI()
app.include_router(router)


def test_scan_request_accepts_analyst_fields():
    """ScanRequest accepts analyst_ids, min_staleness_weight, include_history."""
    req = ScanRequest(
        source="analyst_ideas",
        analyst_ids=[1, 2],
        min_staleness_weight=0.5,
        include_history=True,
    )
    assert req.analyst_ids == [1, 2]
    assert req.min_staleness_weight == 0.5
    assert req.include_history is True


def test_propose_request_accepts_position_overrides():
    """ProposeRequest accepts optional position_overrides dict."""
    req = ProposeRequest(
        selected_tickers=["ARCC"],
        target_portfolio_id="00000000-0000-0000-0000-000000000001",
        position_overrides={"ARCC": {"amount_usd": 3000, "target_price": 19.50}},
    )
    assert req.position_overrides["ARCC"]["amount_usd"] == 3000
