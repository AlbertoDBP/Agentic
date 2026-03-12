"""
Tests for classification/benchmarks.py
Target: 18 tests — all 7 asset classes, edge cases, dict structure.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from app.classification.benchmarks import (
    get_benchmark,
    benchmark_to_dict,
    BenchmarkProfile,
    BENCHMARKS,
)

KNOWN_CLASSES = [
    "COVERED_CALL_ETF",
    "DIVIDEND_STOCK",
    "EQUITY_REIT",
    "MORTGAGE_REIT",
    "BDC",
    "BOND",
    "PREFERRED_STOCK",
]

BENCHMARK_DICT_KEYS = {
    "peer_group",
    "yield_benchmark_pct",
    "expense_ratio_benchmark_pct",
    "nav_stability_benchmark",
    "pe_benchmark",
    "debt_equity_benchmark",
    "payout_ratio_benchmark",
}


# ── get_benchmark ──────────────────────────────────────────────────────────

class TestGetBenchmark:
    @pytest.mark.parametrize("asset_class", KNOWN_CLASSES)
    def test_known_class_returns_profile(self, asset_class):
        result = get_benchmark(asset_class)
        assert result is not None
        assert isinstance(result, BenchmarkProfile)

    def test_unknown_class_returns_none(self):
        assert get_benchmark("UNKNOWN_CLASS") is None

    def test_empty_string_returns_none(self):
        assert get_benchmark("") is None

    def test_lowercase_miss(self):
        # BENCHMARKS keys are uppercase; lowercase should miss
        assert get_benchmark("dividend_stock") is None


# ── BenchmarkProfile values ────────────────────────────────────────────────

class TestBenchmarkValues:
    def test_covered_call_etf_yield_benchmark(self):
        b = get_benchmark("COVERED_CALL_ETF")
        assert b.yield_benchmark_pct == 8.0

    def test_covered_call_etf_has_expense_ratio(self):
        b = get_benchmark("COVERED_CALL_ETF")
        assert b.expense_ratio_benchmark_pct is not None
        assert b.expense_ratio_benchmark_pct > 0

    def test_covered_call_etf_peer_group(self):
        b = get_benchmark("COVERED_CALL_ETF")
        assert "JEPI" in b.peer_group
        assert "JEPQ" in b.peer_group

    def test_dividend_stock_has_pe_benchmark(self):
        b = get_benchmark("DIVIDEND_STOCK")
        assert b.pe_benchmark is not None
        assert b.pe_benchmark > 0

    def test_dividend_stock_yield_below_reit(self):
        div = get_benchmark("DIVIDEND_STOCK")
        reit = get_benchmark("EQUITY_REIT")
        assert div.yield_benchmark_pct < reit.yield_benchmark_pct

    def test_mortgage_reit_highest_yield(self):
        mreit = get_benchmark("MORTGAGE_REIT")
        bdc   = get_benchmark("BDC")
        assert mreit.yield_benchmark_pct >= 10.0
        assert bdc.yield_benchmark_pct >= 8.0

    def test_bond_lowest_expense_ratio(self):
        bond = get_benchmark("BOND")
        etf  = get_benchmark("COVERED_CALL_ETF")
        assert bond.expense_ratio_benchmark_pct < etf.expense_ratio_benchmark_pct

    def test_preferred_stock_peer_group_can_be_empty(self):
        b = get_benchmark("PREFERRED_STOCK")
        assert isinstance(b.peer_group, list)


# ── benchmark_to_dict ──────────────────────────────────────────────────────

class TestBenchmarkToDict:
    @pytest.mark.parametrize("asset_class", KNOWN_CLASSES)
    def test_dict_has_all_keys(self, asset_class):
        profile = get_benchmark(asset_class)
        result = benchmark_to_dict(profile)
        assert BENCHMARK_DICT_KEYS == set(result.keys())

    def test_peer_group_is_list_in_dict(self):
        profile = get_benchmark("DIVIDEND_STOCK")
        d = benchmark_to_dict(profile)
        assert isinstance(d["peer_group"], list)

    def test_yield_benchmark_pct_is_float(self):
        for ac in KNOWN_CLASSES:
            d = benchmark_to_dict(get_benchmark(ac))
            assert isinstance(d["yield_benchmark_pct"], float)

    def test_none_values_preserved(self):
        # DIVIDEND_STOCK has no expense_ratio_benchmark_pct
        d = benchmark_to_dict(get_benchmark("DIVIDEND_STOCK"))
        assert d["expense_ratio_benchmark_pct"] is None


# ── BENCHMARKS dict completeness ───────────────────────────────────────────

class TestBenchmarksDict:
    def test_all_known_classes_in_benchmarks(self):
        for ac in KNOWN_CLASSES:
            assert ac in BENCHMARKS

    def test_benchmarks_count_matches_known_classes(self):
        assert len(BENCHMARKS) == len(KNOWN_CLASSES)
