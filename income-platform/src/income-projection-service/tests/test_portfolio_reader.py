"""
Agent 09 — Income Projection Service
Tests: portfolio_reader — 25 tests.
All tests use mocked asyncpg; no real DB connections.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

import app.projector.portfolio_reader as reader_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(rows=None, row=None):
    """Build a mock asyncpg pool that yields the given rows/row.

    Always wire both fetch and fetchrow so that calling code never gets back
    an un-awaited AsyncMock coroutine regardless of which argument was supplied.
    """
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rows if rows is not None else [])
    mock_conn.fetchrow = AsyncMock(return_value=row)   # None is a valid return value

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool, mock_conn


def _row(**kwargs):
    """Simulate an asyncpg Record as a dict (dict(row) pattern)."""
    return kwargs


# ---------------------------------------------------------------------------
# Class 1: get_positions (10 tests)
# ---------------------------------------------------------------------------

class TestGetPositions:

    @pytest.mark.anyio
    async def test_returns_list_of_dicts(self):
        rows = [
            _row(symbol="O", current_value=10000.0, yield_on_value=5.0,
                 annual_income=500.0, quantity=100.0, portfolio_weight_pct=10.0,
                 acquired_date=None, position_id="uuid-1"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-1")
        assert isinstance(result, list)
        assert result[0]["symbol"] == "O"

    @pytest.mark.anyio
    async def test_empty_when_no_active_positions(self):
        pool, _ = _make_pool(rows=[])
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-empty")
        assert result == []

    @pytest.mark.anyio
    async def test_returns_empty_when_pool_is_none(self):
        with patch.object(reader_module, "_pool", None):
            result = await reader_module.get_positions("pid-1")
        assert result == []

    @pytest.mark.anyio
    async def test_multiple_positions_returned(self):
        rows = [
            _row(symbol="O", current_value=10000.0, yield_on_value=5.0,
                 annual_income=500.0, quantity=100.0, portfolio_weight_pct=10.0,
                 acquired_date=None, position_id="uuid-1"),
            _row(symbol="T", current_value=5000.0, yield_on_value=4.0,
                 annual_income=200.0, quantity=50.0, portfolio_weight_pct=5.0,
                 acquired_date=None, position_id="uuid-2"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-1")
        assert len(result) == 2

    @pytest.mark.anyio
    async def test_position_has_symbol_key(self):
        rows = [_row(symbol="MAIN", current_value=8000.0, yield_on_value=4.5,
                     annual_income=360.0, quantity=80.0, portfolio_weight_pct=8.0,
                     acquired_date=None, position_id="uuid-3")]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-1")
        assert "symbol" in result[0]

    @pytest.mark.anyio
    async def test_position_has_current_value_key(self):
        rows = [_row(symbol="O", current_value=10000.0, yield_on_value=5.0,
                     annual_income=500.0, quantity=100.0, portfolio_weight_pct=10.0,
                     acquired_date=None, position_id="uuid-1")]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-1")
        assert "current_value" in result[0]

    @pytest.mark.anyio
    async def test_position_has_yield_on_value_key(self):
        rows = [_row(symbol="O", current_value=10000.0, yield_on_value=5.0,
                     annual_income=500.0, quantity=100.0, portfolio_weight_pct=10.0,
                     acquired_date=None, position_id="uuid-1")]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-1")
        assert "yield_on_value" in result[0]

    @pytest.mark.anyio
    async def test_position_values_match_row(self):
        rows = [_row(symbol="O", current_value=12345.0, yield_on_value=6.7,
                     annual_income=827.0, quantity=100.0, portfolio_weight_pct=12.0,
                     acquired_date=None, position_id="uuid-X")]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("pid-1")
        assert result[0]["current_value"] == 12345.0
        assert result[0]["yield_on_value"] == 6.7

    @pytest.mark.anyio
    async def test_fetch_called_with_portfolio_id(self):
        pool, mock_conn = _make_pool(rows=[])
        with patch.object(reader_module, "_pool", pool):
            await reader_module.get_positions("my-portfolio-uuid")
        call_args = mock_conn.fetch.call_args
        assert "my-portfolio-uuid" in call_args.args

    @pytest.mark.anyio
    async def test_nonexistent_portfolio_returns_empty(self):
        pool, _ = _make_pool(rows=[])
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_positions("nonexistent-pid")
        assert result == []


# ---------------------------------------------------------------------------
# Class 2: get_features (10 tests)
# ---------------------------------------------------------------------------

class TestGetFeatures:

    @pytest.mark.anyio
    async def test_returns_dict_keyed_by_symbol(self):
        rows = [
            _row(symbol="O", yield_trailing_12m=4.8, yield_forward=5.2,
                 yield_5yr_avg=5.0, div_cagr_1y=2.0, div_cagr_3y=3.0,
                 div_cagr_5y=4.0, chowder_number=8.2, payout_ratio=75.0,
                 as_of_date="2026-01-01"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["O"])
        assert "O" in result

    @pytest.mark.anyio
    async def test_empty_symbols_returns_empty_dict(self):
        with patch.object(reader_module, "_pool", MagicMock()):
            result = await reader_module.get_features([])
        assert result == {}

    @pytest.mark.anyio
    async def test_returns_empty_when_pool_is_none(self):
        with patch.object(reader_module, "_pool", None):
            result = await reader_module.get_features(["O"])
        assert result == {}

    @pytest.mark.anyio
    async def test_multiple_symbols_keyed_correctly(self):
        rows = [
            _row(symbol="O", yield_trailing_12m=4.8, yield_forward=5.2,
                 yield_5yr_avg=5.0, div_cagr_1y=2.0, div_cagr_3y=3.0,
                 div_cagr_5y=4.0, chowder_number=8.2, payout_ratio=75.0,
                 as_of_date="2026-01-01"),
            _row(symbol="T", yield_trailing_12m=3.5, yield_forward=3.8,
                 yield_5yr_avg=3.6, div_cagr_1y=1.5, div_cagr_3y=2.0,
                 div_cagr_5y=2.5, chowder_number=5.5, payout_ratio=60.0,
                 as_of_date="2026-01-01"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["O", "T"])
        assert "O" in result
        assert "T" in result

    @pytest.mark.anyio
    async def test_feature_row_has_yield_forward(self):
        rows = [
            _row(symbol="O", yield_trailing_12m=4.8, yield_forward=5.2,
                 yield_5yr_avg=5.0, div_cagr_1y=2.0, div_cagr_3y=3.0,
                 div_cagr_5y=4.0, chowder_number=8.2, payout_ratio=75.0,
                 as_of_date="2026-01-01"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["O"])
        assert result["O"]["yield_forward"] == 5.2

    @pytest.mark.anyio
    async def test_feature_row_has_div_cagr_3y(self):
        rows = [
            _row(symbol="O", yield_trailing_12m=4.8, yield_forward=5.2,
                 yield_5yr_avg=5.0, div_cagr_1y=2.0, div_cagr_3y=3.2,
                 div_cagr_5y=4.0, chowder_number=8.2, payout_ratio=75.0,
                 as_of_date="2026-01-01"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["O"])
        assert result["O"]["div_cagr_3y"] == 3.2

    @pytest.mark.anyio
    async def test_unknown_symbol_not_in_result(self):
        pool, _ = _make_pool(rows=[])
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["UNKNOWN"])
        assert "UNKNOWN" not in result

    @pytest.mark.anyio
    async def test_feature_values_match_row(self):
        rows = [
            _row(symbol="O", yield_trailing_12m=4.1, yield_forward=5.9,
                 yield_5yr_avg=5.0, div_cagr_1y=2.0, div_cagr_3y=3.0,
                 div_cagr_5y=4.0, chowder_number=9.9, payout_ratio=70.0,
                 as_of_date="2026-03-01"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["O"])
        assert result["O"]["yield_trailing_12m"] == 4.1
        assert result["O"]["chowder_number"] == 9.9

    @pytest.mark.anyio
    async def test_fetch_called_with_symbols_list(self):
        pool, mock_conn = _make_pool(rows=[])
        with patch.object(reader_module, "_pool", pool):
            await reader_module.get_features(["O", "T"])
        call_args = mock_conn.fetch.call_args
        # symbols list passed as second positional arg
        assert ["O", "T"] in call_args.args

    @pytest.mark.anyio
    async def test_as_of_date_present_in_feature(self):
        rows = [
            _row(symbol="O", yield_trailing_12m=4.8, yield_forward=5.2,
                 yield_5yr_avg=5.0, div_cagr_1y=2.0, div_cagr_3y=3.0,
                 div_cagr_5y=4.0, chowder_number=8.2, payout_ratio=75.0,
                 as_of_date="2026-03-12"),
        ]
        pool, _ = _make_pool(rows=rows)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_features(["O"])
        assert result["O"]["as_of_date"] == "2026-03-12"


# ---------------------------------------------------------------------------
# Class 3: get_portfolio (5 tests)
# ---------------------------------------------------------------------------

class TestGetPortfolio:

    @pytest.mark.anyio
    async def test_returns_dict_for_existing_portfolio(self):
        row = _row(id="pid-1", status="active")
        pool, _ = _make_pool(row=row)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_portfolio("pid-1")
        assert result is not None
        assert result["id"] == "pid-1"

    @pytest.mark.anyio
    async def test_returns_none_for_missing_portfolio(self):
        pool, _ = _make_pool(row=None)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_portfolio("nonexistent")
        assert result is None

    @pytest.mark.anyio
    async def test_returns_none_when_pool_is_none(self):
        with patch.object(reader_module, "_pool", None):
            result = await reader_module.get_portfolio("pid-1")
        assert result is None

    @pytest.mark.anyio
    async def test_fetchrow_called_with_portfolio_id(self):
        pool, mock_conn = _make_pool(row=None)
        with patch.object(reader_module, "_pool", pool):
            await reader_module.get_portfolio("test-portfolio-id")
        call_args = mock_conn.fetchrow.call_args
        assert "test-portfolio-id" in call_args.args

    @pytest.mark.anyio
    async def test_portfolio_status_in_returned_dict(self):
        row = _row(id="pid-2", status="active")
        pool, _ = _make_pool(row=row)
        with patch.object(reader_module, "_pool", pool):
            result = await reader_module.get_portfolio("pid-2")
        assert result["status"] == "active"
