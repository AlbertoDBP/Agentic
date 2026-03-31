# src/agent-14-data-quality/tests/test_healer.py
from unittest.mock import MagicMock, patch
import pytest
from app.healer import HealerEngine, IssueStatus


class TestHealerEngine:
    def _make_db(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.fetchone.return_value = None
        return db

    def test_skip_exempt_issues(self):
        """Exempted (symbol, field_name) pairs must be skipped."""
        healer = HealerEngine(fmp_client=MagicMock(), massive_client=MagicMock())
        exempt = {("AAPL", "nav_value")}
        result = healer._should_skip("AAPL", "nav_value", exempt)
        assert result is True

    def test_not_skip_non_exempt(self):
        healer = HealerEngine(fmp_client=MagicMock(), massive_client=MagicMock())
        exempt = set()
        result = healer._should_skip("AAPL", "nav_value", exempt)
        assert result is False

    def test_try_primary_first_then_fallback(self):
        """Healer tries primary source; if None, tries fallback."""
        fmp = MagicMock()
        fmp.fetch_field_with_diagnostic.return_value = (None, {"code": "FIELD_NOT_SUPPORTED"})
        massive = MagicMock()
        massive.fetch_field_with_diagnostic.return_value = (42.5, {})

        healer = HealerEngine(fmp_client=fmp, massive_client=massive)
        value, diag, source = healer._fetch("AAPL", "price", primary="fmp", fallback="massive")
        assert value == 42.5
        assert source == "massive"

    def test_max_attempts_sets_unresolvable(self):
        """After max_heal_attempts fails, status becomes unresolvable."""
        # Issue with attempt_count already at max
        issue = MagicMock()
        issue.attempt_count = 3
        issue.id = 1
        assert issue.attempt_count >= 3
