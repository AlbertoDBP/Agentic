"""
Tests for classification/tax_profile.py
Target: 22 tests — all 7 asset classes, tax drag values, preferred accounts, notes.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from app.classification.tax_profile import (
    build_tax_profile,
    TAX_DRAG_BY_INCOME_TYPE,
    TaxEfficiency,
)

TAX_PROFILE_KEYS = {
    "income_type",
    "tax_treatment",
    "estimated_tax_drag_pct",
    "preferred_account",
    "notes",
}

# Characteristics matching what the detector sets for each class
CHAR_BY_CLASS = {
    "COVERED_CALL_ETF": {
        "income_type": "option_premium",
        "tax_treatment": "ordinary",
        "preferred_account": "IRA",
    },
    "DIVIDEND_STOCK": {
        "income_type": "qualified_dividend",
        "tax_treatment": "qualified",
        "preferred_account": "TAXABLE",
    },
    "EQUITY_REIT": {
        "income_type": "reit_distribution",
        "tax_treatment": "ordinary",
        "preferred_account": "IRA",
    },
    "MORTGAGE_REIT": {
        "income_type": "reit_distribution",
        "tax_treatment": "ordinary",
        "preferred_account": "IRA",
    },
    "BDC": {
        "income_type": "ordinary_dividend",
        "tax_treatment": "ordinary",
        "preferred_account": "IRA",
    },
    "BOND": {
        "income_type": "interest",
        "tax_treatment": "ordinary",
        "preferred_account": "IRA",
    },
    "PREFERRED_STOCK": {
        "income_type": "fixed_dividend",
        "tax_treatment": "qualified",
        "preferred_account": "TAXABLE",
    },
}


# ── Output structure ────────────────────────────────────────────────────────

class TestTaxProfileStructure:
    @pytest.mark.parametrize("asset_class", CHAR_BY_CLASS.keys())
    def test_returns_dict_with_all_keys(self, asset_class):
        result = build_tax_profile(asset_class, CHAR_BY_CLASS[asset_class])
        assert TAX_PROFILE_KEYS == set(result.keys())

    @pytest.mark.parametrize("asset_class", CHAR_BY_CLASS.keys())
    def test_income_type_preserved(self, asset_class):
        chars = CHAR_BY_CLASS[asset_class]
        result = build_tax_profile(asset_class, chars)
        assert result["income_type"] == chars["income_type"]

    @pytest.mark.parametrize("asset_class", CHAR_BY_CLASS.keys())
    def test_preferred_account_preserved(self, asset_class):
        chars = CHAR_BY_CLASS[asset_class]
        result = build_tax_profile(asset_class, chars)
        assert result["preferred_account"] == chars["preferred_account"]

    @pytest.mark.parametrize("asset_class", CHAR_BY_CLASS.keys())
    def test_estimated_tax_drag_is_float(self, asset_class):
        result = build_tax_profile(asset_class, CHAR_BY_CLASS[asset_class])
        assert isinstance(result["estimated_tax_drag_pct"], float)

    @pytest.mark.parametrize("asset_class", CHAR_BY_CLASS.keys())
    def test_notes_not_empty(self, asset_class):
        result = build_tax_profile(asset_class, CHAR_BY_CLASS[asset_class])
        assert result["notes"] and len(result["notes"]) > 10


# ── Tax drag correctness ────────────────────────────────────────────────────

class TestTaxDrag:
    def test_qualified_dividend_15pct(self):
        result = build_tax_profile("DIVIDEND_STOCK", CHAR_BY_CLASS["DIVIDEND_STOCK"])
        assert result["estimated_tax_drag_pct"] == 15.0

    def test_option_premium_37pct(self):
        result = build_tax_profile("COVERED_CALL_ETF", CHAR_BY_CLASS["COVERED_CALL_ETF"])
        assert result["estimated_tax_drag_pct"] == 37.0

    def test_interest_37pct(self):
        result = build_tax_profile("BOND", CHAR_BY_CLASS["BOND"])
        assert result["estimated_tax_drag_pct"] == 37.0

    def test_roc_0pct(self):
        chars = {"income_type": "roc", "tax_treatment": "deferred", "preferred_account": "TAXABLE"}
        result = build_tax_profile("COVERED_CALL_ETF", chars)
        assert result["estimated_tax_drag_pct"] == 0.0

    def test_unknown_income_type_defaults_37pct(self):
        chars = {"income_type": "mystery_income", "tax_treatment": "unknown", "preferred_account": "TAXABLE"}
        result = build_tax_profile("DIVIDEND_STOCK", chars)
        assert result["estimated_tax_drag_pct"] == 37.0

    def test_fixed_dividend_preferred_stock_15pct(self):
        result = build_tax_profile("PREFERRED_STOCK", CHAR_BY_CLASS["PREFERRED_STOCK"])
        assert result["estimated_tax_drag_pct"] == 15.0


# ── Notes content ───────────────────────────────────────────────────────────

class TestTaxNotes:
    def test_covered_call_etf_mentions_ira(self):
        result = build_tax_profile("COVERED_CALL_ETF", CHAR_BY_CLASS["COVERED_CALL_ETF"])
        assert "IRA" in result["notes"] or "ira" in result["notes"].lower()

    def test_bond_mentions_ira(self):
        result = build_tax_profile("BOND", CHAR_BY_CLASS["BOND"])
        assert "IRA" in result["notes"]

    def test_dividend_stock_mentions_qualified(self):
        result = build_tax_profile("DIVIDEND_STOCK", CHAR_BY_CLASS["DIVIDEND_STOCK"])
        assert "qualified" in result["notes"].lower()

    def test_unknown_class_fallback_notes(self):
        chars = {"income_type": "unknown", "tax_treatment": "unknown", "preferred_account": "TAXABLE"}
        result = build_tax_profile("EXOTIC_CLASS", chars)
        assert "Agent 05" in result["notes"]


# ── TAX_DRAG_BY_INCOME_TYPE completeness ────────────────────────────────────

class TestTaxDragTable:
    def test_all_income_types_present(self):
        expected = {
            "qualified_dividend", "option_premium", "interest",
            "reit_distribution", "ordinary_dividend", "fixed_dividend",
            "roc", "unknown",
        }
        assert expected.issubset(set(TAX_DRAG_BY_INCOME_TYPE.keys()))

    def test_roc_zero(self):
        assert TAX_DRAG_BY_INCOME_TYPE["roc"] == 0.00

    def test_qualified_dividend_lower_than_ordinary(self):
        assert TAX_DRAG_BY_INCOME_TYPE["qualified_dividend"] < TAX_DRAG_BY_INCOME_TYPE["ordinary_dividend"]
