# src/opportunity-scanner-service/tests/test_analyst_ideas.py
"""Agent 07 — Analyst ideas scan mode tests"""
from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest


@pytest.fixture
def mock_conn():
    return MagicMock()


class TestAnalystIdeasReader:
    def test_fetch_active_suggestions_returns_list(self):
        from app.scanner.analyst_ideas import fetch_active_suggestions
        mock_conn = MagicMock()
        suggestion_row = (
            "ARCC", "BDC", "BUY", 0.75, 1, "John Smith", 0.72,
            '{"BDC": 0.18}', "none", None, 0.85,
            datetime(2026, 3, 26, tzinfo=timezone.utc),
            datetime(2026, 5, 10, tzinfo=timezone.utc), 10, True
        )
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.fetchall.return_value = [suggestion_row]
            else:
                result.fetchall.return_value = []
            call_count += 1
            return result

        mock_conn.execute.side_effect = side_effect
        result = fetch_active_suggestions(mock_conn)
        assert isinstance(result, list)
        assert result[0]["ticker"] == "ARCC"
        assert result[0]["analyst_name"] == "John Smith"

    def test_fetch_active_suggestions_returns_empty_on_no_rows(self):
        from app.scanner.analyst_ideas import fetch_active_suggestions
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        result = fetch_active_suggestions(mock_conn)
        assert result == []

    def test_fetch_active_suggestions_applies_staleness_filter(self):
        from app.scanner.analyst_ideas import fetch_active_suggestions
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        fetch_active_suggestions(mock_conn, min_staleness_weight=0.5)
        call_args = mock_conn.execute.call_args_list[0]
        # The SQL query should reference staleness_weight
        assert "staleness_weight" in str(call_args)

    def test_build_analyst_context_dict(self):
        from app.scanner.analyst_ideas import build_analyst_context
        row = {
            "ticker": "ARCC",
            "analyst_id": 1,
            "analyst_name": "John Smith",
            "analyst_accuracy": 0.72,
            "analyst_sector_alpha": {"BDC": 0.18},
            "price_guidance_type": "implied_yield",
            "price_guidance_value": {"value": 0.085},
        }
        ctx = build_analyst_context(row)
        assert ctx["analyst_name"] == "John Smith"
        assert ctx["price_guidance_type"] == "implied_yield"


def test_fetch_active_suggestions_include_history(mock_conn):
    """When include_history=True, WHERE clause omits is_active filter."""
    from app.scanner.analyst_ideas import fetch_active_suggestions
    mock_conn.execute.return_value.fetchall.side_effect = [[], []]
    fetch_active_suggestions(mock_conn, include_history=True)
    # The SQL executed should NOT contain 'is_active = TRUE'
    first_call_sql = str(mock_conn.execute.call_args_list[0][0][0])
    assert "is_active = TRUE" not in first_call_sql


def test_fetch_active_suggestions_default_excludes_history(mock_conn):
    """Default call (include_history=False) filters to is_active=TRUE only."""
    from app.scanner.analyst_ideas import fetch_active_suggestions
    mock_conn.execute.return_value.fetchall.side_effect = [[], []]
    fetch_active_suggestions(mock_conn, include_history=False)
    first_call_sql = str(mock_conn.execute.call_args_list[0][0][0])
    assert "is_active = TRUE" in first_call_sql


def test_build_analyst_context_includes_new_fields():
    """build_analyst_context includes is_active, is_proposed, proposed_at."""
    from app.scanner.analyst_ideas import build_analyst_context
    row = {
        "analyst_id": 1, "analyst_name": "Brad", "analyst_accuracy": 0.7,
        "analyst_sector_alpha": {}, "price_guidance_type": None,
        "price_guidance_value": None, "staleness_weight": 0.8,
        "sourced_at": "2026-03-01", "recommendation": "BUY",
        "is_active": True, "is_proposed": True, "proposed_at": "2026-03-10",
    }
    ctx = build_analyst_context(row)
    assert ctx["is_active"] is True
    assert ctx["is_proposed"] is True
    assert ctx["proposed_at"] == "2026-03-10"


def test_fetch_active_suggestions_sets_is_proposed_flag(mock_conn):
    """Suggestions for tickers appearing in proposal_drafts get is_proposed=True."""
    from app.scanner.analyst_ideas import fetch_active_suggestions
    from unittest.mock import MagicMock

    suggestion_row = (
        "ARCC", "BDC", "BUY", 0.9, 1, "Brad", 0.72, {},
        None, None, 0.85, "2026-03-01", "2026-04-15", 42, True
    )

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            result.fetchall.return_value = [suggestion_row]
        else:
            result.fetchall.return_value = [("ARCC", "2026-03-10")]
        call_count += 1
        return result

    mock_conn.execute.side_effect = side_effect
    results = fetch_active_suggestions(mock_conn)
    assert results[0]["is_proposed"] is True
    assert results[0]["proposed_at"] == "2026-03-10"
