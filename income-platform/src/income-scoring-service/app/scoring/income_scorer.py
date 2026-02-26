"""
Agent 03 — Income Scoring Service
Income Scorer: Weighted scoring engine (valuation + durability + technical).

Score breakdown (0–100):
  Valuation & Yield        0–40  (payout_sustainability + yield_vs_market + fcf_coverage)
  Financial Durability     0–40  (debt_safety + dividend_consistency + volatility_score)
  Technical Entry          0–20  (price_momentum + price_range_position)

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


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ScoreResult:
    ticker: str
    asset_class: str

    # Component scores
    valuation_yield_score: float = 0.0       # 0–40
    financial_durability_score: float = 0.0  # 0–40
    technical_entry_score: float = 0.0       # 0–20

    # Totals
    total_score_raw: float = 0.0
    nav_erosion_penalty: float = 0.0         # 0–30, applied externally
    total_score: float = 0.0

    # Classification
    grade: str = "F"
    recommendation: str = "WATCH"

    # Explainability
    factor_details: dict = field(default_factory=dict)
    data_quality_score: float = 100.0
    data_completeness_pct: float = 100.0


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
    ) -> ScoreResult:
        """Score a ticker using pre-fetched market data.

        Args:
            ticker:              Ticker symbol.
            asset_class:         Asset class string (DIVIDEND_STOCK, COVERED_CALL_ETF, BOND).
            quality_gate_result: Object with .dividend_history_years attribute, or None.
            market_data:         Dict containing keys:
                                   fundamentals    → dict from /fundamentals
                                   dividend_history → list from /dividends
                                   history_stats   → dict from /history/stats
                                   current_price   → dict from /price

        Returns:
            ScoreResult with all component scores, grade, and recommendation.
            nav_erosion_penalty is left at 0.0 — the API layer applies it.
        """
        ticker = ticker.upper()
        fundamentals      = market_data.get("fundamentals")      or {}
        dividend_history  = market_data.get("dividend_history")  or []
        history_stats     = market_data.get("history_stats")     or {}
        current_price_data = market_data.get("current_price")    or {}

        none_count = 0  # counts fields that fell back to partial credit

        # ── Valuation & Yield (0–40) ──────────────────────────────────────────

        # payout_sustainability (0–16)
        payout_ratio = fundamentals.get("payout_ratio")
        if payout_ratio is None:
            none_count += 1
            payout_score = 8        # 50% of 16
        elif payout_ratio < 0.40:
            payout_score = 16
        elif payout_ratio < 0.60:
            payout_score = 12
        elif payout_ratio < 0.75:
            payout_score = 8
        elif payout_ratio < 0.90:
            payout_score = 4
        else:
            payout_score = 0

        # yield_vs_market (0–14): annual dividend / avg_price * 100
        avg_price = history_stats.get("avg_price")
        div_yield: Optional[float] = None
        if dividend_history and avg_price and avg_price > 0:
            annual_div = sum(
                float(d.get("amount") or 0) for d in dividend_history[:4]
            )
            div_yield = (annual_div / avg_price) * 100

        if div_yield is None:
            none_count += 1
            yield_score = 7         # 50% of 14
        elif div_yield > 4.0:
            yield_score = 14
        elif div_yield > 3.0:
            yield_score = 10
        elif div_yield > 2.0:
            yield_score = 6
        elif div_yield > 1.0:
            yield_score = 2
        else:
            yield_score = 0

        # fcf_coverage (0–10)
        free_cash_flow = fundamentals.get("free_cash_flow")
        if free_cash_flow is None:
            none_count += 1
            fcf_score = 5           # 50% of 10
        elif free_cash_flow > 0:
            fcf_score = 10
        elif free_cash_flow < 0:
            fcf_score = 0
        else:                        # == 0
            fcf_score = 5

        valuation_yield_score = payout_score + yield_score + fcf_score

        # ── Financial Durability (0–40) ───────────────────────────────────────

        # debt_safety (0–16)
        debt_to_equity = fundamentals.get("debt_to_equity")
        if debt_to_equity is None:
            none_count += 1
            debt_score = 8          # 50% of 16
        elif debt_to_equity < 0.5:
            debt_score = 16
        elif debt_to_equity < 1.0:
            debt_score = 12
        elif debt_to_equity < 1.5:
            debt_score = 8
        elif debt_to_equity < 2.0:
            debt_score = 4
        else:
            debt_score = 0

        # dividend_consistency (0–14): from quality_gate_result.dividend_history_years
        div_years: Optional[int] = getattr(quality_gate_result, "dividend_history_years", None)
        if div_years is None:
            none_count += 1
            consistency_score = 7   # 50% of 14
        elif div_years > 25:
            consistency_score = 14
        elif div_years > 15:
            consistency_score = 10
        elif div_years > 10:
            consistency_score = 7
        else:
            consistency_score = 4

        # volatility_score (0–10): price standard deviation
        volatility = history_stats.get("volatility")
        if volatility is None:
            none_count += 1
            vol_score = 5           # 50% of 10
        elif volatility < 2:
            vol_score = 10
        elif volatility < 5:
            vol_score = 7
        elif volatility < 10:
            vol_score = 4
        elif volatility < 20:
            vol_score = 2
        else:
            vol_score = 0

        financial_durability_score = debt_score + consistency_score + vol_score

        # ── Technical Entry (0–20) ────────────────────────────────────────────

        # price_momentum (0–12): 90-day price_change_pct
        price_change_pct = history_stats.get("price_change_pct")
        if price_change_pct is None:
            none_count += 1
            momentum_score = 6      # 50% of 12
        elif price_change_pct < -15.0:
            momentum_score = 12     # oversold — best entry signal
        elif price_change_pct < -5.0:
            momentum_score = 8
        elif price_change_pct < 5.0:
            momentum_score = 6
        elif price_change_pct < 15.0:
            momentum_score = 3
        else:
            momentum_score = 0

        # price_range_position (0–8): where current price sits in the 90-day range
        min_price = history_stats.get("min_price")
        max_price = history_stats.get("max_price")
        current_price = current_price_data.get("price") if current_price_data else None

        range_ratio: Optional[float] = None
        if min_price is not None and max_price is not None and current_price is not None:
            if max_price != min_price:
                range_ratio = (current_price - min_price) / (max_price - min_price)
            else:
                range_ratio = 0.5   # flat range — treat as neutral mid-point

        if range_ratio is None:
            none_count += 1
            range_score = 4         # 50% of 8
        elif range_ratio < 0.3:
            range_score = 8
        elif range_ratio < 0.5:
            range_score = 5
        elif range_ratio < 0.7:
            range_score = 3
        else:
            range_score = 1

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
                "score": payout_score,
                "max": 16,
            },
            "yield_vs_market": {
                "value": round(div_yield, 4) if div_yield is not None else None,
                "score": yield_score,
                "max": 14,
            },
            "fcf_coverage": {
                "value": free_cash_flow,
                "score": fcf_score,
                "max": 10,
            },
            "debt_safety": {
                "value": debt_to_equity,
                "score": debt_score,
                "max": 16,
            },
            "dividend_consistency": {
                "value": div_years,
                "score": consistency_score,
                "max": 14,
            },
            "volatility_score": {
                "value": volatility,
                "score": vol_score,
                "max": 10,
            },
            "price_momentum": {
                "value": price_change_pct,
                "score": momentum_score,
                "max": 12,
            },
            "price_range_position": {
                "value": round(range_ratio, 4) if range_ratio is not None else None,
                "score": range_score,
                "max": 8,
            },
        }

        return ScoreResult(
            ticker=ticker,
            asset_class=asset_class,
            valuation_yield_score=float(valuation_yield_score),
            financial_durability_score=float(financial_durability_score),
            technical_entry_score=float(technical_entry_score),
            total_score_raw=total_score_raw,
            nav_erosion_penalty=0.0,    # applied externally for covered call ETFs
            total_score=total_score_raw,
            grade=grade,
            recommendation=recommendation,
            factor_details=factor_details,
            data_quality_score=data_quality_score,
            data_completeness_pct=data_completeness_pct,
        )

    # ------------------------------------------------------------------
    # Classification helpers (static so API layer can call them post-penalty)
    # ------------------------------------------------------------------

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
