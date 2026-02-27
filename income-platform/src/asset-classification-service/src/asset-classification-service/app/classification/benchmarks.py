"""
Benchmarks
Class-specific peer groups and benchmark values for sub-scoring.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class BenchmarkProfile:
    peer_group: list
    yield_benchmark_pct: float
    expense_ratio_benchmark_pct: Optional[float]
    nav_stability_benchmark: Optional[str]
    pe_benchmark: Optional[float]
    debt_equity_benchmark: Optional[float]
    payout_ratio_benchmark: Optional[float]


BENCHMARKS: Dict[str, BenchmarkProfile] = {
    "COVERED_CALL_ETF": BenchmarkProfile(
        peer_group=["JEPI", "JEPQ", "QYLD", "XYLD", "DIVO"],
        yield_benchmark_pct=8.0,
        expense_ratio_benchmark_pct=0.45,
        nav_stability_benchmark="moderate",
        pe_benchmark=None,
        debt_equity_benchmark=None,
        payout_ratio_benchmark=None,
    ),
    "DIVIDEND_STOCK": BenchmarkProfile(
        peer_group=["JNJ", "PG", "KO", "MMM", "T"],
        yield_benchmark_pct=3.0,
        expense_ratio_benchmark_pct=None,
        nav_stability_benchmark=None,
        pe_benchmark=18.0,
        debt_equity_benchmark=1.0,
        payout_ratio_benchmark=0.60,
    ),
    "EQUITY_REIT": BenchmarkProfile(
        peer_group=["O", "VICI", "AMT", "CCI", "SPG"],
        yield_benchmark_pct=4.5,
        expense_ratio_benchmark_pct=None,
        nav_stability_benchmark=None,
        pe_benchmark=None,
        debt_equity_benchmark=1.5,
        payout_ratio_benchmark=0.85,
    ),
    "MORTGAGE_REIT": BenchmarkProfile(
        peer_group=["AGNC", "NLY", "RITM", "MFA", "PMT"],
        yield_benchmark_pct=10.0,
        expense_ratio_benchmark_pct=None,
        nav_stability_benchmark="volatile",
        pe_benchmark=None,
        debt_equity_benchmark=5.0,
        payout_ratio_benchmark=0.90,
    ),
    "BDC": BenchmarkProfile(
        peer_group=["ARCC", "MAIN", "BXSL", "OBDC", "HTGC"],
        yield_benchmark_pct=9.0,
        expense_ratio_benchmark_pct=None,
        nav_stability_benchmark="moderate",
        pe_benchmark=None,
        debt_equity_benchmark=1.0,
        payout_ratio_benchmark=0.90,
    ),
    "BOND": BenchmarkProfile(
        peer_group=["AGG", "BND", "LQD", "TLT", "IEF"],
        yield_benchmark_pct=4.0,
        expense_ratio_benchmark_pct=0.10,
        nav_stability_benchmark="stable",
        pe_benchmark=None,
        debt_equity_benchmark=None,
        payout_ratio_benchmark=None,
    ),
    "PREFERRED_STOCK": BenchmarkProfile(
        peer_group=[],
        yield_benchmark_pct=6.0,
        expense_ratio_benchmark_pct=None,
        nav_stability_benchmark="stable",
        pe_benchmark=None,
        debt_equity_benchmark=None,
        payout_ratio_benchmark=None,
    ),
}


def get_benchmark(asset_class: str) -> Optional[BenchmarkProfile]:
    return BENCHMARKS.get(asset_class)


def benchmark_to_dict(profile: BenchmarkProfile) -> dict:
    return {
        "peer_group": profile.peer_group,
        "yield_benchmark_pct": profile.yield_benchmark_pct,
        "expense_ratio_benchmark_pct": profile.expense_ratio_benchmark_pct,
        "nav_stability_benchmark": profile.nav_stability_benchmark,
        "pe_benchmark": profile.pe_benchmark,
        "debt_equity_benchmark": profile.debt_equity_benchmark,
        "payout_ratio_benchmark": profile.payout_ratio_benchmark,
    }
