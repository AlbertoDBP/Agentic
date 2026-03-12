"""
Agent 07 — Opportunity Scanner Service
Tests: Scanner engine — 40 tests.
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")

from app.scanner.engine import ScanEngineResult, ScanItem, run_scan


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _score(ticker: str, score: float, asset_class: str = "DIVIDEND_STOCK") -> dict:
    return {
        "ticker": ticker,
        "total_score": score,
        "grade": "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "D",
        "recommendation": "AGGRESSIVE_BUY" if score >= 80 else "ACCUMULATE" if score >= 70 else "HOLD" if score >= 60 else "AVOID",
        "asset_class": asset_class,
        "chowder_signal": "ATTRACTIVE" if score >= 70 else "UNATTRACTIVE",
        "chowder_number": score * 0.1,
        "signal_penalty": 0.0,
        "valuation_yield_score": score * 0.4,
        "financial_durability_score": score * 0.4,
        "technical_entry_score": score * 0.2,
        "nav_erosion_penalty": 0.0,
    }


# ── Class 1: Basic scan behavior ──────────────────────────────────────────────

class TestBasicScan:
    """10 tests covering fundamental scan behavior."""

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_empty_tickers_returns_zero_result(self, mock_score):
        result = await run_scan([])
        assert result.total_scanned == 0
        assert result.total_passed == 0
        assert result.total_vetoed == 0
        assert result.items == []

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_single_ticker_scored(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert result.total_scanned == 1
        assert mock_score.call_count == 1

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_none_response_skipped(self, mock_score):
        mock_score.return_value = None
        result = await run_scan(["BADTICKER"])
        assert result.total_scanned == 0

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_multiple_tickers_all_scored(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 75.0)
        result = await run_scan(["O", "JEPI", "MAIN"])
        assert result.total_scanned == 3

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_duplicate_tickers_deduplicated(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 75.0)
        result = await run_scan(["O", "O", "JEPI"])
        assert result.total_scanned == 2
        assert mock_score.call_count == 2

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_tickers_uppercased(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 75.0)
        await run_scan(["o", "jepi"])
        calls = [c.args[0] for c in mock_score.call_args_list]
        assert "O" in calls
        assert "JEPI" in calls

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_items_ranked_by_score_desc(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 90.0), "B": _score("B", 75.0), "C": _score("C", 80.0)
        }[t]
        result = await run_scan(["A", "B", "C"])
        scores = [it.score for it in result.items]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_rank_starts_at_1(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 75.0)
        result = await run_scan(["O", "JEPI"])
        assert result.items[0].rank == 1

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_all_items_populated(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 75.0)
        result = await run_scan(["O", "JEPI"])
        assert len(result.all_items) == 2

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_score_details_populated(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        item = result.items[0]
        assert "valuation_yield_score" in item.score_details
        assert "financial_durability_score" in item.score_details


# ── Class 2: VETO gate logic ──────────────────────────────────────────────────

class TestVetoGate:
    """10 tests covering VETO gate (score < 70 flagging)."""

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_score_above_70_not_vetoed(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert result.items[0].veto_flag is False
        assert result.items[0].passed_quality_gate is True

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_score_below_70_vetoed(self, mock_score):
        mock_score.return_value = _score("X", 55.0)
        result = await run_scan(["X"])
        assert result.all_items[0].veto_flag is True
        assert result.all_items[0].passed_quality_gate is False

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_score_exactly_70_passes_gate(self, mock_score):
        mock_score.return_value = _score("O", 70.0)
        result = await run_scan(["O"])
        assert result.items[0].passed_quality_gate is True
        assert result.items[0].veto_flag is False

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_total_vetoed_count_correct(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 80.0), "B": _score("B", 50.0), "C": _score("C", 45.0)
        }[t]
        result = await run_scan(["A", "B", "C"])
        assert result.total_vetoed == 2

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_quality_gate_only_excludes_vetoed(self, mock_score):
        mock_score.side_effect = lambda t: {
            "GOOD": _score("GOOD", 80.0), "BAD": _score("BAD", 50.0)
        }[t]
        result = await run_scan(["GOOD", "BAD"], quality_gate_only=True)
        tickers = [it.ticker for it in result.items]
        assert "GOOD" in tickers
        assert "BAD" not in tickers

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_quality_gate_false_includes_vetoed(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 50.0)
        result = await run_scan(["X"], quality_gate_only=False)
        assert len(result.items) == 1
        assert result.items[0].veto_flag is True

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_all_vetoed_total_passed_zero_when_gate_only(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 40.0)
        result = await run_scan(["A", "B"], quality_gate_only=True)
        assert result.total_passed == 0
        assert result.items == []

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_vetoed_still_appear_in_all_items(self, mock_score):
        mock_score.return_value = _score("X", 40.0)
        result = await run_scan(["X"], quality_gate_only=True)
        assert len(result.all_items) == 1
        assert result.all_items[0].veto_flag is True

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_score_zero_is_vetoed(self, mock_score):
        mock_score.return_value = _score("X", 0.0)
        result = await run_scan(["X"])
        assert result.all_items[0].veto_flag is True

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_score_100_passes_gate(self, mock_score):
        mock_score.return_value = _score("X", 100.0)
        result = await run_scan(["X"])
        assert result.items[0].passed_quality_gate is True


# ── Class 3: Filters ──────────────────────────────────────────────────────────

class TestFilters:
    """10 tests covering min_score, asset_classes, and combined filters."""

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_min_score_filter_excludes_below(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 80.0), "B": _score("B", 60.0)
        }[t]
        result = await run_scan(["A", "B"], min_score=75.0)
        assert len(result.items) == 1
        assert result.items[0].ticker == "A"

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_min_score_zero_passes_all(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 50.0)
        result = await run_scan(["A", "B"], min_score=0.0)
        assert len(result.items) == 2

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_min_score_exact_boundary_included(self, mock_score):
        mock_score.return_value = _score("X", 75.0)
        result = await run_scan(["X"], min_score=75.0)
        assert len(result.items) == 1

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_asset_class_filter_includes_matching(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 75.0, "EQUITY_REIT"),
            "B": _score("B", 75.0, "BDC"),
        }[t]
        result = await run_scan(["A", "B"], asset_classes=["EQUITY_REIT"])
        assert len(result.items) == 1
        assert result.items[0].ticker == "A"

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_asset_class_none_allows_all(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 75.0, "DIVIDEND_STOCK")
        result = await run_scan(["A", "B"], asset_classes=None)
        assert len(result.items) == 2

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_asset_class_multiple_allowed(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 75.0, "EQUITY_REIT"),
            "B": _score("B", 75.0, "BDC"),
            "C": _score("C", 75.0, "BOND"),
        }[t]
        result = await run_scan(["A", "B", "C"], asset_classes=["EQUITY_REIT", "BDC"])
        tickers = {it.ticker for it in result.items}
        assert tickers == {"A", "B"}

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_combined_min_score_and_gate_only(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 85.0),  # passes both
            "B": _score("B", 72.0),  # passes gate, fails min_score=80
            "C": _score("C", 50.0),  # fails gate
        }[t]
        result = await run_scan(["A", "B", "C"], min_score=80.0, quality_gate_only=True)
        assert len(result.items) == 1
        assert result.items[0].ticker == "A"

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_total_passed_reflects_filtered_count(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 85.0), "B": _score("B", 55.0)
        }[t]
        result = await run_scan(["A", "B"], min_score=80.0)
        assert result.total_passed == 1

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_no_match_returns_empty_items(self, mock_score):
        mock_score.side_effect = lambda t: _score(t, 50.0)
        result = await run_scan(["A", "B"], min_score=99.0)
        assert result.items == []
        assert result.total_passed == 0

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_rank_sequential_after_filter(self, mock_score):
        mock_score.side_effect = lambda t: {
            "A": _score("A", 90.0), "B": _score("B", 85.0), "C": _score("C", 50.0)
        }[t]
        result = await run_scan(["A", "B", "C"], min_score=80.0)
        ranks = [it.rank for it in result.items]
        assert ranks == [1, 2]


# ── Class 4: Error handling and concurrency ───────────────────────────────────

class TestErrorHandlingAndConcurrency:
    """10 tests covering partial failures, error resilience, and field types."""

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_partial_failure_still_returns_successes(self, mock_score):
        async def _side_effect(ticker):
            if ticker == "FAIL":
                return None
            return _score(ticker, 75.0)
        mock_score.side_effect = _side_effect
        result = await run_scan(["O", "FAIL", "JEPI"])
        assert result.total_scanned == 2

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_all_fail_returns_zero(self, mock_score):
        mock_score.return_value = None
        result = await run_scan(["A", "B", "C"])
        assert result.total_scanned == 0
        assert result.items == []

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_scan_item_ticker_matches_input(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert result.items[0].ticker == "O"

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_scan_item_score_is_float(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert isinstance(result.items[0].score, float)

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_scan_item_grade_is_string(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert isinstance(result.items[0].grade, str)

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_scan_item_veto_flag_is_bool(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert isinstance(result.items[0].veto_flag, bool)

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_engine_result_is_dataclass(self, mock_score):
        mock_score.return_value = _score("O", 75.0)
        result = await run_scan(["O"])
        assert isinstance(result, ScanEngineResult)

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_signal_penalty_captured(self, mock_score):
        data = _score("O", 75.0)
        data["signal_penalty"] = 5.0
        mock_score.return_value = data
        result = await run_scan(["O"])
        assert result.items[0].signal_penalty == 5.0

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_chowder_signal_none_allowed(self, mock_score):
        data = _score("O", 75.0)
        data["chowder_signal"] = None
        mock_score.return_value = data
        result = await run_scan(["O"])
        assert result.items[0].chowder_signal is None

    @pytest.mark.anyio
    @patch("app.scanner.engine.score_ticker", new_callable=AsyncMock)
    async def test_large_batch_deduplicated_correctly(self, mock_score):
        # 50 unique tickers + 50 duplicates = 50 scored
        tickers = [f"T{i}" for i in range(50)] * 2
        mock_score.side_effect = lambda t: _score(t, 75.0)
        result = await run_scan(tickers)
        assert result.total_scanned == 50
        assert mock_score.call_count == 50
