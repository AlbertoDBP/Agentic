"""
Agent 09 — Income Projection Service
Tests: Projection engine — 40 tests.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

from app.projector.engine import ProjectionResult, run_projection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pos(
    symbol: str,
    value: float = 10_000.0,
    yield_on_value: float = 5.0,
    annual_income: float = 500.0,
) -> dict:
    return {
        "symbol": symbol,
        "current_value": value,
        "yield_on_value": yield_on_value,
        "annual_income": annual_income,
        "quantity": 100.0,
        "portfolio_weight_pct": 10.0,
        "acquired_date": None,
        "position_id": "some-uuid",
    }


def _feat(
    symbol: str,
    yield_forward: float | None = 5.5,
    yield_trailing: float | None = 5.0,
    div_cagr_3y: float | None = 3.2,
    div_cagr_1y: float | None = 2.0,
    div_cagr_5y: float | None = 4.0,
) -> dict:
    return {
        "symbol": symbol,
        "yield_forward": yield_forward,
        "yield_trailing_12m": yield_trailing,
        "yield_5yr_avg": 5.0,
        "div_cagr_1y": div_cagr_1y,
        "div_cagr_3y": div_cagr_3y,
        "div_cagr_5y": div_cagr_5y,
        "chowder_number": 8.7,
        "payout_ratio": 75.0,
        "as_of_date": "2026-01-01",
    }


# ---------------------------------------------------------------------------
# Class 1: Basic projection behaviour (10 tests)
# ---------------------------------------------------------------------------

class TestBasicProjection:

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_single_position_forward_yield(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O", yield_forward=5.5)})
        result = await run_projection("pid-1", horizon_months=12, yield_source="forward")
        assert isinstance(result, ProjectionResult)
        assert result.total_projected_annual == pytest.approx(550.0, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_single_position_trailing_yield(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O", yield_trailing=4.0)})
        result = await run_projection("pid-1", horizon_months=12, yield_source="trailing")
        assert result.total_projected_annual == pytest.approx(400.0, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_position_record_yield_source(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0, yield_on_value=6.0)])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", horizon_months=12, yield_source="position_record")
        assert result.total_projected_annual == pytest.approx(600.0, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_monthly_cashflow_length_equals_horizon(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O")})
        result = await run_projection("pid-1", horizon_months=12, yield_source="forward")
        assert len(result.monthly_cashflow) == 12

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_monthly_cashflow_custom_horizon(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O")})
        result = await run_projection("pid-1", horizon_months=24, yield_source="forward")
        assert len(result.monthly_cashflow) == 24

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_monthly_avg_equals_annual_divided_by_12(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=12_000.0)])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O", yield_forward=5.0)})
        result = await run_projection("pid-1", horizon_months=12, yield_source="forward")
        assert result.total_projected_monthly_avg == pytest.approx(
            result.total_projected_annual / 12.0, rel=1e-3
        )

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_monthly_cashflow_entries_have_month_key(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O")})
        result = await run_projection("pid-1", horizon_months=3, yield_source="forward")
        months = [e["month"] for e in result.monthly_cashflow]
        assert months == [1, 2, 3]

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_monthly_cashflow_entries_have_projected_income_key(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O")})
        result = await run_projection("pid-1", horizon_months=3, yield_source="forward")
        for entry in result.monthly_cashflow:
            assert "projected_income" in entry

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_div_cagr_3y_in_position_output(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O", div_cagr_3y=3.2)})
        result = await run_projection("pid-1", horizon_months=12, yield_source="forward")
        assert result.positions[0]["div_cagr_3y"] == pytest.approx(3.2, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_empty_positions_returns_zero_totals(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", horizon_months=12, yield_source="forward")
        assert result.total_projected_annual == 0.0
        assert result.positions_included == 0
        assert result.positions_missing_data == 0


# ---------------------------------------------------------------------------
# Class 2: Yield source fallback chain (10 tests)
# ---------------------------------------------------------------------------

class TestYieldFallback:

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_forward_used_when_available(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=6.0, yield_trailing=4.0)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["yield_used_pct"] == pytest.approx(6.0)
        assert result.positions[0]["data_source"] == "features_historical"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_trailing_fallback_when_forward_missing(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=None, yield_trailing=4.0)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["yield_used_pct"] == pytest.approx(4.0)
        assert result.positions[0]["data_source"] == "features_historical"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_position_record_fallback_when_both_features_missing(self, mock_reader):
        mock_reader.get_positions = AsyncMock(
            return_value=[_pos("O", value=10_000.0, yield_on_value=3.5)]
        )
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=None, yield_trailing=None)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["yield_used_pct"] == pytest.approx(3.5)
        assert result.positions[0]["data_source"] == "position_record"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_missing_when_no_yield_anywhere(self, mock_reader):
        pos = _pos("X", value=10_000.0)
        pos["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[pos])
        mock_reader.get_features = AsyncMock(
            return_value={"X": _feat("X", yield_forward=None, yield_trailing=None)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["data_source"] == "missing"
        assert result.positions[0]["projected_annual"] == 0.0
        assert result.positions_missing_data == 1

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_missing_when_no_features_row_and_no_position_yield(self, mock_reader):
        pos = _pos("X", value=10_000.0)
        pos["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[pos])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["data_source"] == "missing"
        assert result.positions_missing_data == 1

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_trailing_source_uses_trailing_first(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=6.0, yield_trailing=4.0)}
        )
        result = await run_projection("pid-1", yield_source="trailing")
        assert result.positions[0]["yield_used_pct"] == pytest.approx(4.0)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_trailing_source_falls_back_to_forward(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=6.0, yield_trailing=None)}
        )
        result = await run_projection("pid-1", yield_source="trailing")
        assert result.positions[0]["yield_used_pct"] == pytest.approx(6.0)
        assert result.positions[0]["data_source"] == "features_historical"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_position_record_source_uses_position_yield_directly(self, mock_reader):
        mock_reader.get_positions = AsyncMock(
            return_value=[_pos("O", value=10_000.0, yield_on_value=7.0)]
        )
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=6.0, yield_trailing=4.0)}
        )
        result = await run_projection("pid-1", yield_source="position_record")
        assert result.positions[0]["yield_used_pct"] == pytest.approx(7.0)
        assert result.positions[0]["data_source"] == "position_record"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_position_record_source_missing_when_no_yield(self, mock_reader):
        pos = _pos("X", value=10_000.0)
        pos["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[pos])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", yield_source="position_record")
        assert result.positions[0]["data_source"] == "missing"
        assert result.positions_missing_data == 1

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_invalid_yield_source_defaults_to_forward(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=10_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=5.5)}
        )
        result = await run_projection("pid-1", yield_source="invalid_source")
        assert result.yield_source == "forward"
        assert result.positions[0]["data_source"] == "features_historical"


# ---------------------------------------------------------------------------
# Class 3: Multiple positions & totals (10 tests)
# ---------------------------------------------------------------------------

class TestMultiplePositions:

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_two_positions_totals_sum(self, mock_reader):
        mock_reader.get_positions = AsyncMock(
            return_value=[_pos("O", value=10_000.0), _pos("MAIN", value=5_000.0)]
        )
        mock_reader.get_features = AsyncMock(
            return_value={
                "O": _feat("O", yield_forward=5.0),
                "MAIN": _feat("MAIN", yield_forward=4.0),
            }
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.total_projected_annual == pytest.approx(700.0, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_positions_included_count(self, mock_reader):
        mock_reader.get_positions = AsyncMock(
            return_value=[_pos("O"), _pos("T"), _pos("MAIN")]
        )
        mock_reader.get_features = AsyncMock(
            return_value={
                "O": _feat("O", yield_forward=5.0),
                "T": _feat("T", yield_forward=3.0),
                "MAIN": _feat("MAIN", yield_forward=4.0),
            }
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions_included == 3
        assert result.positions_missing_data == 0

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_positions_missing_counted_separately(self, mock_reader):
        good = _pos("O", value=10_000.0)
        bad = _pos("X", value=5_000.0)
        bad["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[good, bad])
        mock_reader.get_features = AsyncMock(
            return_value={
                "O": _feat("O", yield_forward=5.0),
                "X": _feat("X", yield_forward=None, yield_trailing=None),
            }
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions_included == 1
        assert result.positions_missing_data == 1

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_missing_position_does_not_inflate_total(self, mock_reader):
        good = _pos("O", value=10_000.0)
        bad = _pos("X", value=5_000.0)
        bad["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[good, bad])
        mock_reader.get_features = AsyncMock(
            return_value={
                "O": _feat("O", yield_forward=5.0),
                "X": _feat("X", yield_forward=None, yield_trailing=None),
            }
        )
        result = await run_projection("pid-1", yield_source="forward")
        # Only O contributes: 10000 * 5% = 500
        assert result.total_projected_annual == pytest.approx(500.0, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_positions_list_length_equals_all_positions(self, mock_reader):
        mock_reader.get_positions = AsyncMock(
            return_value=[_pos("A"), _pos("B"), _pos("C")]
        )
        mock_reader.get_features = AsyncMock(
            return_value={
                "A": _feat("A"),
                "B": _feat("B"),
                "C": _feat("C"),
            }
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert len(result.positions) == 3

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_projected_annual_per_position_correct(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=20_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=5.0)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["projected_annual"] == pytest.approx(1000.0, rel=1e-3)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_position_symbol_in_output(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("REALTY")])
        mock_reader.get_features = AsyncMock(
            return_value={"REALTY": _feat("REALTY", yield_forward=5.5)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["symbol"] == "REALTY"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_current_value_in_position_output(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=12_345.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=5.0)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["current_value"] == pytest.approx(12_345.0)

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_div_cagr_3y_none_when_no_features(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("X")])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions[0]["div_cagr_3y"] is None

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_all_missing_gives_zero_annual(self, mock_reader):
        pos = _pos("X")
        pos["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[pos])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", yield_source="forward")
        assert result.total_projected_annual == 0.0


# ---------------------------------------------------------------------------
# Class 4: Result metadata & edge cases (10 tests)
# ---------------------------------------------------------------------------

class TestResultMetadata:

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_result_has_portfolio_id(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("my-portfolio-id")
        assert result.portfolio_id == "my-portfolio-id"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_result_has_yield_source(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", yield_source="trailing")
        assert result.yield_source == "trailing"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_result_has_horizon_months(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1", horizon_months=24)
        assert result.horizon_months == 24

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_result_computed_at_is_set(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[])
        mock_reader.get_features = AsyncMock(return_value={})
        result = await run_projection("pid-1")
        assert result.computed_at is not None

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_horizon_60_months_cashflow_length(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O")])
        mock_reader.get_features = AsyncMock(return_value={"O": _feat("O")})
        result = await run_projection("pid-1", horizon_months=60)
        assert len(result.monthly_cashflow) == 60

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_monthly_cashflow_uniform_distribution(self, mock_reader):
        mock_reader.get_positions = AsyncMock(return_value=[_pos("O", value=12_000.0)])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=10.0)}
        )
        result = await run_projection("pid-1", horizon_months=12)
        incomes = [e["projected_income"] for e in result.monthly_cashflow]
        assert all(i == incomes[0] for i in incomes), "All months should be equal (uniform)"

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_positions_included_excludes_missing(self, mock_reader):
        pos1 = _pos("A", value=10_000.0)
        pos2 = _pos("B", value=10_000.0)
        pos2["yield_on_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[pos1, pos2])
        mock_reader.get_features = AsyncMock(
            return_value={
                "A": _feat("A", yield_forward=5.0),
                "B": _feat("B", yield_forward=None, yield_trailing=None),
            }
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.positions_included == 1
        assert result.positions_missing_data == 1

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_zero_value_position_does_not_raise(self, mock_reader):
        mock_reader.get_positions = AsyncMock(
            return_value=[_pos("O", value=0.0, yield_on_value=5.0)]
        )
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=5.0)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.total_projected_annual == 0.0

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_none_current_value_treated_as_zero(self, mock_reader):
        pos = _pos("O", value=10_000.0)
        pos["current_value"] = None
        mock_reader.get_positions = AsyncMock(return_value=[pos])
        mock_reader.get_features = AsyncMock(
            return_value={"O": _feat("O", yield_forward=5.0)}
        )
        result = await run_projection("pid-1", yield_source="forward")
        assert result.total_projected_annual == 0.0

    @pytest.mark.anyio
    @patch("app.projector.engine.portfolio_reader")
    async def test_large_portfolio_sums_correctly(self, mock_reader):
        # 10 positions each $100k at 5% = $50k total
        positions = [_pos(f"S{i}", value=100_000.0) for i in range(10)]
        features = {
            f"S{i}": _feat(f"S{i}", yield_forward=5.0) for i in range(10)
        }
        mock_reader.get_positions = AsyncMock(return_value=positions)
        mock_reader.get_features = AsyncMock(return_value=features)
        result = await run_projection("pid-1", yield_source="forward")
        assert result.total_projected_annual == pytest.approx(50_000.0, rel=1e-3)
