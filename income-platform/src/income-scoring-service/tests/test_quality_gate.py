"""
Agent 03 — Income Scoring Service
Tests: Quality Gate Engine — Phase 1

Coverage targets: 85%+
Tests: 45+ cases covering all asset classes, edge cases, boundary conditions.

Run:
    pytest tests/test_quality_gate.py -v
    pytest tests/test_quality_gate.py -v --tb=short --cov=app/scoring
"""
import pytest
from datetime import datetime

from app.scoring.quality_gate import (
    QualityGateEngine,
    AssetClass,
    GateStatus,
    DividendStockGateInput,
    CoveredCallETFGateInput,
    BondGateInput,
    GateResult,
    credit_rating_meets_minimum,
    CREDIT_RATING_ORDER,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    return QualityGateEngine()


@pytest.fixture
def passing_dividend_stock():
    return DividendStockGateInput(
        ticker="JNJ",
        credit_rating="AAA",
        consecutive_positive_fcf_years=20,
        dividend_history_years=60,
    )


@pytest.fixture
def passing_etf():
    return CoveredCallETFGateInput(
        ticker="JEPI",
        aum_millions=18_000,
        track_record_years=4.5,
        distribution_history_months=54,
    )


@pytest.fixture
def passing_bond():
    return BondGateInput(
        ticker="TLT",
        credit_rating="AAA",
        duration_years=16.5,   # ← will FAIL (>15y)
        issuer_type="GOVERNMENT",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# credit_rating_meets_minimum
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreditRatingHelper:

    def test_aaa_passes(self):
        assert credit_rating_meets_minimum("AAA") is True

    def test_bbb_minus_passes(self):
        assert credit_rating_meets_minimum("BBB-") is True

    def test_bb_plus_fails(self):
        assert credit_rating_meets_minimum("BB+") is False

    def test_d_fails(self):
        assert credit_rating_meets_minimum("D") is False

    def test_case_insensitive(self):
        assert credit_rating_meets_minimum("bbb-") is True
        assert credit_rating_meets_minimum("BBB-") is True
        assert credit_rating_meets_minimum("Bbb-") is True

    def test_with_whitespace(self):
        assert credit_rating_meets_minimum("  BBB-  ") is True

    def test_none_returns_false(self):
        assert credit_rating_meets_minimum(None) is False

    def test_empty_string_returns_false(self):
        assert credit_rating_meets_minimum("") is False

    def test_unknown_rating_returns_false(self):
        assert credit_rating_meets_minimum("ZZZ") is False

    def test_all_investment_grade_pass(self):
        investment_grade = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
                             "BBB+", "BBB", "BBB-"]
        for rating in investment_grade:
            assert credit_rating_meets_minimum(rating) is True, f"{rating} should pass"

    def test_all_below_investment_grade_fail(self):
        junk = ["BB+", "BB", "BB-", "B+", "B", "B-",
                "CCC+", "CCC", "CCC-", "CC", "C", "D"]
        for rating in junk:
            assert credit_rating_meets_minimum(rating) is False, f"{rating} should fail"

    def test_custom_minimum_aa(self):
        assert credit_rating_meets_minimum("AAA", minimum="AA") is True
        assert credit_rating_meets_minimum("AA-", minimum="AA") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Dividend Stock Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestDividendStockGate:

    def test_perfect_ticker_passes(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert result.passed is True
        assert result.status == GateStatus.PASS
        assert result.fail_reasons == []
        assert result.ticker == "JNJ"
        assert result.asset_class == AssetClass.DIVIDEND_STOCK

    def test_bbb_minus_passes(self, engine):
        data = DividendStockGateInput(
            ticker="T",
            credit_rating="BBB-",
            consecutive_positive_fcf_years=5,
            dividend_history_years=35,
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is True

    def test_junk_rating_fails(self, engine):
        data = DividendStockGateInput(
            ticker="BADCO",
            credit_rating="BB+",
            consecutive_positive_fcf_years=5,
            dividend_history_years=12,
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is False
        assert result.status == GateStatus.FAIL
        assert any("BB+" in r for r in result.fail_reasons)

    def test_insufficient_fcf_fails(self, engine):
        data = DividendStockGateInput(
            ticker="NEWCO",
            credit_rating="A",
            consecutive_positive_fcf_years=2,   # < 3 required
            dividend_history_years=15,
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is False
        assert any("FCF" in r or "fcf" in r.lower() for r in result.fail_reasons)

    def test_short_dividend_history_fails(self, engine):
        data = DividendStockGateInput(
            ticker="YOUNGCO",
            credit_rating="A",
            consecutive_positive_fcf_years=5,
            dividend_history_years=5,   # < 10 required
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is False
        assert any("dividend" in r.lower() for r in result.fail_reasons)

    def test_multiple_failures_captured(self, engine):
        data = DividendStockGateInput(
            ticker="BADCO",
            credit_rating="C",
            consecutive_positive_fcf_years=1,
            dividend_history_years=2,
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is False
        assert len(result.fail_reasons) == 3   # all three checks fail

    def test_missing_credit_rating_skipped(self, engine):
        data = DividendStockGateInput(
            ticker="UNRATED",
            credit_rating=None,
            consecutive_positive_fcf_years=5,
            dividend_history_years=15,
        )
        result = engine.evaluate_dividend_stock(data)
        # Should still pass (other checks pass, missing skipped with warning)
        assert result.passed is True
        assert result.checks["credit_rating"]["passed"] is None
        assert len(result.warnings) > 0
        assert result.data_quality_score < 100.0

    def test_all_fields_missing_insufficient_data(self, engine):
        data = DividendStockGateInput(ticker="GHOST")
        result = engine.evaluate_dividend_stock(data)
        assert result.status == GateStatus.INSUFFICIENT_DATA
        assert result.passed is False

    def test_exact_fcf_boundary(self, engine):
        """Exactly 3 years FCF should pass."""
        data = DividendStockGateInput(
            ticker="BORDERLINE",
            credit_rating="BBB",
            consecutive_positive_fcf_years=3,   # exactly the minimum
            dividend_history_years=10,
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is True

    def test_exact_dividend_boundary(self, engine):
        """Exactly 10 years dividend history should pass."""
        data = DividendStockGateInput(
            ticker="BORDERLINE",
            credit_rating="BBB",
            consecutive_positive_fcf_years=3,
            dividend_history_years=10,   # exactly the minimum
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.passed is True

    def test_result_has_valid_until(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert result.valid_until is not None
        assert result.valid_until > result.evaluated_at

    def test_data_quality_100_when_all_present(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert result.data_quality_score == 100.0

    def test_data_quality_drops_with_missing_field(self, engine):
        data = DividendStockGateInput(
            ticker="PARTIAL",
            credit_rating=None,   # missing
            consecutive_positive_fcf_years=5,
            dividend_history_years=12,
        )
        result = engine.evaluate_dividend_stock(data)
        assert result.data_quality_score < 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# Covered Call ETF Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoveredCallETFGate:

    def test_jepi_passes(self, engine, passing_etf):
        result = engine.evaluate_covered_call_etf(passing_etf)
        assert result.passed is True
        assert result.status == GateStatus.PASS
        assert result.asset_class == AssetClass.COVERED_CALL_ETF

    def test_small_etf_fails_aum(self, engine):
        data = CoveredCallETFGateInput(
            ticker="TINY",
            aum_millions=100.0,   # < 500M required
            track_record_years=4.0,
            distribution_history_months=24,
        )
        result = engine.evaluate_covered_call_etf(data)
        assert result.passed is False
        assert any("AUM" in r or "aum" in r.lower() for r in result.fail_reasons)

    def test_new_etf_fails_track_record(self, engine):
        data = CoveredCallETFGateInput(
            ticker="NEWETF",
            aum_millions=2000.0,
            track_record_years=1.5,   # < 3 years required
            distribution_history_months=18,
        )
        result = engine.evaluate_covered_call_etf(data)
        assert result.passed is False
        assert any("track record" in r.lower() for r in result.fail_reasons)

    def test_short_distribution_history_fails(self, engine):
        data = CoveredCallETFGateInput(
            ticker="SHORTDIST",
            aum_millions=2000.0,
            track_record_years=4.0,
            distribution_history_months=6,   # < 12 months required
        )
        result = engine.evaluate_covered_call_etf(data)
        assert result.passed is False

    def test_exact_aum_boundary(self, engine):
        """Exactly $500M AUM should pass."""
        data = CoveredCallETFGateInput(
            ticker="BOUNDARY",
            aum_millions=500.0,
            track_record_years=3.0,
            distribution_history_months=12,
        )
        result = engine.evaluate_covered_call_etf(data)
        assert result.passed is True

    def test_all_missing_insufficient_data(self, engine):
        data = CoveredCallETFGateInput(ticker="GHOST")
        result = engine.evaluate_covered_call_etf(data)
        assert result.status == GateStatus.INSUFFICIENT_DATA

    def test_checks_stored_correctly(self, engine, passing_etf):
        result = engine.evaluate_covered_call_etf(passing_etf)
        assert "aum" in result.checks
        assert "track_record" in result.checks
        assert "distribution_history" in result.checks
        assert result.checks["aum"]["passed"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Bond Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestBondGate:

    def test_treasury_passes(self, engine):
        data = BondGateInput(
            ticker="SHY",
            credit_rating="AAA",
            duration_years=2.5,
            issuer_type="GOVERNMENT",
        )
        result = engine.evaluate_bond(data)
        assert result.passed is True
        assert result.asset_class == AssetClass.BOND

    def test_long_duration_fails(self, engine):
        data = BondGateInput(
            ticker="TLT",
            credit_rating="AAA",
            duration_years=16.5,   # > 15 years max
        )
        result = engine.evaluate_bond(data)
        assert result.passed is False
        assert any("duration" in r.lower() for r in result.fail_reasons)

    def test_junk_bond_fails(self, engine):
        data = BondGateInput(
            ticker="JUNK",
            credit_rating="BB",
            duration_years=5.0,
        )
        result = engine.evaluate_bond(data)
        assert result.passed is False

    def test_exactly_15yr_duration_passes(self, engine):
        """Exactly 15 year duration should pass."""
        data = BondGateInput(
            ticker="MAXDUR",
            credit_rating="A",
            duration_years=15.0,
        )
        result = engine.evaluate_bond(data)
        assert result.passed is True

    def test_corporate_bond_warning(self, engine):
        data = BondGateInput(
            ticker="LQD",
            credit_rating="A",
            duration_years=8.0,
            issuer_type="CORPORATE",
        )
        result = engine.evaluate_bond(data)
        assert result.passed is True
        assert any("corporate" in w.lower() for w in result.warnings)

    def test_all_missing_insufficient_data(self, engine):
        data = BondGateInput(ticker="GHOST")
        result = engine.evaluate_bond(data)
        assert result.status == GateStatus.INSUFFICIENT_DATA


# ═══════════════════════════════════════════════════════════════════════════════
# GateResult contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateResultContract:

    def test_result_has_all_required_fields(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert hasattr(result, "ticker")
        assert hasattr(result, "asset_class")
        assert hasattr(result, "passed")
        assert hasattr(result, "status")
        assert hasattr(result, "fail_reasons")
        assert hasattr(result, "warnings")
        assert hasattr(result, "checks")
        assert hasattr(result, "data_quality_score")
        assert hasattr(result, "evaluated_at")
        assert hasattr(result, "valid_until")

    def test_evaluated_at_is_datetime(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert isinstance(result.evaluated_at, datetime)

    def test_fail_reasons_is_list(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert isinstance(result.fail_reasons, list)

    def test_pass_has_empty_fail_reasons(self, engine, passing_dividend_stock):
        result = engine.evaluate_dividend_stock(passing_dividend_stock)
        assert result.passed is True
        assert len(result.fail_reasons) == 0
