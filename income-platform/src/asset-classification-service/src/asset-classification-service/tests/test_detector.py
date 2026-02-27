"""
Tests for shared/asset_class_detector — Rule Matcher + Detector
Target: 50+ tests covering all 7 asset classes, boundaries, fallback
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from shared.asset_class_detector import AssetClassDetector
from shared.asset_class_detector.taxonomy import AssetClass
from shared.asset_class_detector.rule_matcher import RuleMatcher
from shared.asset_class_detector.seed_rules import SEED_RULES


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

@pytest.fixture
def detector():
    return AssetClassDetector()


# ─────────────────────────────────────────
# COVERED_CALL_ETF — known ticker list
# ─────────────────────────────────────────

class TestCoveredCallETF:
    def test_jepi_by_ticker(self, detector):
        r = detector.detect("JEPI")
        assert r.asset_class == AssetClass.COVERED_CALL_ETF
        assert r.confidence >= 0.90

    def test_jepq_by_ticker(self, detector):
        r = detector.detect("JEPQ")
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_qyld_by_ticker(self, detector):
        r = detector.detect("QYLD")
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_xyld_by_ticker(self, detector):
        r = detector.detect("XYLD")
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_by_metadata_strategy(self, detector):
        r = detector.detect("XYZ", {"strategy": "Covered Call"})
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_by_feature_flags(self, detector):
        r = detector.detect("XYZ", {"options_strategy_present": True, "is_etf": True})
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_nav_erosion_tracking_in_characteristics(self, detector):
        r = detector.detect("JEPI")
        assert r.characteristics["nav_erosion_tracking"] is True

    def test_preferred_account_ira(self, detector):
        r = detector.detect("JEPI")
        assert r.characteristics["preferred_account"] == "IRA"

    def test_income_type_option_premium(self, detector):
        r = detector.detect("JEPI")
        assert r.characteristics["income_type"] == "option_premium"

    def test_tax_treatment_ordinary(self, detector):
        r = detector.detect("JEPI")
        assert r.characteristics["tax_treatment"] == "ordinary"


# ─────────────────────────────────────────
# PREFERRED_STOCK — suffix patterns
# ─────────────────────────────────────────

class TestPreferredStock:
    def test_pa_suffix(self, detector):
        r = detector.detect("BAC-PA")
        assert r.asset_class == AssetClass.PREFERRED_STOCK

    def test_pb_suffix(self, detector):
        r = detector.detect("JPM-PB")
        assert r.asset_class == AssetClass.PREFERRED_STOCK

    def test_pc_suffix(self, detector):
        r = detector.detect("WFC-PC")
        assert r.asset_class == AssetClass.PREFERRED_STOCK

    def test_metadata_preferred_stock(self, detector):
        r = detector.detect("XYZ", {"security_type": "Preferred Stock"})
        assert r.asset_class == AssetClass.PREFERRED_STOCK

    def test_preferred_tax_treatment_qualified(self, detector):
        r = detector.detect("BAC-PA")
        assert r.characteristics["tax_treatment"] == "qualified"

    def test_preferred_income_type_fixed(self, detector):
        r = detector.detect("BAC-PA")
        assert r.characteristics["income_type"] == "fixed_dividend"


# ─────────────────────────────────────────
# MORTGAGE_REIT — known tickers
# ─────────────────────────────────────────

class TestMortgageREIT:
    def test_agnc_by_ticker(self, detector):
        r = detector.detect("AGNC")
        assert r.asset_class == AssetClass.MORTGAGE_REIT

    def test_nly_by_ticker(self, detector):
        r = detector.detect("NLY")
        assert r.asset_class == AssetClass.MORTGAGE_REIT

    def test_ritm_by_ticker(self, detector):
        r = detector.detect("RITM")
        assert r.asset_class == AssetClass.MORTGAGE_REIT

    def test_mreit_is_hybrid(self, detector):
        r = detector.detect("AGNC")
        assert r.is_hybrid is True

    def test_mreit_coverage_ratio_required(self, detector):
        r = detector.detect("AGNC")
        assert r.characteristics["coverage_ratio_required"] is True

    def test_mreit_by_metadata(self, detector):
        r = detector.detect("XYZ", {"fund_category": "Mortgage REIT"})
        assert r.asset_class == AssetClass.MORTGAGE_REIT


# ─────────────────────────────────────────
# EQUITY_REIT
# ─────────────────────────────────────────

class TestEquityREIT:
    def test_by_real_estate_sector(self, detector):
        r = detector.detect("O", {"sector": "Real Estate", "security_type": "REIT"})
        assert r.asset_class == AssetClass.EQUITY_REIT

    def test_valuation_method_pffо(self, detector):
        r = detector.detect("O", {"sector": "Real Estate", "security_type": "REIT"})
        assert "FFO" in r.characteristics["valuation_method"]

    def test_preferred_account_ira(self, detector):
        r = detector.detect("O", {"sector": "Real Estate", "security_type": "REIT"})
        assert r.characteristics["preferred_account"] == "IRA"


# ─────────────────────────────────────────
# BDC
# ─────────────────────────────────────────

class TestBDC:
    def test_arcc_by_ticker(self, detector):
        r = detector.detect("ARCC")
        assert r.asset_class == AssetClass.BDC

    def test_main_by_ticker(self, detector):
        r = detector.detect("MAIN")
        assert r.asset_class == AssetClass.BDC

    def test_bdc_by_metadata(self, detector):
        r = detector.detect("XYZ", {"fund_category": "Business Development Company"})
        assert r.asset_class == AssetClass.BDC

    def test_bdc_coverage_ratio_required(self, detector):
        r = detector.detect("ARCC")
        assert r.characteristics["coverage_ratio_required"] is True

    def test_bdc_valuation_pnav(self, detector):
        r = detector.detect("ARCC")
        assert "NAV" in r.characteristics["valuation_method"]


# ─────────────────────────────────────────
# BOND
# ─────────────────────────────────────────

class TestBond:
    def test_agg_by_ticker(self, detector):
        r = detector.detect("AGG")
        assert r.asset_class == AssetClass.BOND

    def test_bnd_by_ticker(self, detector):
        r = detector.detect("BND")
        assert r.asset_class == AssetClass.BOND

    def test_by_maturity_feature(self, detector):
        r = detector.detect("XYZ", {"has_maturity_date": True, "coupon_rate_exists": True})
        assert r.asset_class == AssetClass.BOND

    def test_bond_income_type_interest(self, detector):
        r = detector.detect("AGG")
        assert r.characteristics["income_type"] == "interest"

    def test_bond_preferred_account_ira(self, detector):
        r = detector.detect("AGG")
        assert r.characteristics["preferred_account"] == "IRA"


# ─────────────────────────────────────────
# DIVIDEND_STOCK
# ─────────────────────────────────────────

class TestDividendStock:
    def test_by_common_stock_feature(self, detector):
        r = detector.detect("JNJ", {
            "dividend_yield": 0.03,
            "is_common_stock": True,
            "payout_ratio": 0.50,
            "security_type": "Common Stock",
        })
        assert r.asset_class == AssetClass.DIVIDEND_STOCK

    def test_dividend_stock_tax_qualified(self, detector):
        r = detector.detect("JNJ", {
            "dividend_yield": 0.03,
            "is_common_stock": True,
            "security_type": "Common Stock",
        })
        assert r.characteristics["tax_treatment"] == "qualified"

    def test_dividend_stock_preferred_account_taxable(self, detector):
        r = detector.detect("JNJ", {
            "dividend_yield": 0.03,
            "is_common_stock": True,
            "security_type": "Common Stock",
        })
        assert r.characteristics["preferred_account"] == "TAXABLE"


# ─────────────────────────────────────────
# Fallback and edge cases
# ─────────────────────────────────────────

class TestFallbackAndEdgeCases:
    def test_unknown_ticker_no_data(self, detector):
        r = detector.detect("ZZZZZ")
        assert r.asset_class == AssetClass.UNKNOWN
        assert r.confidence == 0.0

    def test_detect_with_fallback_never_unknown(self, detector):
        r = detector.detect_with_fallback("ZZZZZ")
        assert r.asset_class != AssetClass.UNKNOWN
        assert r.asset_class == AssetClass.DIVIDEND_STOCK

    def test_detect_with_fallback_source_is_fallback(self, detector):
        r = detector.detect_with_fallback("ZZZZZ")
        assert r.source == "fallback"

    def test_none_security_data_handled(self, detector):
        r = detector.detect("JEPI", None)
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_empty_security_data_handled(self, detector):
        r = detector.detect("JEPI", {})
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_result_has_characteristics(self, detector):
        r = detector.detect("JEPI")
        assert "income_type" in r.characteristics
        assert "tax_treatment" in r.characteristics
        assert "valuation_method" in r.characteristics
        assert "preferred_account" in r.characteristics

    def test_result_has_matched_rules(self, detector):
        r = detector.detect("JEPI")
        assert len(r.matched_rules) > 0

    def test_mreit_beats_equity_reit_for_agnc(self, detector):
        """MORTGAGE_REIT should win over EQUITY_REIT for known mREIT tickers."""
        r = detector.detect("AGNC", {"sector": "Real Estate"})
        assert r.asset_class == AssetClass.MORTGAGE_REIT

    def test_covered_call_etf_beats_etf_generic(self, detector):
        """COVERED_CALL_ETF should win for known CC ETF tickers."""
        r = detector.detect("JEPI", {"is_etf": True, "sector": "Financials"})
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_ticker_case_insensitive(self, detector):
        r = detector.detect("jepi")
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_ticker_whitespace_stripped(self, detector):
        r = detector.detect("  JEPI  ")
        assert r.asset_class == AssetClass.COVERED_CALL_ETF

    def test_needs_enrichment_false_for_high_confidence(self, detector):
        r = detector.detect("JEPI")
        assert r.needs_enrichment is False

    def test_needs_enrichment_true_for_unknown(self, detector):
        r = detector.detect("ZZZZZ")
        assert r.needs_enrichment is True


# ─────────────────────────────────────────
# Seed rules completeness
# ─────────────────────────────────────────

class TestSeedRules:
    def test_all_7_classes_have_rules(self):
        classes = {r["asset_class"] for r in SEED_RULES}
        expected = {
            "COVERED_CALL_ETF", "PREFERRED_STOCK", "MORTGAGE_REIT",
            "EQUITY_REIT", "BDC", "BOND", "DIVIDEND_STOCK"
        }
        assert expected == classes

    def test_all_rules_have_required_fields(self):
        for rule in SEED_RULES:
            assert "asset_class" in rule
            assert "rule_type" in rule
            assert "rule_config" in rule
            assert "priority" in rule
            assert "confidence_weight" in rule

    def test_all_confidence_weights_valid(self):
        for rule in SEED_RULES:
            assert 0 < rule["confidence_weight"] <= 1.0

    def test_all_rule_types_valid(self):
        valid = {"ticker_pattern", "sector", "feature", "metadata"}
        for rule in SEED_RULES:
            assert rule["rule_type"] in valid
