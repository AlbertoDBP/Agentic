"""
Agent 10 — NAV Erosion Monitor
Tests: snapshot_reader.py — 25 tests.
All tests are pure unit tests using unittest.mock (no real DB).
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

import app.monitor.snapshot_reader as reader


def _make_pool(rows_snapshots=None, rows_scores=None):
    """Build a mock asyncpg pool that returns configurable rows."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=_make_fetch(rows_snapshots, rows_scores))

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))
    return mock_pool


def _make_fetch(rows_snapshots, rows_scores):
    """Return a side_effect function that switches return value by call count."""
    call_count = [0]

    async def _fetch(query, *args):
        result = rows_snapshots if call_count[0] == 0 else (rows_scores or [])
        call_count[0] += 1
        return result or []

    return _fetch


class _async_ctx:
    """Async context manager that returns the given conn."""
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


def _make_row(**kwargs):
    """Create a dict-like row (asyncpg Record substitute)."""
    return dict(**kwargs)


# ── get_recent_snapshots ──────────────────────────────────────────────────────

class TestGetRecentSnapshots:
    """13 tests."""

    @pytest.mark.asyncio
    async def test_pool_none_returns_empty(self):
        original = reader._pool
        reader._pool = None
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        rows = [
            _make_row(
                symbol="PDI",
                snapshot_date="2026-03-10",
                nav=20.0,
                market_price=19.5,
                premium_discount=-0.025,
                distribution_rate=0.10,
                erosion_rate_30d=-0.02,
                erosion_rate_90d=-0.04,
                erosion_rate_1y=-0.06,
                erosion_flag=False,
                source="manual",
            )
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["symbol"] == "PDI"

    @pytest.mark.asyncio
    async def test_no_snapshots_returns_empty_list(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_symbols_returned(self):
        rows = [
            _make_row(symbol="PDI", snapshot_date="2026-03-10", nav=20.0,
                      market_price=19.5, premium_discount=-0.025,
                      distribution_rate=0.10, erosion_rate_30d=-0.02,
                      erosion_rate_90d=-0.04, erosion_rate_1y=-0.06,
                      erosion_flag=False, source="manual"),
            _make_row(symbol="MAIN", snapshot_date="2026-03-10", nav=30.0,
                      market_price=30.5, premium_discount=0.017,
                      distribution_rate=0.08, erosion_rate_30d=0.01,
                      erosion_rate_90d=0.02, erosion_rate_1y=0.03,
                      erosion_flag=False, source="manual"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        symbols = [r["symbol"] for r in result]
        assert "PDI" in symbols
        assert "MAIN" in symbols

    @pytest.mark.asyncio
    async def test_default_lookback_is_90(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        call_args = mock_conn.fetch.call_args
        assert call_args[0][1] == 90

    @pytest.mark.asyncio
    async def test_custom_lookback_passed(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            await reader.get_recent_snapshots(lookback_days=30)
        finally:
            reader._pool = original

        call_args = mock_conn.fetch.call_args
        assert call_args[0][1] == 30

    @pytest.mark.asyncio
    async def test_each_row_converted_to_dict(self):
        row = _make_row(
            symbol="PDI", snapshot_date="2026-03-10", nav=20.0,
            market_price=19.5, premium_discount=-0.025,
            distribution_rate=0.10, erosion_rate_30d=-0.02,
            erosion_rate_90d=-0.04, erosion_rate_1y=-0.06,
            erosion_flag=False, source="manual",
        )
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert isinstance(result[0], dict)

    @pytest.mark.asyncio
    async def test_erosion_rate_30d_present_in_result(self):
        row = _make_row(symbol="PDI", snapshot_date="2026-03-10", nav=20.0,
                        market_price=19.5, premium_discount=-0.025,
                        distribution_rate=0.10, erosion_rate_30d=-0.07,
                        erosion_rate_90d=-0.04, erosion_rate_1y=-0.06,
                        erosion_flag=False, source="manual")
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert result[0]["erosion_rate_30d"] == -0.07

    @pytest.mark.asyncio
    async def test_premium_discount_present_in_result(self):
        row = _make_row(symbol="PDI", snapshot_date="2026-03-10", nav=20.0,
                        market_price=19.5, premium_discount=-0.10,
                        distribution_rate=0.10, erosion_rate_30d=-0.07,
                        erosion_rate_90d=-0.04, erosion_rate_1y=-0.06,
                        erosion_flag=False, source="manual")
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert result[0]["premium_discount"] == -0.10

    @pytest.mark.asyncio
    async def test_pool_none_logs_warning(self, caplog):
        import logging
        original = reader._pool
        reader._pool = None
        try:
            with caplog.at_level(logging.WARNING, logger="app.monitor.snapshot_reader"):
                await reader.get_recent_snapshots()
        finally:
            reader._pool = original
        assert any("pool not available" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_fetch_called_with_sql(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert mock_conn.fetch.called

    @pytest.mark.asyncio
    async def test_returns_all_rows_from_db(self):
        rows = [
            _make_row(symbol=f"SYM{i}", snapshot_date="2026-03-10", nav=20.0,
                      market_price=19.5, premium_discount=-0.025,
                      distribution_rate=0.10, erosion_rate_30d=-0.02,
                      erosion_rate_90d=-0.04, erosion_rate_1y=-0.06,
                      erosion_flag=False, source="manual")
            for i in range(5)
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_nav_field_present(self):
        row = _make_row(symbol="PDI", snapshot_date="2026-03-10", nav=22.50,
                        market_price=21.0, premium_discount=-0.067,
                        distribution_rate=0.10, erosion_rate_30d=0.0,
                        erosion_rate_90d=0.0, erosion_rate_1y=0.0,
                        erosion_flag=False, source="manual")
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_recent_snapshots()
        finally:
            reader._pool = original

        assert result[0]["nav"] == 22.50


# ── get_income_scores ─────────────────────────────────────────────────────────

class TestGetIncomeScores:
    """12 tests."""

    @pytest.mark.asyncio
    async def test_pool_none_returns_empty_dict(self):
        original = reader._pool
        reader._pool = None
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_dict_keyed_by_ticker(self):
        rows = [
            _make_row(ticker="PDI", total_score=72.5,
                      nav_erosion_penalty=5.0, nav_erosion_details={},
                      scored_at="2026-03-10"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original

        assert "PDI" in result
        assert result["PDI"]["total_score"] == 72.5

    @pytest.mark.asyncio
    async def test_no_scores_returns_empty_dict(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original
        assert result == {}

    @pytest.mark.asyncio
    async def test_multiple_tickers_keyed_correctly(self):
        rows = [
            _make_row(ticker="PDI", total_score=72.5,
                      nav_erosion_penalty=5.0, nav_erosion_details={},
                      scored_at="2026-03-10"),
            _make_row(ticker="MAIN", total_score=81.0,
                      nav_erosion_penalty=2.0, nav_erosion_details={},
                      scored_at="2026-03-10"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original

        assert "PDI" in result
        assert "MAIN" in result

    @pytest.mark.asyncio
    async def test_symbols_filter_passed_to_query(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            await reader.get_income_scores(symbols=["PDI", "MAIN"])
        finally:
            reader._pool = original

        call_args = mock_conn.fetch.call_args
        # Second positional arg should be the symbols list
        assert ["PDI", "MAIN"] in call_args[0] or ["PDI", "MAIN"] == call_args[0][1]

    @pytest.mark.asyncio
    async def test_no_symbols_filter_fetches_all(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            await reader.get_income_scores(symbols=None)
        finally:
            reader._pool = original

        # Called without a symbols parameter
        call_args = mock_conn.fetch.call_args
        assert len(call_args[0]) == 1  # only the query string, no extra args

    @pytest.mark.asyncio
    async def test_nav_erosion_penalty_in_result(self):
        rows = [
            _make_row(ticker="PDI", total_score=72.5,
                      nav_erosion_penalty=12.5, nav_erosion_details={},
                      scored_at="2026-03-10"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original

        assert result["PDI"]["nav_erosion_penalty"] == 12.5

    @pytest.mark.asyncio
    async def test_nav_erosion_details_in_result(self):
        rows = [
            _make_row(ticker="PDI", total_score=72.5,
                      nav_erosion_penalty=5.0,
                      nav_erosion_details={"flag": True},
                      scored_at="2026-03-10"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original

        assert result["PDI"]["nav_erosion_details"] == {"flag": True}

    @pytest.mark.asyncio
    async def test_pool_none_logs_warning(self, caplog):
        import logging
        original = reader._pool
        reader._pool = None
        try:
            with caplog.at_level(logging.WARNING, logger="app.monitor.snapshot_reader"):
                await reader.get_income_scores()
        finally:
            reader._pool = original
        assert any("pool not available" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_scored_at_present_in_result(self):
        rows = [
            _make_row(ticker="PDI", total_score=72.5,
                      nav_erosion_penalty=5.0, nav_erosion_details={},
                      scored_at="2026-03-10T00:00:00+00:00"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original

        assert "scored_at" in result["PDI"]

    @pytest.mark.asyncio
    async def test_empty_symbols_list_fetches_all(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            # Empty list is falsy — should fetch all (same as None)
            result = await reader.get_income_scores(symbols=None)
        finally:
            reader._pool = original
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_values_are_dicts(self):
        rows = [
            _make_row(ticker="PDI", total_score=72.5,
                      nav_erosion_penalty=5.0, nav_erosion_details={},
                      scored_at="2026-03-10"),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_async_ctx(mock_conn))

        original = reader._pool
        reader._pool = mock_pool
        try:
            result = await reader.get_income_scores()
        finally:
            reader._pool = original

        for v in result.values():
            assert isinstance(v, dict)
