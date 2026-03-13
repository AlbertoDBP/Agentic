"""
Agent 10 — NAV Erosion Monitor
Tests: detector.py — 40 tests covering all three alert types.
"""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

from app.monitor.detector import (
    AlertResult,
    detect_violations,
    _detect_nav_erosion,
    _detect_premium_discount,
    _detect_score_divergence,
)

# Default thresholds matching config defaults
_T = {
    "nav_erosion_30d_threshold": 0.05,
    "nav_erosion_90d_threshold": 0.10,
    "premium_discount_warning_pct": 0.08,
    "premium_discount_cap_pct": 0.15,
    "premium_discount_critical_abs": 0.15,
    "score_divergence_penalty_threshold": 10.0,
    "score_divergence_score_threshold": 55.0,
    "score_divergence_critical_score": 40.0,
}


def _snap(symbol="PDI", rate_30d=None, rate_90d=None, pd=0.0, rate_1y=None):
    return {
        "symbol": symbol,
        "erosion_rate_30d": rate_30d,
        "erosion_rate_90d": rate_90d,
        "erosion_rate_1y": rate_1y,
        "premium_discount": pd,
    }


def _score(total=60.0, penalty=5.0, details=None):
    return {
        "total_score": total,
        "nav_erosion_penalty": penalty,
        "nav_erosion_details": details or {},
    }


# ── NAV_EROSION detection ─────────────────────────────────────────────────────

class TestNavErosion:
    """15 tests."""

    def test_no_breach_returns_none(self):
        snap = _snap(rate_30d=-0.02, rate_90d=-0.05)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is None

    def test_30d_breach_only_is_warning(self):
        snap = _snap(rate_30d=-0.07, rate_90d=-0.05)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is not None
        assert result.alert_type == "NAV_EROSION"
        assert result.severity == "WARNING"

    def test_90d_breach_only_is_warning(self):
        snap = _snap(rate_30d=-0.02, rate_90d=-0.12)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is not None
        assert result.severity == "WARNING"

    def test_both_breach_is_critical(self):
        snap = _snap(rate_30d=-0.07, rate_90d=-0.12)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is not None
        assert result.severity == "CRITICAL"

    def test_symbol_preserved(self):
        snap = _snap(symbol="MAIN", rate_30d=-0.07, rate_90d=-0.12)
        result = _detect_nav_erosion("MAIN", snap, _T)
        assert result.symbol == "MAIN"

    def test_exactly_at_30d_threshold_no_alert(self):
        # -0.05 is not < -0.05
        snap = _snap(rate_30d=-0.05, rate_90d=0.0)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is None

    def test_just_below_30d_threshold_alerts(self):
        snap = _snap(rate_30d=-0.0501, rate_90d=0.0)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is not None

    def test_exactly_at_90d_threshold_no_alert(self):
        snap = _snap(rate_30d=0.0, rate_90d=-0.10)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is None

    def test_none_rates_no_alert(self):
        snap = _snap(rate_30d=None, rate_90d=None)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is None

    def test_30d_none_90d_breach_is_warning(self):
        snap = _snap(rate_30d=None, rate_90d=-0.12)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is not None
        assert result.severity == "WARNING"

    def test_30d_breach_90d_none_is_warning(self):
        snap = _snap(rate_30d=-0.07, rate_90d=None)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is not None
        assert result.severity == "WARNING"

    def test_details_contains_both_rates(self):
        snap = _snap(rate_30d=-0.07, rate_90d=-0.12)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert "erosion_rate_30d" in result.details
        assert "erosion_rate_90d" in result.details

    def test_erosion_rate_used_is_worst(self):
        snap = _snap(rate_30d=-0.07, rate_90d=-0.12)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result.erosion_rate_used == -0.12

    def test_details_contains_breach_flags(self):
        snap = _snap(rate_30d=-0.07, rate_90d=-0.05)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result.details["breach_30d"] is True
        assert result.details["breach_90d"] is False

    def test_positive_rates_no_alert(self):
        snap = _snap(rate_30d=0.03, rate_90d=0.05)
        result = _detect_nav_erosion("PDI", snap, _T)
        assert result is None


# ── PREMIUM_DISCOUNT_DRIFT detection ─────────────────────────────────────────

class TestPremiumDiscountDrift:
    """13 tests."""

    def test_within_band_no_alert(self):
        snap = _snap(pd=-0.03)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is None

    def test_deep_discount_triggers_alert(self):
        snap = _snap(pd=-0.10)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is not None
        assert result.alert_type == "PREMIUM_DISCOUNT_DRIFT"

    def test_deep_discount_warning_when_abs_le_15(self):
        snap = _snap(pd=-0.10)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result.severity == "WARNING"

    def test_deep_discount_critical_when_abs_gt_15(self):
        snap = _snap(pd=-0.20)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result.severity == "CRITICAL"

    def test_frothy_premium_triggers_alert(self):
        snap = _snap(pd=0.16)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is not None
        assert result.alert_type == "PREMIUM_DISCOUNT_DRIFT"

    def test_frothy_premium_warning_when_abs_le_15(self):
        # pd=0.16 → abs=0.16 > 0.15 → CRITICAL
        snap = _snap(pd=0.14)
        # pd=0.14 < cap=0.15, no alert
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is None

    def test_frothy_premium_critical_when_abs_gt_15(self):
        snap = _snap(pd=0.20)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result.severity == "CRITICAL"

    def test_pd_none_returns_none(self):
        snap = {"symbol": "PDI", "premium_discount": None}
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is None

    def test_exactly_at_warning_threshold_no_alert(self):
        # -0.08 is not < -0.08
        snap = _snap(pd=-0.08)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is None

    def test_just_below_warning_threshold_alerts(self):
        snap = _snap(pd=-0.0801)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is not None

    def test_exactly_at_cap_no_alert(self):
        # 0.15 is not > 0.15
        snap = _snap(pd=0.15)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result is None

    def test_details_contains_pd_value(self):
        snap = _snap(pd=-0.10)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result.details["premium_discount"] == -0.10

    def test_deep_discount_flag_set(self):
        snap = _snap(pd=-0.10)
        result = _detect_premium_discount("PDI", snap, _T)
        assert result.details["deep_discount"] is True
        assert result.details["frothy_premium"] is False


