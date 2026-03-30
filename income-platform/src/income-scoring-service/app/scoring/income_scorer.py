"""
Agent 03 — Income Scoring Service
Income Scorer: Weighted scoring engine (valuation + durability + technical).

Score breakdown (0–100):
  Valuation & Yield        0–weight_yield       (payout_sustainability + yield_vs_market + fcf_coverage)
  Financial Durability     0–weight_durability  (debt_safety + dividend_consistency + volatility_score)
  Technical Entry          0–weight_technical   (price_momentum + price_range_position)

Pillar weights are class-specific and loaded from ScoringWeightProfile (v2.0).
Default fallback: 40/40/20 (preserves v1.0 behavior when no profile is in DB).

Sub-component ceilings are computed as:
    ceiling = pillar_budget × sub_weight_pct / 100

Each sub-component is scored on a normalised scale [0.0–1.0], then multiplied
by its ceiling, so changing pillar totals does not alter the scoring thresholds.

Missing data: any None field scores 50% of its sub-component maximum (partial
credit). The missing-field count drives data_completeness_pct.

Grade thresholds: A+(≥95) A(≥85) B+(≥75) B(≥70) C(≥60) D(≥50) F(<50)
Recommendation:   AGGRESSIVE_BUY(≥85) ACCUMULATE(≥70) WATCH(<70)
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Number of scoreable dimensions (used for data_completeness_pct).
_TOTAL_FIELDS = 8

# ── Default weight profile (v1.0 universal weights) ───────────────────────────
# Used when no class-specific profile is found in the database.
# With these defaults all sub-component ceilings are identical to the v1.0
# hardcoded values, so existing behaviour is fully preserved.

_DEFAULT_WEIGHT_PROFILE: dict = {
    "asset_class": "DEFAULT",
    "version": 0,
    "source": "FALLBACK",
    "weight_yield": 40,
    "weight_durability": 40,
    "weight_technical": 20,
    "yield_sub_weights":      {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25},
    "durability_sub_weights": {"debt_safety": 40, "dividend_consistency": 35, "volatility_score": 25},
    "technical_sub_weights":  {"price_momentum": 60, "price_range_position": 40},
}


def _compute_ceilings(profile: dict) -> dict:
    """Derive absolute point ceilings for each sub-component from a weight profile.

    All arithmetic is in floats to avoid rounding issues when the profile
    contains non-round pillar weights.

    With the default 40/40/20 profile the results are:
        payout_sustainability=16, yield_vs_market=14, fcf_coverage=10,
        debt_safety=16, dividend_consistency=14, volatility_score=10,
        price_momentum=12, price_range_position=8
    — identical to the v1.0 hardcoded values.
    """
    wy = float(profile["weight_yield"])
    wd = float(profile["weight_durability"])
    wt = float(profile["weight_technical"])

    ysub = profile["yield_sub_weights"]
    dsub = profile["durability_sub_weights"]
    tsub = profile["technical_sub_weights"]

    return {
        "payout_sustainability": wy * ysub["payout_sustainability"] / 100.0,
        "yield_vs_market":       wy * ysub["yield_vs_market"]       / 100.0,
        "fcf_coverage":          wy * ysub["fcf_coverage"]          / 100.0,
        "debt_safety":           wd * dsub["debt_safety"]           / 100.0,
        "dividend_consistency":  wd * dsub["dividend_consistency"]  / 100.0,
        "volatility_score":      wd * dsub["volatility_score"]      / 100.0,
        "price_momentum":        wt * tsub["price_momentum"]        / 100.0,
        "price_range_position":  wt * tsub["price_range_position"]  / 100.0,
    }


# ── Normalised score functions ─────────────────────────────────────────────────
# Each returns a float in [0.0, 1.0].  None input → 0.5 (50% partial credit).
# These are module-level so they can be unit-tested independently.

def _norm_payout(payout_ratio: Optional[float]) -> float:
    if payout_ratio is None:
        return 0.5
    if payout_ratio < 0.40:
        return 1.0
    if payout_ratio < 0.60:
        return 0.75
    if payout_ratio < 0.75:
        return 0.50
    if payout_ratio < 0.90:
        return 0.25
    return 0.0


def _norm_yield(div_yield: Optional[float]) -> float:
    if div_yield is None:
        return 0.5
    if div_yield > 4.0:
        return 1.0
    if div_yield > 3.0:
        return 10.0 / 14.0
    if div_yield > 2.0:
        return 6.0  / 14.0
    if div_yield > 1.0:
        return 2.0  / 14.0
    return 0.0


def _norm_fcf(free_cash_flow: Optional[float]) -> float:
    if free_cash_flow is None:
        return 0.5
    if free_cash_flow > 0:
        return 1.0
    if free_cash_flow < 0:
        return 0.0
    return 0.5  # exactly zero → neutral


def _norm_debt(debt_to_equity: Optional[float]) -> float:
    if debt_to_equity is None:
        return 0.5
    if debt_to_equity < 0.5:
        return 1.0
    if debt_to_equity < 1.0:
        return 0.75
    if debt_to_equity < 1.5:
        return 0.50
    if debt_to_equity < 2.0:
        return 0.25
    return 0.0


def _norm_consistency(div_years: Optional[int]) -> float:
    if div_years is None:
        return 0.5
    if div_years > 25:
        return 1.0
    if div_years > 15:
        return 10.0 / 14.0
    if div_years > 10:
        return 7.0  / 14.0
    return 4.0 / 14.0


def _norm_volatility(volatility: Optional[float]) -> float:
    if volatility is None:
        return 0.5
    if volatility < 2:
        return 1.0
    if volatility < 5:
        return 0.7
    if volatility < 10:
        return 0.4
    if volatility < 20:
        return 0.2
    return 0.0


def _norm_momentum(price_change_pct: Optional[float]) -> float:
    if price_change_pct is None:
        return 0.5
    if price_change_pct < -15.0:
        return 1.0
    if price_change_pct < -5.0:
        return 8.0  / 12.0
    if price_change_pct < 5.0:
        return 6.0  / 12.0
    if price_change_pct < 15.0:
        return 3.0  / 12.0
    return 0.0


def _norm_range(range_ratio: Optional[float]) -> float:
    if range_ratio is None:
        return 0.5
    if range_ratio < 0.3:
        return 1.0
    if range_ratio < 0.5:
        return 5.0 / 8.0
    if range_ratio < 0.7:
        return 3.0 / 8.0
    return 1.0 / 8.0


CHOWDER_THRESHOLDS = {
    "DIVIDEND_STOCK":   {"attractive": 12.0, "floor": 8.0},
    "COVERED_CALL_ETF": {"attractive": 8.0,  "floor": 5.0},
    "BOND":             {"attractive": 8.0,  "floor": 5.0},
}


def _chowder_signal_from_number(chowder: float, asset_class: str) -> str:
    """Classify a pre-computed chowder number against the asset-class thresholds."""
    t = CHOWDER_THRESHOLDS.get(asset_class.upper(), CHOWDER_THRESHOLDS["DIVIDEND_STOCK"])
    if chowder >= t["attractive"]:
        return "ATTRACTIVE"
    elif chowder >= t["floor"]:
        return "BORDERLINE"
    else:
        return "UNATTRACTIVE"


def _compute_chowder(
    yield_ttm: Optional[float],
    div_cagr_5y: Optional[float],
    asset_class: str,
) -> tuple[Optional[float], Optional[str]]:
    if yield_ttm is None or div_cagr_5y is None:
        return None, "INSUFFICIENT_DATA"
    # Cast explicitly to float — asyncpg returns Decimal for NUMERIC columns
    chowder = float(yield_ttm) + float(div_cagr_5y)
    return round(chowder, 4), _chowder_signal_from_number(chowder, asset_class)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ScoreResult:
    ticker: str = ""
    asset_class: str = ""

    # Component scores
    valuation_yield_score: float = 0.0
    financial_durability_score: float = 0.0
    technical_entry_score: float = 0.0

    # Totals
    total_score_raw: float = 0.0
    nav_erosion_penalty: float = 0.0    # applied externally for COVERED_CALL_ETF
    total_score: float = 0.0

    # Classification
    grade: str = "F"
    recommendation: str = "WATCH"

    # Explainability
    factor_details: dict = field(default_factory=dict)
    data_quality_score: float = 100.0
    data_completeness_pct: float = 100.0

    # Chowder Rule
    chowder_number: Optional[float] = None
    chowder_signal: Optional[str] = None

    # v2.0: weight profile provenance
    weight_profile_version: Optional[int] = None
    weight_profile_id: Optional[str] = None

    # v2.1: weight profile dict (class-specific weights used during scoring)
    weight_profile: Optional[dict] = None


# ── Scorer ────────────────────────────────────────────────────────────────────

class IncomeScorer:
    """Synchronous scoring engine for income assets.

    All I/O (market data fetching) happens upstream in the API layer.
    This class is pure computation — no network calls, no DB access.
    """

    def score(
        self,
        ticker: str,
        asset_class: str,
        quality_gate_result,      # GateResult dataclass or ORM QualityGateResult or None
        market_data: dict,
        weight_profile: Optional[dict] = None,  # v2.0: class-specific weight profile
    ) -> ScoreResult:
        """Score a ticker using pre-fetched market data.

        Args:
            ticker:              Ticker symbol.
            asset_class:         Asset class string (DIVIDEND_STOCK, COVERED_CALL_ETF, BOND …).
            quality_gate_result: Object with .dividend_history_years attribute, or None.
            market_data:         Dict containing keys:
                                   fundamentals    → dict from /fundamentals
                                   dividend_history → list from /dividends
                                   history_stats   → dict from /history/stats
                                   current_price   → dict from /price
            weight_profile:      Class-specific weight profile dict from WeightProfileLoader.
                                  If None, the universal 40/40/20 fallback is used.

        Returns:
            ScoreResult with all component scores, grade, and recommendation.
            nav_erosion_penalty is left at 0.0 — the API layer applies it.
        """
        ticker = ticker.upper()
        fundamentals       = market_data.get("fundamentals")      or {}
        dividend_history   = market_data.get("dividend_history")  or []
        history_stats      = market_data.get("history_stats")     or {}
        current_price_data = market_data.get("current_price")     or {}

        # ── Resolve weight profile & compute sub-component ceilings ───────────

        profile  = weight_profile if weight_profile else _DEFAULT_WEIGHT_PROFILE
        ceilings = _compute_ceilings(profile)

        profile_version = profile.get("version")
        profile_id      = profile.get("id")

        none_count = 0  # counts fields that fell back to partial credit

        # ── Valuation & Yield ─────────────────────────────────────────────────

        payout_ratio = fundamentals.get("payout_ratio")
        if payout_ratio is None:
            none_count += 1
        payout_score = _norm_payout(payout_ratio) * ceilings["payout_sustainability"]

        # yield_vs_market: annual dividend / avg_price * 100
        avg_price  = history_stats.get("avg_price")
        div_yield: Optional[float] = None
        if dividend_history and avg_price and avg_price > 0:
            annual_div = sum(float(d.get("amount") or 0) for d in dividend_history[:4])
            div_yield = (annual_div / avg_price) * 100
        if div_yield is None:
            none_count += 1
        yield_score = _norm_yield(div_yield) * ceilings["yield_vs_market"]

        free_cash_flow = fundamentals.get("free_cash_flow")
        if free_cash_flow is None:
            none_count += 1
        fcf_score = _norm_fcf(free_cash_flow) * ceilings["fcf_coverage"]

        valuation_yield_score = payout_score + yield_score + fcf_score

        # ── Financial Durability ──────────────────────────────────────────────

        debt_to_equity = fundamentals.get("debt_to_equity")
        if debt_to_equity is None:
            none_count += 1
        debt_score = _norm_debt(debt_to_equity) * ceilings["debt_safety"]

        div_years: Optional[int] = getattr(quality_gate_result, "dividend_history_years", None)
        if div_years is None:
            none_count += 1
        consistency_score = _norm_consistency(div_years) * ceilings["dividend_consistency"]

        volatility = history_stats.get("volatility")
        if volatility is None:
            none_count += 1
        vol_score = _norm_volatility(volatility) * ceilings["volatility_score"]

        financial_durability_score = debt_score + consistency_score + vol_score

        # ── Technical Entry ───────────────────────────────────────────────────

        price_change_pct = history_stats.get("price_change_pct")
        if price_change_pct is None:
            none_count += 1
        momentum_score = _norm_momentum(price_change_pct) * ceilings["price_momentum"]

        min_price     = history_stats.get("min_price")
        max_price     = history_stats.get("max_price")
        current_price = current_price_data.get("price") if current_price_data else None

        range_ratio: Optional[float] = None
        if min_price is not None and max_price is not None and current_price is not None:
            if max_price != min_price:
                range_ratio = (current_price - min_price) / (max_price - min_price)
            else:
                range_ratio = 0.5  # flat range — treat as neutral mid-point
        if range_ratio is None:
            none_count += 1
        range_score = _norm_range(range_ratio) * ceilings["price_range_position"]

        technical_entry_score = momentum_score + range_score

        # ── Totals & classification ───────────────────────────────────────────

        total_score_raw = float(
            valuation_yield_score + financial_durability_score + technical_entry_score
        )
        data_completeness_pct = round((1 - none_count / _TOTAL_FIELDS) * 100, 1)
        data_quality_score    = min(100.0, data_completeness_pct)

        grade          = self._grade(total_score_raw)
        recommendation = self._recommendation(total_score_raw)

        factor_details = {
            "payout_sustainability": {
                "value": payout_ratio,
                "score": round(payout_score, 4),
                "max": round(ceilings["payout_sustainability"], 4),
            },
            "yield_vs_market": {
                "value": round(div_yield, 4) if div_yield is not None else None,
                "score": round(yield_score, 4),
                "max": round(ceilings["yield_vs_market"], 4),
            },
            "fcf_coverage": {
                "value": free_cash_flow,
                "score": round(fcf_score, 4),
                "max": round(ceilings["fcf_coverage"], 4),
            },
            "debt_safety": {
                "value": debt_to_equity,
                "score": round(debt_score, 4),
                "max": round(ceilings["debt_safety"], 4),
            },
            "dividend_consistency": {
                "value": div_years,
                "score": round(consistency_score, 4),
                "max": round(ceilings["dividend_consistency"], 4),
            },
            "volatility_score": {
                "value": volatility,
                "score": round(vol_score, 4),
                "max": round(ceilings["volatility_score"], 4),
            },
            "price_momentum": {
                "value": price_change_pct,
                "score": round(momentum_score, 4),
                "max": round(ceilings["price_momentum"], 4),
            },
            "price_range_position": {
                "value": round(range_ratio, 4) if range_ratio is not None else None,
                "score": round(range_score, 4),
                "max": round(ceilings["price_range_position"], 4),
            },
        }

        result = ScoreResult(
            ticker=ticker,
            asset_class=asset_class,
            valuation_yield_score=round(valuation_yield_score, 4),
            financial_durability_score=round(financial_durability_score, 4),
            technical_entry_score=round(technical_entry_score, 4),
            total_score_raw=round(total_score_raw, 4),
            nav_erosion_penalty=0.0,
            total_score=round(total_score_raw, 4),
            grade=grade,
            recommendation=recommendation,
            factor_details=factor_details,
            data_quality_score=data_quality_score,
            data_completeness_pct=data_completeness_pct,
            weight_profile_version=profile_version,
            weight_profile_id=profile_id,
        )

        features  = market_data.get("features", {})
        yield_ttm = features.get("yield_trailing_12m")
        div_cagr5 = features.get("div_cagr_5y")

        if features.get("chowder_number") is not None and yield_ttm is None:
            chowder_number = float(features["chowder_number"])
            chowder_signal = _chowder_signal_from_number(chowder_number, asset_class)
        else:
            chowder_number, chowder_signal = _compute_chowder(yield_ttm, div_cagr5, asset_class)

        result.chowder_number = chowder_number
        result.chowder_signal = chowder_signal
        result.factor_details["chowder_number"] = chowder_number
        result.factor_details["chowder_signal"] = chowder_signal

        return result

    # ── Classification helpers (static, so API layer can call them post-penalty) ──

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 95:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"

    @staticmethod
    def _recommendation(score: float) -> str:
        if score >= 85:
            return "AGGRESSIVE_BUY"
        elif score >= 70:
            return "ACCUMULATE"
        else:
            return "WATCH"
