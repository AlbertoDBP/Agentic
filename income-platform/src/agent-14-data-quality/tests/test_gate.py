# src/agent-14-data-quality/tests/test_gate.py
from unittest.mock import MagicMock
import pytest
from app.gate import evaluate_gate, GateResult


class TestGateEvaluator:
    def test_gate_passes_with_no_critical_issues(self):
        db = MagicMock()
        mock_execute = MagicMock()
        db.execute.return_value = mock_execute
        mock_execute.fetchall.return_value = [
            MagicMock(symbol="AAPL"), MagicMock(symbol="JNK")
        ]
        mock_execute.scalar.return_value = 0
        result = evaluate_gate(db, "portfolio-uuid-123")
        assert result.status == "passed"
        assert result.blocking_issue_count == 0

    def test_gate_blocked_with_critical_issues(self):
        db = MagicMock()
        mock_execute = MagicMock()
        db.execute.return_value = mock_execute
        mock_execute.fetchall.return_value = [
            MagicMock(symbol="ARCC")
        ]
        mock_execute.scalar.return_value = 1
        result = evaluate_gate(db, "portfolio-uuid-456")
        assert result.status == "blocked"
        assert result.blocking_issue_count >= 1