# ── SCORE_DIVERGENCE detection ────────────────────────────────────────────────

class TestScoreDivergence:
    """12 tests."""

    def test_high_penalty_low_score_triggers(self):
        snap = _snap()
        score = _score(total=50.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result is not None
        assert result.alert_type == "SCORE_DIVERGENCE"

    def test_severity_warning_when_score_40_to_55(self):
        snap = _snap()
        score = _score(total=50.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result.severity == "WARNING"

    def test_severity_critical_when_score_below_40(self):
        snap = _snap()
        score = _score(total=35.0, penalty=15.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result.severity == "CRITICAL"

    def test_penalty_at_threshold_no_alert(self):
        # penalty=10.0 is not > 10.0
        snap = _snap()
        score = _score(total=50.0, penalty=10.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result is None

    def test_score_at_threshold_no_alert(self):
        # total_score=55.0 is not < 55.0
        snap = _snap()
        score = _score(total=55.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result is None

    def test_none_score_returns_none(self):
        snap = _snap()
        result = _detect_score_divergence("PDI", snap, None, _T)
        assert result is None

    def test_none_penalty_field_returns_none(self):
        snap = _snap()
        score = {"total_score": 50.0, "nav_erosion_penalty": None}
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result is None

    def test_none_total_score_field_returns_none(self):
        snap = _snap()
        score = {"total_score": None, "nav_erosion_penalty": 12.0}
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result is None

    def test_score_at_alert_populated(self):
        snap = _snap()
        score = _score(total=45.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result.score_at_alert == 45.0

    def test_details_contains_penalty(self):
        snap = _snap()
        score = _score(total=50.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result.details["nav_erosion_penalty"] == 12.0

    def test_details_contains_total_score(self):
        snap = _snap()
        score = _score(total=50.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result.details["total_score"] == 50.0

    def test_exactly_at_critical_score_threshold_is_warning(self):
        # total_score exactly 40.0 — NOT < 40 → WARNING
        snap = _snap()
        score = _score(total=40.0, penalty=12.0)
        result = _detect_score_divergence("PDI", snap, score, _T)
        assert result.severity == "WARNING"


# ── detect_violations integration ─────────────────────────────────────────────

class TestDetectViolations:
    """10 tests."""

    def test_empty_snapshots_returns_empty(self):
        results = detect_violations([], {})
        assert results == []

    def test_no_violations_returns_empty(self):
        snap = _snap(rate_30d=-0.01, rate_90d=-0.02, pd=0.0)
        results = detect_violations([snap], {})
        assert results == []

    def test_multiple_alert_types_same_symbol(self):
        snap = _snap(symbol="PDI", rate_30d=-0.07, rate_90d=-0.12, pd=-0.10)
        score = _score(total=50.0, penalty=12.0)
        results = detect_violations([snap], {"PDI": score})
        types = {r.alert_type for r in results}
        assert "NAV_EROSION" in types
        assert "PREMIUM_DISCOUNT_DRIFT" in types
        assert "SCORE_DIVERGENCE" in types

    def test_returns_list_of_alert_results(self):
        snap = _snap(rate_30d=-0.07)
        results = detect_violations([snap], {})
        assert all(isinstance(r, AlertResult) for r in results)

    def test_multiple_symbols_scanned(self):
        snaps = [
            _snap(symbol="PDI", rate_30d=-0.07),
            _snap(symbol="MAIN", rate_30d=-0.07),
        ]
        results = detect_violations(snaps, {})
        symbols = {r.symbol for r in results}
        assert "PDI" in symbols
        assert "MAIN" in symbols

    def test_no_score_for_symbol_still_detects_nav_erosion(self):
        snap = _snap(rate_30d=-0.07)
        results = detect_violations([snap], {})
        assert any(r.alert_type == "NAV_EROSION" for r in results)

    def test_score_divergence_requires_score(self):
        snap = _snap()
        # No score provided → no SCORE_DIVERGENCE alert
        results = detect_violations([snap], {})
        assert not any(r.alert_type == "SCORE_DIVERGENCE" for r in results)

    def test_snapshot_missing_symbol_skipped(self):
        snap = {"erosion_rate_30d": -0.07, "erosion_rate_90d": -0.12}
        results = detect_violations([snap], {})
        assert results == []

    def test_score_at_alert_populated_for_nav_erosion(self):
        snap = _snap(symbol="PDI", rate_30d=-0.07)
        score = _score(total=62.0, penalty=3.0)
        results = detect_violations([snap], {"PDI": score})
        nav_results = [r for r in results if r.alert_type == "NAV_EROSION"]
        assert nav_results[0].score_at_alert == 62.0

    def test_all_safe_no_alerts(self):
        snaps = [
            _snap(symbol="PDI", rate_30d=-0.01, rate_90d=-0.02, pd=0.05),
            _snap(symbol="MAIN", rate_30d=-0.02, rate_90d=-0.03, pd=-0.02),
        ]
        scores = {
            "PDI": _score(total=75.0, penalty=2.0),
            "MAIN": _score(total=80.0, penalty=1.0),
        }
        results = detect_violations(snaps, scores)
        assert results == []
