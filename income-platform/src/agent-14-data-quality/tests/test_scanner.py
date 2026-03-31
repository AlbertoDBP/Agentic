# src/agent-14-data-quality/tests/test_scanner.py
from unittest.mock import MagicMock, patch
import pytest
from app.scanner import ASSET_TYPE_TO_CLASS, resolve_asset_class, compute_severity


class TestAssetTypeMapping:
    def test_covered_call_etf_maps_to_etf(self):
        assert ASSET_TYPE_TO_CLASS["COVERED_CALL_ETF"] == "ETF"

    def test_equity_reit_maps_to_reit(self):
        assert ASSET_TYPE_TO_CLASS["EQUITY_REIT"] == "REIT"

    def test_mortgage_reit_maps_to_reit(self):
        assert ASSET_TYPE_TO_CLASS["MORTGAGE_REIT"] == "REIT"

    def test_preferred_stock_maps_to_preferred(self):
        assert ASSET_TYPE_TO_CLASS["PREFERRED_STOCK"] == "Preferred"

    def test_unknown_returns_none(self):
        assert ASSET_TYPE_TO_CLASS.get("UNKNOWN") is None


class TestComputeSeverity:
    def test_critical_when_peer_has_field(self):
        """If any peer has the field populated, severity is critical."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 1  # one peer has it
        severity = compute_severity(mock_db, "MAIN", "interest_coverage_ratio", "BDC")
        assert severity == "critical"

    def test_warning_when_no_peer_has_field(self):
        """If no peer has the field, severity is warning."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 0  # no peer has it
        severity = compute_severity(mock_db, "MAIN", "chowder_number", "BDC")
        assert severity == "warning"
