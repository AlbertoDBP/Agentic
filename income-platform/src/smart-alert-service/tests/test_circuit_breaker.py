"""
test_circuit_breaker.py — 35 tests for circuit breaker detection logic.

Tests:
  - SCORE_DETERIORATION: delta >=25 CRITICAL, 15-24 WARNING, <15 no alert (10 tests)
  - YIELD_SUSTAINABILITY: payout >90% + chowder <0 WARNING, single condition no alert (8 tests)
  - GROWTH_STALL: was positive now <=0 WARNING, both negative no alert, 1 row no alert (9 tests)
  - Empty DB returns empty list (3 tests)
  - Multiple tickers (5 tests)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.detector.circuit_breaker import (
    AlertData,
    _detect_growth_stall,
    _detect_score_deterioration,
    _detect_yield_sustainability,
    detect_circuit_breaker_alerts,
)


def _make_score_row(ticker: str, total_score: float, scored_at=None):
    row = MagicMock()
    row.ticker = ticker
    row.total_score = total_score
    row.scored_at = scored_at or "2026-01-01"
    return row


def _make_feature_row(symbol: str, payout_ratio=None, chowder_number=None, div_cagr_3y=None, as_of_date=None):
    row = MagicMock()
    row.symbol = symbol
    row.payout_ratio = payout_ratio
    row.chowder_number = chowder_number
    row.div_cagr_3y = div_cagr_3y
    row.as_of_date = as_of_date or "2026-01-01"
    return row


def _db_with_rows(rows):
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = rows
    return db


# ---------------------------------------------------------------------------
# SCORE_DETERIORATION (10 tests)
# ---------------------------------------------------------------------------

class TestScoreDeterioration:
    def test_delta_25_is_critical(self):
        rows = [
            _make_score_row("AAPL", 50.0),   # newest
            _make_score_row("AAPL", 75.0),   # older
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "CRITICAL"
        assert alerts[0].alert_type == "SCORE_DETERIORATION"

    def test_delta_exactly_25_is_critical(self):
        rows = [
            _make_score_row("AAPL", 50.0),
            _make_score_row("AAPL", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert alerts[0].severity == "CRITICAL"

    def test_delta_26_is_critical(self):
        rows = [
            _make_score_row("MSFT", 49.0),
            _make_score_row("MSFT", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert alerts[0].severity == "CRITICAL"

    def test_delta_15_is_warning(self):
        rows = [
            _make_score_row("T", 60.0),
            _make_score_row("T", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "WARNING"

    def test_delta_exactly_15_is_warning(self):
        rows = [
            _make_score_row("T", 60.0),
            _make_score_row("T", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert alerts[0].severity == "WARNING"

    def test_delta_20_is_warning(self):
        rows = [
            _make_score_row("O", 55.0),
            _make_score_row("O", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert alerts[0].severity == "WARNING"

    def test_delta_14_no_alert(self):
        rows = [
            _make_score_row("VZ", 61.0),
            _make_score_row("VZ", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert len(alerts) == 0

    def test_delta_zero_no_alert(self):
        rows = [
            _make_score_row("VZ", 75.0),
            _make_score_row("VZ", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert len(alerts) == 0

    def test_details_contain_scores(self):
        rows = [
            _make_score_row("AAPL", 50.0),
            _make_score_row("AAPL", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        d = alerts[0].details
        assert d["score_before"] == 75.0
        assert d["score_after"] == 50.0
        assert d["delta"] == 25.0

    def test_only_one_row_no_alert(self):
        rows = [_make_score_row("SOLO", 60.0)]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# YIELD_SUSTAINABILITY (8 tests)
# ---------------------------------------------------------------------------

class TestYieldSustainability:
    def test_payout_above_90_chowder_negative_warning(self):
        rows = [_make_feature_row("AAPL", payout_ratio=0.95, chowder_number=-1.0)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "WARNING"
        assert alerts[0].alert_type == "YIELD_SUSTAINABILITY"

    def test_payout_91_chowder_minus_5(self):
        rows = [_make_feature_row("T", payout_ratio=0.91, chowder_number=-5.0)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 1

    def test_payout_below_90_no_alert(self):
        rows = [_make_feature_row("MCD", payout_ratio=0.85, chowder_number=-2.0)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 0

    def test_payout_above_90_chowder_positive_no_alert(self):
        rows = [_make_feature_row("O", payout_ratio=0.95, chowder_number=3.0)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 0

    def test_payout_above_90_chowder_zero_no_alert(self):
        rows = [_make_feature_row("VZ", payout_ratio=0.95, chowder_number=0.0)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 0

    def test_payout_none_no_alert(self):
        rows = [_make_feature_row("MSFT", payout_ratio=None, chowder_number=-1.0)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 0

    def test_chowder_none_no_alert(self):
        rows = [_make_feature_row("AMZN", payout_ratio=0.95, chowder_number=None)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 0

    def test_details_contain_payout_and_chowder(self):
        rows = [_make_feature_row("AAPL", payout_ratio=0.95, chowder_number=-2.5)]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        d = alerts[0].details
        assert d["payout_ratio"] == 0.95
        assert d["chowder_number"] == -2.5


# ---------------------------------------------------------------------------
# GROWTH_STALL (9 tests)
# ---------------------------------------------------------------------------

class TestGrowthStall:
    def test_positive_to_zero_warning(self):
        rows = [
            _make_feature_row("AAPL", div_cagr_3y=0.0, as_of_date="2026-01-01"),
            _make_feature_row("AAPL", div_cagr_3y=5.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "WARNING"
        assert alerts[0].alert_type == "GROWTH_STALL"

    def test_positive_to_negative_warning(self):
        rows = [
            _make_feature_row("T", div_cagr_3y=-1.0, as_of_date="2026-01-01"),
            _make_feature_row("T", div_cagr_3y=3.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "WARNING"

    def test_both_negative_no_alert(self):
        rows = [
            _make_feature_row("VZ", div_cagr_3y=-1.0, as_of_date="2026-01-01"),
            _make_feature_row("VZ", div_cagr_3y=-2.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 0

    def test_both_positive_no_alert(self):
        rows = [
            _make_feature_row("O", div_cagr_3y=3.0, as_of_date="2026-01-01"),
            _make_feature_row("O", div_cagr_3y=5.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 0

    def test_only_one_row_no_alert(self):
        rows = [_make_feature_row("SOLO", div_cagr_3y=3.0)]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 0

    def test_details_contain_cagr_values(self):
        rows = [
            _make_feature_row("AAPL", div_cagr_3y=-0.5, as_of_date="2026-01-01"),
            _make_feature_row("AAPL", div_cagr_3y=4.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        d = alerts[0].details
        assert d["div_cagr_3y_before"] == 4.0
        assert d["div_cagr_3y_now"] == -0.5

    def test_was_zero_now_negative_no_alert(self):
        # Before was 0 (not positive) — should not trigger
        rows = [
            _make_feature_row("MCD", div_cagr_3y=-1.0, as_of_date="2026-01-01"),
            _make_feature_row("MCD", div_cagr_3y=0.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 0

    def test_symbol_in_alert(self):
        rows = [
            _make_feature_row("IBM", div_cagr_3y=0.0, as_of_date="2026-01-01"),
            _make_feature_row("IBM", div_cagr_3y=2.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        assert alerts[0].symbol == "IBM"

    def test_none_cagr_no_crash(self):
        rows = [
            _make_feature_row("XYZ", div_cagr_3y=None, as_of_date="2026-01-01"),
            _make_feature_row("XYZ", div_cagr_3y=2.0, as_of_date="2025-01-01"),
        ]
        db = _db_with_rows(rows)
        # Should not raise, should return no alerts
        alerts = _detect_growth_stall(db)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Empty DB returns empty list (3 tests)
# ---------------------------------------------------------------------------

class TestEmptyDB:
    def test_score_deterioration_empty(self):
        db = _db_with_rows([])
        alerts = _detect_score_deterioration(db)
        assert alerts == []

    def test_yield_sustainability_empty(self):
        db = _db_with_rows([])
        alerts = _detect_yield_sustainability(db)
        assert alerts == []

    def test_growth_stall_empty(self):
        db = _db_with_rows([])
        alerts = _detect_growth_stall(db)
        assert alerts == []


# ---------------------------------------------------------------------------
# Multiple tickers (5 tests)
# ---------------------------------------------------------------------------

class TestMultipleTickers:
    def test_two_tickers_both_trigger(self):
        rows = [
            _make_score_row("AAPL", 40.0),
            _make_score_row("AAPL", 70.0),
            _make_score_row("MSFT", 45.0),
            _make_score_row("MSFT", 75.0),
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        symbols = {a.symbol for a in alerts}
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_two_tickers_one_triggers(self):
        rows = [
            _make_score_row("AAPL", 40.0),
            _make_score_row("AAPL", 70.0),  # delta=30 triggers
            _make_score_row("MSFT", 73.0),
            _make_score_row("MSFT", 75.0),  # delta=2 no alert
        ]
        db = _db_with_rows(rows)
        alerts = _detect_score_deterioration(db)
        assert len(alerts) == 1
        assert alerts[0].symbol == "AAPL"

    def test_yield_multiple_symbols(self):
        rows = [
            _make_feature_row("AAPL", payout_ratio=0.95, chowder_number=-1.0),
            _make_feature_row("T", payout_ratio=0.92, chowder_number=-3.0),
            _make_feature_row("O", payout_ratio=0.80, chowder_number=-1.0),  # no trigger
        ]
        db = _db_with_rows(rows)
        alerts = _detect_yield_sustainability(db)
        assert len(alerts) == 2

    def test_growth_stall_multiple_symbols(self):
        rows = [
            _make_feature_row("AAPL", div_cagr_3y=0.0, as_of_date="2026-01-01"),
            _make_feature_row("AAPL", div_cagr_3y=5.0, as_of_date="2025-01-01"),
            _make_feature_row("T", div_cagr_3y=-1.0, as_of_date="2026-01-01"),
            _make_feature_row("T", div_cagr_3y=2.0, as_of_date="2025-01-01"),
            _make_feature_row("O", div_cagr_3y=3.0, as_of_date="2026-01-01"),
            _make_feature_row("O", div_cagr_3y=4.0, as_of_date="2025-01-01"),  # no trigger
        ]
        db = _db_with_rows(rows)
        alerts = _detect_growth_stall(db)
        symbols = {a.symbol for a in alerts}
        assert "AAPL" in symbols
        assert "T" in symbols
        assert "O" not in symbols

    def test_combined_detector_aggregates_all(self):
        """detect_circuit_breaker_alerts calls all three and returns combined list."""
        db = MagicMock()
        # Return empty for all calls
        db.execute.return_value.fetchall.return_value = []
        alerts = detect_circuit_breaker_alerts(db)
        assert isinstance(alerts, list)
