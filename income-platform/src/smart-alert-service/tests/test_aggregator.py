"""
test_aggregator.py — 30 tests for external alert aggregation.

Tests:
  - Agent 07 scan_results (8 tests)
  - Agent 08 rebalancing_results (8 tests)
  - Agent 09 income_projections (5 tests)
  - Agent 10 nav_alerts pass-through (5 tests)
  - All empty tables returns empty list (4 tests)
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from app.detector.aggregator import (
    _aggregate_agent07,
    _aggregate_agent08,
    _aggregate_agent09,
    _aggregate_agent10,
    aggregate_external_alerts,
)


def _db_with_rows(rows):
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = rows
    return db


def _make_scan_row(symbol: str, created_at="2026-01-10"):
    row = MagicMock()
    row.symbol = symbol
    row.created_at = created_at
    return row


def _make_rebalance_row(violations, created_at="2026-01-10"):
    row = MagicMock()
    row.violations = violations
    row.created_at = created_at
    return row


def _make_projection_row(portfolio_id, positions_missing_data, total_projected_annual=100000.0, created_at="2026-01-10"):
    row = MagicMock()
    row.portfolio_id = portfolio_id
    row.positions_missing_data = positions_missing_data
    row.total_projected_annual = total_projected_annual
    row.created_at = created_at
    return row


def _make_nav_row(symbol, alert_type, severity, details=None, created_at="2026-01-10"):
    row = MagicMock()
    row.symbol = symbol
    row.alert_type = alert_type
    row.severity = severity
    row.details = details or {}
    row.created_at = created_at
    return row


# ---------------------------------------------------------------------------
# Agent 07 scan_results (8 tests)
# ---------------------------------------------------------------------------

class TestAgent07:
    def test_veto_flag_creates_alert(self):
        rows = [_make_scan_row("AAPL")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert len(alerts) == 1

    def test_alert_type_is_veto_flag(self):
        rows = [_make_scan_row("AAPL")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert alerts[0].alert_type == "VETO_FLAG"

    def test_source_agent_is_7(self):
        rows = [_make_scan_row("AAPL")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert alerts[0].source_agent == 7

    def test_severity_is_warning(self):
        rows = [_make_scan_row("AAPL")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert alerts[0].severity == "WARNING"

    def test_symbol_preserved(self):
        rows = [_make_scan_row("MSFT")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert alerts[0].symbol == "MSFT"

    def test_multiple_symbols(self):
        rows = [_make_scan_row("AAPL"), _make_scan_row("T"), _make_scan_row("VZ")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert len(alerts) == 3

    def test_empty_returns_empty(self):
        db = _db_with_rows([])
        alerts = _aggregate_agent07(db)
        assert alerts == []

    def test_details_contains_created_at(self):
        rows = [_make_scan_row("AAPL", created_at="2026-01-10")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent07(db)
        assert "created_at" in alerts[0].details


# ---------------------------------------------------------------------------
# Agent 08 rebalancing_results (8 tests)
# ---------------------------------------------------------------------------

class TestAgent08:
    def test_veto_violation_creates_critical(self):
        violations = [{"violation_type": "VETO", "symbol": "AAPL"}]
        rows = [_make_rebalance_row(violations)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "CRITICAL"

    def test_below_grade_violation_creates_warning(self):
        violations = [{"violation_type": "BELOW_GRADE", "symbol": "T"}]
        rows = [_make_rebalance_row(violations)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "WARNING"

    def test_alert_type_is_rebalance_violation(self):
        violations = [{"violation_type": "VETO", "symbol": "MSFT"}]
        rows = [_make_rebalance_row(violations)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert alerts[0].alert_type == "REBALANCE_VIOLATION"

    def test_source_agent_is_8(self):
        violations = [{"violation_type": "VETO", "symbol": "MSFT"}]
        rows = [_make_rebalance_row(violations)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert alerts[0].source_agent == 8

    def test_unknown_violation_type_skipped(self):
        violations = [{"violation_type": "OTHER", "symbol": "XYZ"}]
        rows = [_make_rebalance_row(violations)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert len(alerts) == 0

    def test_multiple_violations_in_one_row(self):
        violations = [
            {"violation_type": "VETO", "symbol": "AAPL"},
            {"violation_type": "BELOW_GRADE", "symbol": "T"},
        ]
        rows = [_make_rebalance_row(violations)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert len(alerts) == 2

    def test_empty_violations_skipped(self):
        rows = [_make_rebalance_row(None)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent08(db)
        assert len(alerts) == 0

    def test_empty_returns_empty(self):
        db = _db_with_rows([])
        alerts = _aggregate_agent08(db)
        assert alerts == []


# ---------------------------------------------------------------------------
# Agent 09 income_projections (5 tests)
# ---------------------------------------------------------------------------

class TestAgent09:
    def test_missing_data_creates_info_alert(self):
        rows = [_make_projection_row("port-123", positions_missing_data=3)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent09(db)
        assert len(alerts) == 1
        assert alerts[0].severity == "INFO"

    def test_alert_type_is_projection_data_gap(self):
        rows = [_make_projection_row("port-456", positions_missing_data=1)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent09(db)
        assert alerts[0].alert_type == "PROJECTION_DATA_GAP"

    def test_source_agent_is_9(self):
        rows = [_make_projection_row("port-789", positions_missing_data=2)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent09(db)
        assert alerts[0].source_agent == 9

    def test_symbol_is_portfolio_id_as_string(self):
        rows = [_make_projection_row("port-abc", positions_missing_data=1)]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent09(db)
        assert alerts[0].symbol == "port-abc"

    def test_empty_returns_empty(self):
        db = _db_with_rows([])
        alerts = _aggregate_agent09(db)
        assert alerts == []


# ---------------------------------------------------------------------------
# Agent 10 nav_alerts pass-through (5 tests)
# ---------------------------------------------------------------------------

class TestAgent10:
    def test_unresolved_alert_passed_through(self):
        rows = [_make_nav_row("AAPL", "NAV_EROSION", "WARNING")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent10(db)
        assert len(alerts) == 1

    def test_source_agent_is_10(self):
        rows = [_make_nav_row("AAPL", "NAV_EROSION", "WARNING")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent10(db)
        assert alerts[0].source_agent == 10

    def test_alert_type_preserved(self):
        rows = [_make_nav_row("MSFT", "SCORE_DIVERGENCE", "CRITICAL")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent10(db)
        assert alerts[0].alert_type == "SCORE_DIVERGENCE"

    def test_severity_preserved(self):
        rows = [_make_nav_row("T", "NAV_EROSION", "CRITICAL")]
        db = _db_with_rows(rows)
        alerts = _aggregate_agent10(db)
        assert alerts[0].severity == "CRITICAL"

    def test_empty_returns_empty(self):
        db = _db_with_rows([])
        alerts = _aggregate_agent10(db)
        assert alerts == []


# ---------------------------------------------------------------------------
# All empty tables returns empty list (4 tests)
# ---------------------------------------------------------------------------

class TestAllEmpty:
    def test_agent07_empty(self):
        db = _db_with_rows([])
        assert _aggregate_agent07(db) == []

    def test_agent08_empty(self):
        db = _db_with_rows([])
        assert _aggregate_agent08(db) == []

    def test_agent09_empty(self):
        db = _db_with_rows([])
        assert _aggregate_agent09(db) == []

    def test_combined_empty_all_empty(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        alerts = aggregate_external_alerts(db)
        assert alerts == []
