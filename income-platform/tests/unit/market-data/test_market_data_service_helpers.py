"""
Unit tests for the pure helper functions in services/market_data_service.py.

Covers:
  _normalise_dates:
    - Converts ISO string 'date' values to date objects.
    - Leaves existing date objects unchanged.

  _filter_by_range:
    - Keeps only records in [start_date, end_date] (inclusive).
    - Returns records sorted ascending by date.
    - Outputs 'date' as ISO strings.
    - Handles mixed string / date input.

  _compute_yield_trailing_12m:
    - Sums dividends in the last 12 months and divides by current_price.
    - Returns None when current_price is 0 or None.
    - Returns None when no dividends fall within the trailing-12-month window.
    - Returns None when dividends list is empty.

  _compute_div_cagr_5y:
    - Computes annual-dividend CAGR correctly over N years.
    - Returns None when fewer than 2 distinct calendar years are available.
    - Excludes the current (in-progress) year to avoid partial-year bias.
    - Returns None when the earliest year amount is 0.

  _compute_yield_5yr_avg:
    - Averages per-year dividend yields over up to 5 calendar years.
    - Returns None when current_price is 0 or None.
    - Returns None when fewer than 2 years of dividend data exist.

Run with:
    pytest tests/unit/market-data/test_market_data_service_helpers.py -v
"""
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the service module directly so private helpers are accessible
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

_mds_path = _SERVICE_DIR / "services" / "market_data_service.py"
_spec = importlib.util.spec_from_file_location("services.market_data_service", _mds_path)
_mds = importlib.util.module_from_spec(_spec)
sys.modules["services.market_data_service"] = _mds
_spec.loader.exec_module(_mds)

_normalise_dates          = _mds._normalise_dates
_filter_by_range          = _mds._filter_by_range
_compute_yield_trailing_12m = _mds._compute_yield_trailing_12m
_compute_div_cagr_5y      = _mds._compute_div_cagr_5y
_compute_yield_5yr_avg    = _mds._compute_yield_5yr_avg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> date:
    return date.today()


def _days_ago(n: int) -> date:
    return _today() - timedelta(days=n)


def _div(ex_date: date, amount: float) -> dict:
    return {"ex_date": ex_date.isoformat(), "amount": amount}


# ---------------------------------------------------------------------------
# _normalise_dates
# ---------------------------------------------------------------------------


def test_normalise_dates_converts_string_to_date():
    prices = [{"date": "2024-01-15", "close": 100.0}]
    result = _normalise_dates(prices)
    assert result[0]["date"] == date(2024, 1, 15)


def test_normalise_dates_leaves_date_objects_unchanged():
    d = date(2024, 3, 1)
    prices = [{"date": d, "close": 50.0}]
    result = _normalise_dates(prices)
    assert result[0]["date"] == d


def test_normalise_dates_handles_empty_list():
    assert _normalise_dates([]) == []


def test_normalise_dates_preserves_other_fields():
    prices = [{"date": "2024-06-01", "close": 200.0, "volume": 1_000_000}]
    result = _normalise_dates(prices)
    assert result[0]["close"] == 200.0
    assert result[0]["volume"] == 1_000_000


# ---------------------------------------------------------------------------
# _filter_by_range
# ---------------------------------------------------------------------------


def test_filter_by_range_keeps_inclusive_bounds():
    d1 = date(2024, 1, 1)
    d2 = date(2024, 1, 31)
    prices = [
        {"date": d1, "close": 10.0},
        {"date": date(2024, 1, 15), "close": 11.0},
        {"date": d2, "close": 12.0},
    ]
    result = _filter_by_range(prices, d1, d2)
    assert len(result) == 3


def test_filter_by_range_excludes_out_of_range():
    prices = [
        {"date": date(2023, 12, 31), "close": 9.0},   # before
        {"date": date(2024, 1, 15), "close": 11.0},   # in range
        {"date": date(2024, 2, 1),  "close": 12.0},   # after
    ]
    result = _filter_by_range(prices, date(2024, 1, 1), date(2024, 1, 31))
    assert len(result) == 1
    assert result[0]["close"] == 11.0


def test_filter_by_range_output_sorted_ascending():
    prices = [
        {"date": date(2024, 1, 20), "close": 3.0},
        {"date": date(2024, 1, 5),  "close": 1.0},
        {"date": date(2024, 1, 10), "close": 2.0},
    ]
    result = _filter_by_range(prices, date(2024, 1, 1), date(2024, 1, 31))
    dates = [r["date"] for r in result]
    assert dates == sorted(dates)


def test_filter_by_range_dates_are_iso_strings_in_output():
    prices = [{"date": date(2024, 6, 1), "close": 5.0}]
    result = _filter_by_range(prices, date(2024, 1, 1), date(2024, 12, 31))
    assert isinstance(result[0]["date"], str)
    assert result[0]["date"] == "2024-06-01"


def test_filter_by_range_handles_string_input_dates():
    prices = [{"date": "2024-06-15", "close": 7.0}]
    result = _filter_by_range(prices, date(2024, 1, 1), date(2024, 12, 31))
    assert len(result) == 1


def test_filter_by_range_returns_empty_on_no_match():
    prices = [{"date": date(2023, 1, 1), "close": 5.0}]
    result = _filter_by_range(prices, date(2024, 1, 1), date(2024, 12, 31))
    assert result == []


# ---------------------------------------------------------------------------
# _compute_yield_trailing_12m
# ---------------------------------------------------------------------------


