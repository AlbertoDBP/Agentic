"""
Agent 08 — Rebalancing Service
Tests: Rebalancing engine — 40 tests.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")
os.environ.setdefault("TAX_OPTIMIZATION_URL", "http://agent-05:8005")

from app.rebalancer.engine import RebalanceEngineResult, run_rebalance


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _pos(symbol: str, weight: float = 5.0, value: float = 5000.0, qty: float = 50.0,
         cost_basis: float = 100.0, acquired_date=None) -> dict:
    return {
        "symbol": symbol,
        "current_value": value,
        "portfolio_weight_pct": weight,
        "quantity": qty,
        "avg_cost_basis": cost_basis,
        "annual_income": value * 0.05,
        "yield_on_value": 5.0,
        "acquired_date": acquired_date,
        "position_id": "some-uuid",
    }


def _score(score: float, grade: str = None, chowder_signal: str = "ATTRACTIVE",
           recommendation: str = "ACCUMULATE", commentary: str = None) -> dict:
    if grade is None:
        if score >= 80:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 50:
            grade = "D"
        else:
            grade = "F"
    return {
        "total_score": score,
        "grade": grade,
        "chowder_signal": chowder_signal,
        "recommendation": recommendation,
        "score_commentary": commentary,
    }


def _score_hhs(
    score: float,
    grade: str = None,
    hhs_score: float = 75.0,
    hhs_status: str = "GOOD",
    unsafe_flag: bool = False,
    ies_score: float = 75.0,
    ies_calculated: bool = True,
    yield_on_value: float = 5.0,
) -> dict:
    """Extended score dict including HHS/IES fields used by updated engine."""
    base = _score(score, grade)
    base.update({
        "hhs_score": hhs_score,
        "hhs_status": hhs_status,
        "unsafe_flag": unsafe_flag,
        "ies_score": ies_score,
        "ies_calculated": ies_calculated,
    })
    return base


def _portfolio(value: float = 100_000.0, capital: float = 0.0) -> dict:
    return {"total_value": value, "capital_to_deploy": capital}


def _constraints(max_pct: float = 10.0, min_grade: str = "B") -> dict:
    return {"max_position_pct": max_pct, "min_income_score_grade": min_grade}


def _metrics(actual: float = 5000.0, target: float = 6000.0, gap: float = -1000.0) -> dict:
    return {"actual_income_annual": actual, "target_income_annual": target, "income_gap_annual": gap}


def _tax_impact(savings: float = 200.0, long_term: bool = True, wash_risk: bool = False) -> dict:
    return {
        "unrealized_loss": -500.0,
        "tax_savings_estimated": savings,
        "long_term": long_term,
        "wash_sale_risk": wash_risk,
        "action": "HARVEST_NOW",
    }


# ── Class 1: Basic rebalancing behavior ───────────────────────────────────────

class TestBasicRebalance:
    """10 tests covering fundamental rebalancing behavior."""

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_empty_positions_returns_empty_proposals(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        result = await run_rebalance("pid-1")
        assert result.proposals == []
        assert result.violations_count == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_passing_position_no_violation(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0, min_grade="B"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(80.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.violations_count == 0
        assert result.proposals == []

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_veto_position_generates_sell_priority1(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(50.0, grade="D")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert len(result.proposals) == 1
        assert result.proposals[0]["action"] == "SELL"
        assert result.proposals[0]["priority"] == 1
        assert result.proposals[0]["violation_type"] == "VETO"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_overweight_position_generates_trim_priority2(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BIG", weight=15.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(80.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert len(result.proposals) == 1
        assert result.proposals[0]["action"] == "TRIM"
        assert result.proposals[0]["priority"] == 2
        assert result.proposals[0]["violation_type"] == "OVERWEIGHT"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_below_grade_generates_sell_priority3(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("LOW", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(min_grade="B"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        # Score is above veto threshold but grade is C (below B minimum)
        mock_score.return_value = _score(72.0, grade="C")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert len(result.proposals) == 1
        assert result.proposals[0]["action"] == "SELL"
        assert result.proposals[0]["priority"] == 3
        assert result.proposals[0]["violation_type"] == "BELOW_GRADE"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_proposal_when_capital_to_deploy(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", weight=5.0, value=5000.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0, capital=10_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(85.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert len(result.proposals) == 1
        assert result.proposals[0]["action"] == "ADD"
        assert result.proposals[0]["priority"] == 4

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_proposals_sorted_by_priority(self, mock_reader, mock_score, mock_tax):
        positions = [
            _pos("BELOW", weight=5.0),   # will be BELOW_GRADE
            _pos("OVER", weight=15.0),   # will be OVERWEIGHT
            _pos("VETO", weight=3.0),    # will be VETO
        ]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0, min_grade="B"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())

        async def _side_effect(ticker):
            if ticker == "VETO":
                return _score(40.0, grade="F")
            if ticker == "OVER":
                return _score(85.0, grade="A")  # overweight but good score
            if ticker == "BELOW":
                return _score(72.0, grade="C")  # above veto but below grade B
            return None

        mock_score.side_effect = _side_effect
        result = await run_rebalance("pid-1", include_tax_impact=False)
        priorities = [p["priority"] for p in result.proposals]
        assert priorities == sorted(priorities)

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_total_savings_computed_from_tax_impact(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = _tax_impact(savings=500.0)
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.tax_impact_total_savings == 500.0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_violations_count_matches_actual(self, mock_reader, mock_score, mock_tax):
        positions = [_pos("A"), _pos("B"), _pos("C")]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = lambda t: _score(40.0, grade="F")  # all VETO
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.violations_count == 3

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_portfolio_value_propagated(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=250_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(85.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.portfolio_value == 250_000.0


# ── Class 2: Violation priority edge cases ────────────────────────────────────

class TestViolationPriority:
    """10 tests covering priority rules and edge cases."""

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_veto_takes_priority_over_overweight(self, mock_reader, mock_score, mock_tax):
        """A position that is both VETO and OVERWEIGHT should only get VETO (priority 1)."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("X", weight=20.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")  # VETO threshold
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert len(result.proposals) == 1
        assert result.proposals[0]["violation_type"] == "VETO"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_multiple_veto_positions_all_flagged(self, mock_reader, mock_score, mock_tax):
        positions = [_pos("A"), _pos("B"), _pos("C")]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = lambda t: _score(30.0, grade="F")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        veto_proposals = [p for p in result.proposals if p["violation_type"] == "VETO"]
        assert len(veto_proposals) == 3

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_mixed_violations_all_present(self, mock_reader, mock_score, mock_tax):
        positions = [
            _pos("VETO_POS", weight=5.0),
            _pos("OVER_POS", weight=15.0),
            _pos("GRADE_POS", weight=5.0),
        ]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0, min_grade="B"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())

        async def _side(ticker):
            if ticker == "VETO_POS":
                return _score(40.0, grade="F")
            if ticker == "OVER_POS":
                return _score(85.0, grade="A")
            return _score(72.0, grade="C")

        mock_score.side_effect = _side
        result = await run_rebalance("pid-1", include_tax_impact=False)
        vtypes = {p["violation_type"] for p in result.proposals}
        assert "VETO" in vtypes
        assert "OVERWEIGHT" in vtypes
        assert "BELOW_GRADE" in vtypes

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_max_proposals_truncates(self, mock_reader, mock_score, mock_tax):
        positions = [_pos(f"T{i}", weight=5.0) for i in range(10)]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = lambda t: _score(40.0, grade="F")
        result = await run_rebalance("pid-1", include_tax_impact=False, max_proposals=3)
        assert len(result.proposals) == 3

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_no_add_when_no_capital(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0, capital=0.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(90.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        add_proposals = [p for p in result.proposals if p["action"] == "ADD"]
        assert len(add_proposals) == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_no_add_when_at_max_weight(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", weight=10.0, value=10_000.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0, capital=5000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(90.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        add_proposals = [p for p in result.proposals if p["action"] == "ADD"]
        assert len(add_proposals) == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_grade_ordering_correct(self, mock_reader, mock_score, mock_tax):
        """Grade A > B > C > D > F — C is below B minimum."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("X", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(min_grade="B"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(72.0, grade="C")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["violation_type"] == "BELOW_GRADE"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_min_grade_a_only_a_passes(self, mock_reader, mock_score, mock_tax):
        """When min_grade=A, only grade A positions are clean."""
        positions = [_pos("A_POS"), _pos("B_POS")]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(min_grade="A"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())

        async def _side(ticker):
            if ticker == "A_POS":
                return _score(90.0, grade="A")
            return _score(80.0, grade="B")  # B is below A min

        mock_score.side_effect = _side
        result = await run_rebalance("pid-1", include_tax_impact=False)
        below_grade = [p for p in result.proposals if p["violation_type"] == "BELOW_GRADE"]
        assert len(below_grade) == 1
        assert below_grade[0]["symbol"] == "B_POS"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_no_violations_when_all_pass(self, mock_reader, mock_score, mock_tax):
        positions = [_pos("A"), _pos("B")]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0, min_grade="B"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = lambda t: _score(85.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.violations_count == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_income_gap_propagated_from_metrics(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(
            return_value=_metrics(actual=4000.0, target=6000.0, gap=-2000.0)
        )
        mock_score.return_value = _score(85.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.income_gap_annual == -2000.0


# ── Class 3: Tax enrichment ───────────────────────────────────────────────────

class TestTaxEnrichment:
    """10 tests covering tax impact integration."""

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_tax_impact_populated_when_enabled(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = _tax_impact(savings=300.0)
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.proposals[0]["tax_impact"] is not None
        assert result.proposals[0]["tax_impact"]["estimated_tax_savings"] == 300.0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_tax_impact_none_when_disabled(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["tax_impact"] is None
        mock_tax.assert_not_called()

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_tax_impact_none_when_agent05_returns_none(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = None
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.proposals[0]["tax_impact"] is None

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_proposals_skip_tax_enrichment(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", weight=5.0, value=5000.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(value=100_000.0, capital=10_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(90.0, grade="A")
        mock_tax.return_value = _tax_impact()
        result = await run_rebalance("pid-1", include_tax_impact=True)
        add_proposals = [p for p in result.proposals if p["action"] == "ADD"]
        assert len(add_proposals) > 0
        assert add_proposals[0]["tax_impact"] is None
        mock_tax.assert_not_called()

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_long_term_flag_set_correctly(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = _tax_impact(long_term=True)
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.proposals[0]["tax_impact"]["long_term"] is True

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_wash_sale_risk_flag_set_correctly(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = _tax_impact(wash_risk=True)
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.proposals[0]["tax_impact"]["wash_sale_risk"] is True

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_total_savings_summed_correctly(self, mock_reader, mock_score, mock_tax):
        positions = [_pos("A"), _pos("B")]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = lambda t: _score(40.0, grade="F")
        mock_tax.return_value = _tax_impact(savings=150.0)
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.tax_impact_total_savings == 300.0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_total_savings_none_when_no_savings(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = _tax_impact(savings=0.0)
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert result.tax_impact_total_savings is None

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_tax_client_called_with_correct_symbol(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("MYSTOCK")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = None
        await run_rebalance("pid-1", include_tax_impact=True)
        call_kwargs = mock_tax.call_args
        assert call_kwargs.kwargs["symbol"] == "MYSTOCK" or call_kwargs.args[0] == "MYSTOCK"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_tax_client_error_does_not_fail_result(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("BAD")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        mock_tax.return_value = None  # tax client gracefully returns None on error
        result = await run_rebalance("pid-1", include_tax_impact=True)
        assert len(result.proposals) == 1  # proposal still returned


# ── Class 4: Agent integration edge cases ────────────────────────────────────

class TestAgentIntegration:
    """10 tests covering agent interaction behaviors."""

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_agent03_none_response_skips_position(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("X")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = None
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals == []

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_all_positions_failing_agent03_returns_empty(self, mock_reader, mock_score, mock_tax):
        positions = [_pos(f"X{i}") for i in range(5)]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = None
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals == []
        assert result.violations_count == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_score_exactly_at_threshold_not_veto(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("X", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(min_grade="C"))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(70.0, grade="B")  # exactly at gate
        result = await run_rebalance("pid-1", include_tax_impact=False)
        veto_proposals = [p for p in result.proposals if p.get("violation_type") == "VETO"]
        assert len(veto_proposals) == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_score_below_threshold_is_veto(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("X")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(69.9, grade="C")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["violation_type"] == "VETO"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_agent03_grade_mapped_to_proposal(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["income_grade"] == "F"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_income_score_in_proposal_matches_total_score(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(42.5, grade="F")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["income_score"] == 42.5

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_score_commentary_propagated(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F", commentary="Dividend at risk")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["score_commentary"] == "Dividend at risk"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_chowder_signal_propagated(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score(40.0, grade="F", chowder_signal="UNATTRACTIVE")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals[0]["chowder_signal"] == "UNATTRACTIVE"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_concurrent_agent03_calls_bounded_by_semaphore(self, mock_reader, mock_score, mock_tax):
        """Engine should gather all calls without hanging (semaphore doesn't block progress)."""
        positions = [_pos(f"T{i}") for i in range(20)]
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = lambda t: _score(85.0, grade="A")
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert mock_score.call_count == 20

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_portfolio_reader_unavailable_returns_empty(self, mock_reader, mock_score, mock_tax):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_portfolio = AsyncMock(return_value=None)
        mock_reader.get_constraints = AsyncMock(return_value=None)
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=None)
        result = await run_rebalance("pid-1", include_tax_impact=False)
        assert result.proposals == []
        assert result.portfolio_value == 0.0


# ── Class 5: HHS/IES enhancements ────────────────────────────────────────────

class TestEngineHhsIesEnhancements:
    """Tests for UNSAFE priority, IES gate, income gap, and hhs_tiers."""

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_unsafe_generates_priority_0_above_veto(
        self, mock_reader, mock_score, mock_tax
    ):
        """UNSAFE flag must produce priority=0, beating VETO at priority=1."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("UNSAFE_TICKER", weight=5.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score_hhs(80.0, grade="A", unsafe_flag=True, hhs_score=30.0)
        result = await run_rebalance("pid-hhs-1", include_tax_impact=False)
        assert len(result.proposals) == 1
        assert result.proposals[0]["priority"] == 0
        assert result.proposals[0]["violation_type"] == "UNSAFE"
        assert result.proposals[0]["action"] == "SELL"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_unsafe_priority_beats_veto_in_sort(
        self, mock_reader, mock_score, mock_tax
    ):
        """When both UNSAFE and VETO exist, UNSAFE comes first."""
        mock_reader.get_positions = AsyncMock(return_value=[
            _pos("VETO_TICKER", weight=5.0),
            _pos("UNSAFE_TICKER", weight=5.0),
        ])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = [
            _score_hhs(50.0, grade="D"),                            # VETO_TICKER
            _score_hhs(80.0, grade="A", unsafe_flag=True, hhs_score=15.0),  # UNSAFE_TICKER
        ]
        result = await run_rebalance("pid-hhs-2", include_tax_impact=False)
        assert result.proposals[0]["violation_type"] == "UNSAFE"
        assert result.proposals[1]["violation_type"] == "VETO"

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_blocked_when_ies_not_calculated(
        self, mock_reader, mock_score, mock_tax
    ):
        """ADD proposal must not be generated when ies_calculated=False."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("MAIN", weight=3.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(capital=10_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score_hhs(80.0, grade="A", ies_calculated=False, ies_score=None)
        result = await run_rebalance("pid-hhs-3", include_tax_impact=False)
        assert result.proposals == []

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_blocked_when_ies_below_70(
        self, mock_reader, mock_score, mock_tax
    ):
        """ADD proposal must not be generated when ies_score < 70."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("LOW_IES", weight=3.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(capital=10_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score_hhs(80.0, grade="A", ies_calculated=True, ies_score=65.0)
        result = await run_rebalance("pid-hhs-4", include_tax_impact=False)
        assert result.proposals == []

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_proposals_sorted_by_income_contribution_desc(
        self, mock_reader, mock_score, mock_tax
    ):
        """ADD proposals must be ranked by income_contribution_est descending."""
        mock_reader.get_positions = AsyncMock(return_value=[
            {**_pos("LOW_YIELD", weight=3.0), "yield_on_value": 2.0},
            {**_pos("HIGH_YIELD", weight=3.0), "yield_on_value": 8.0},
        ])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(capital=20_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.return_value = _score_hhs(80.0, grade="A", ies_calculated=True, ies_score=80.0)
        result = await run_rebalance("pid-hhs-5", include_tax_impact=False)
        add_proposals = [p for p in result.proposals if p["action"] == "ADD"]
        assert len(add_proposals) == 2
        assert add_proposals[0]["symbol"] == "HIGH_YIELD"
        assert add_proposals[0]["income_contribution_est"] > add_proposals[1]["income_contribution_est"]

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_hhs_tiers_populated_in_violations_summary(
        self, mock_reader, mock_score, mock_tax
    ):
        """violations_summary must include hhs_tiers with counts per status."""
        mock_reader.get_positions = AsyncMock(return_value=[
            _pos("A", weight=5.0), _pos("B", weight=5.0), _pos("C", weight=5.0),
        ])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio())
        mock_reader.get_constraints = AsyncMock(return_value=_constraints())
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=_metrics())
        mock_score.side_effect = [
            _score_hhs(80.0, grade="A", unsafe_flag=True, hhs_status="UNSAFE"),
            _score_hhs(72.0, grade="B", hhs_status="GOOD"),
            _score_hhs(78.0, grade="A", hhs_status="STRONG"),
        ]
        result = await run_rebalance("pid-hhs-6", include_tax_impact=False)
        tiers = result.violations_summary.get("hhs_tiers", {})
        assert tiers["UNSAFE"] == 1
        assert tiers["GOOD"] == 1
        assert tiers["STRONG"] == 1
        assert tiers.get("WATCH", 0) == 0

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_reason_includes_income_gap_string(
        self, mock_reader, mock_score, mock_tax
    ):
        """ADD reason must include gap percentage when income gap exists."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("MAIN", weight=3.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(capital=10_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(
            return_value=_metrics(actual=4000.0, target=6000.0, gap=-2000.0)
        )
        mock_score.return_value = _score_hhs(80.0, grade="A", ies_calculated=True, ies_score=80.0)
        result = await run_rebalance("pid-hhs-7", include_tax_impact=False)
        add_proposals = [p for p in result.proposals if p["action"] == "ADD"]
        assert len(add_proposals) == 1
        assert "gap" in add_proposals[0]["reason"].lower()

    @pytest.mark.anyio
    @patch("app.rebalancer.engine.get_harvest_impact", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.score_ticker", new_callable=AsyncMock)
    @patch("app.rebalancer.engine.portfolio_reader")
    async def test_add_reason_graceful_when_income_gap_none(
        self, mock_reader, mock_score, mock_tax
    ):
        """ADD reason must not crash when income_gap_annual is None."""
        mock_reader.get_positions = AsyncMock(return_value=[_pos("MAIN", weight=3.0)])
        mock_reader.get_portfolio = AsyncMock(return_value=_portfolio(capital=10_000.0))
        mock_reader.get_constraints = AsyncMock(return_value=_constraints(max_pct=10.0))
        mock_reader.get_latest_income_metrics = AsyncMock(return_value=None)  # no metrics
        mock_score.return_value = _score_hhs(80.0, grade="A", ies_calculated=True, ies_score=80.0)
        result = await run_rebalance("pid-hhs-8", include_tax_impact=False)
        add_proposals = [p for p in result.proposals if p["action"] == "ADD"]
        assert len(add_proposals) == 1
        assert isinstance(add_proposals[0]["reason"], str)
