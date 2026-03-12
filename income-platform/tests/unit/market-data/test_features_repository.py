"""
Unit tests for the pure helper functions in features_repository.py.

Covers:
  _credit_quality_from_rating:
    - Investment-grade ratings (AAA, AA+, BBB-) → INVESTMENT_GRADE
    - Borderline ratings (BB+, BB, BB-)         → BORDERLINE
    - Speculative ratings (B+, CCC, D)          → SPECULATIVE_GRADE
    - None input                                → None
    - Case-insensitive / leading-trailing space handling

  _credit_quality_from_coverage:
    - interest_coverage >= 3.0  → INVESTMENT_GRADE
    - interest_coverage 1.5–2.99 → BORDERLINE
    - interest_coverage < 1.5   → SPECULATIVE_GRADE
    - None input                → None
    - Boundary values (exactly 3.0 and 1.5)

  compute_credit_quality_proxy:
    - Uses rating when available (ignores coverage)
    - Falls back to coverage when rating is None
    - Returns None when both are None

Run with:
    pytest tests/unit/market-data/test_features_repository.py -v
"""
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from repositories.features_repository import (  # noqa: E402
    _credit_quality_from_coverage,
    _credit_quality_from_rating,
    compute_credit_quality_proxy,
)


# ---------------------------------------------------------------------------
# _credit_quality_from_rating
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rating", [
    "AAA", "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
])
def test_credit_quality_from_rating_investment_grade(rating):
    assert _credit_quality_from_rating(rating) == "INVESTMENT_GRADE"


@pytest.mark.parametrize("rating", ["BB+", "BB", "BB-"])
def test_credit_quality_from_rating_borderline(rating):
    assert _credit_quality_from_rating(rating) == "BORDERLINE"


@pytest.mark.parametrize("rating", ["B+", "B", "B-", "CCC+", "CCC", "CC", "C", "D"])
def test_credit_quality_from_rating_speculative(rating):
    assert _credit_quality_from_rating(rating) == "SPECULATIVE_GRADE"


def test_credit_quality_from_rating_none_returns_none():
    assert _credit_quality_from_rating(None) is None


def test_credit_quality_from_rating_empty_string_returns_none():
    assert _credit_quality_from_rating("") is None


def test_credit_quality_from_rating_strips_whitespace():
    """Leading/trailing whitespace must be stripped before lookup."""
    assert _credit_quality_from_rating("  BBB+  ") == "INVESTMENT_GRADE"


def test_credit_quality_from_rating_case_insensitive():
    """Input is normalised to uppercase before lookup."""
    assert _credit_quality_from_rating("bbb-") == "INVESTMENT_GRADE"
    assert _credit_quality_from_rating("bb+") == "BORDERLINE"


# ---------------------------------------------------------------------------
# _credit_quality_from_coverage
# ---------------------------------------------------------------------------


def test_credit_quality_from_coverage_none_returns_none():
    assert _credit_quality_from_coverage(None) is None


def test_credit_quality_from_coverage_high_is_investment_grade():
    assert _credit_quality_from_coverage(5.0) == "INVESTMENT_GRADE"


def test_credit_quality_from_coverage_exactly_3_is_investment_grade():
    """Boundary: exactly 3.0 is INVESTMENT_GRADE (>= 3.0)."""
    assert _credit_quality_from_coverage(3.0) == "INVESTMENT_GRADE"


def test_credit_quality_from_coverage_borderline_range():
    assert _credit_quality_from_coverage(2.0) == "BORDERLINE"


def test_credit_quality_from_coverage_exactly_1_5_is_borderline():
    """Boundary: exactly 1.5 is BORDERLINE (>= 1.5)."""
    assert _credit_quality_from_coverage(1.5) == "BORDERLINE"


def test_credit_quality_from_coverage_below_1_5_is_speculative():
    assert _credit_quality_from_coverage(1.4) == "SPECULATIVE_GRADE"


def test_credit_quality_from_coverage_zero_is_speculative():
    assert _credit_quality_from_coverage(0.0) == "SPECULATIVE_GRADE"


def test_credit_quality_from_coverage_negative_is_speculative():
    assert _credit_quality_from_coverage(-1.0) == "SPECULATIVE_GRADE"


# ---------------------------------------------------------------------------
# compute_credit_quality_proxy
# ---------------------------------------------------------------------------


def test_compute_proxy_prefers_rating_over_coverage():
    """When rating is provided, coverage is ignored."""
    result = compute_credit_quality_proxy("AA", interest_coverage=0.5)
    assert result == "INVESTMENT_GRADE"


def test_compute_proxy_falls_back_to_coverage_when_rating_is_none():
    result = compute_credit_quality_proxy(None, interest_coverage=4.0)
    assert result == "INVESTMENT_GRADE"


def test_compute_proxy_falls_back_to_coverage_borderline():
    result = compute_credit_quality_proxy(None, interest_coverage=2.0)
    assert result == "BORDERLINE"


def test_compute_proxy_returns_none_when_both_are_none():
    assert compute_credit_quality_proxy(None, None) is None


def test_compute_proxy_speculative_rating_takes_precedence():
    """Speculative rating overrides a high coverage ratio."""
    result = compute_credit_quality_proxy("CCC", interest_coverage=10.0)
    assert result == "SPECULATIVE_GRADE"