def test_compute_yield_trailing_12m_correct_calculation():
    """Sum dividends in last 12 months and divide by price × 100."""
    today = _today()
    divs = [
        _div(_days_ago(30), 0.50),
        _div(_days_ago(120), 0.50),
        _div(_days_ago(200), 0.50),
        _div(_days_ago(370), 0.50),   # > 365 days — excluded
    ]
    result = _compute_yield_trailing_12m(divs, current_price=100.0)
    # 3 dividends × 0.50 = 1.50 ; yield = 1.50 / 100 * 100 = 1.5%
    assert result is not None
    assert abs(result - 1.5) < 0.001


def test_compute_yield_trailing_12m_none_when_no_price():
    divs = [_div(_days_ago(30), 1.0)]
    assert _compute_yield_trailing_12m(divs, current_price=None) is None


def test_compute_yield_trailing_12m_none_when_price_zero():
    divs = [_div(_days_ago(30), 1.0)]
    assert _compute_yield_trailing_12m(divs, current_price=0) is None


def test_compute_yield_trailing_12m_none_when_empty_dividends():
    assert _compute_yield_trailing_12m([], current_price=100.0) is None


def test_compute_yield_trailing_12m_none_when_all_dividends_older_than_12m():
    divs = [_div(_days_ago(400), 1.0), _div(_days_ago(500), 1.0)]
    assert _compute_yield_trailing_12m(divs, current_price=100.0) is None


# ---------------------------------------------------------------------------
# _compute_div_cagr_5y
# ---------------------------------------------------------------------------


def test_compute_div_cagr_5y_correct_growth():
    """CAGR from 1.00/yr to 1.46/yr over 4 years ≈ 9.97%."""
    today_year = _today().year
    divs = [
        # 4 years back: annual total = 1.00
        _div(date(today_year - 4, 6, 15), 0.25),
        _div(date(today_year - 4, 9, 15), 0.25),
        _div(date(today_year - 4, 12, 15), 0.25),
        _div(date(today_year - 4, 3, 15), 0.25),
        # last full year: annual total = 1.46
        _div(date(today_year - 1, 3, 15), 0.365),
        _div(date(today_year - 1, 6, 15), 0.365),
        _div(date(today_year - 1, 9, 15), 0.365),
        _div(date(today_year - 1, 12, 15), 0.365),
    ]
    result = _compute_div_cagr_5y(divs)
    assert result is not None
    expected = ((1.46 / 1.00) ** (1 / 3) - 1) * 100  # 4-yr apart but 3 periods
    assert abs(result - expected) < 0.1


def test_compute_div_cagr_5y_none_when_single_year():
    """Returns None when only one distinct year of dividend data exists."""
    today_year = _today().year
    divs = [_div(date(today_year - 1, 6, 15), 0.50)]
    assert _compute_div_cagr_5y(divs) is None


def test_compute_div_cagr_5y_none_when_empty():
    assert _compute_div_cagr_5y([]) is None


def test_compute_div_cagr_5y_excludes_current_year():
    """Dividends with ex_date in the current calendar year must be excluded."""
    today_year = _today().year
    divs = [
        _div(date(today_year - 1, 6, 15), 1.0),
        _div(date(today_year,     6, 15), 2.0),   # current year — must be excluded
    ]
    # Only 1 valid year → None
    assert _compute_div_cagr_5y(divs) is None


def test_compute_div_cagr_5y_none_when_first_year_amount_zero():
    """Returns None when the earliest year's total dividend amount is zero."""
    today_year = _today().year
    divs = [
        _div(date(today_year - 3, 6, 15), 0.0),
        _div(date(today_year - 1, 6, 15), 1.0),
    ]
    assert _compute_div_cagr_5y(divs) is None


# ---------------------------------------------------------------------------
# _compute_yield_5yr_avg
# ---------------------------------------------------------------------------


def test_compute_yield_5yr_avg_correct_calculation():
    """Average of per-year dividend yields over 2 full calendar years."""
    today_year = _today().year
    # Year Y-2: total = 1.0 → yield = 1.0 / 100 * 100 = 1.0%
    # Year Y-1: total = 2.0 → yield = 2.0 / 100 * 100 = 2.0%
    # Average = 1.5%
    divs = [
        _div(date(today_year - 2, 6, 15), 1.0),
        _div(date(today_year - 1, 6, 15), 2.0),
    ]
    result = _compute_yield_5yr_avg(divs, current_price=100.0)
    assert result is not None
    assert abs(result - 1.5) < 0.001


def test_compute_yield_5yr_avg_none_when_no_price():
    today_year = _today().year
    divs = [
        _div(date(today_year - 2, 6, 15), 1.0),
        _div(date(today_year - 1, 6, 15), 1.0),
    ]
    assert _compute_yield_5yr_avg(divs, current_price=None) is None


def test_compute_yield_5yr_avg_none_when_price_zero():
    today_year = _today().year
    divs = [_div(date(today_year - 1, 6, 15), 1.0)]
    assert _compute_yield_5yr_avg(divs, current_price=0) is None


def test_compute_yield_5yr_avg_none_when_only_one_year():
    """Returns None when fewer than 2 calendar years of data are present."""
    today_year = _today().year
    divs = [_div(date(today_year - 1, 6, 15), 1.0)]
    assert _compute_yield_5yr_avg(divs, current_price=100.0) is None


def test_compute_yield_5yr_avg_none_when_empty():
    assert _compute_yield_5yr_avg([], current_price=100.0) is None
