# src/opportunity-scanner-service/tests/test_analyst_ideas.py
"""Agent 07 — Analyst ideas scan mode tests"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestAnalystIdeasReader:
    def test_fetch_active_suggestions_returns_list(self):
        from app.scanner.analyst_ideas import fetch_active_suggestions
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("ARCC", "BDC", "BUY", 0.75, 1, "John Smith", 0.72,
             '{"BDC": 0.18}', "none", None, 0.85,
             datetime(2026, 3, 26, tzinfo=timezone.utc),
             datetime(2026, 5, 10, tzinfo=timezone.utc), 10)
        ]
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
        call_args = mock_conn.execute.call_args
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
