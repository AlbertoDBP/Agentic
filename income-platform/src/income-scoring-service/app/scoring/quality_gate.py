"""
Agent 03 — Income Scoring Service
Quality Gate Engine: Binary pass/fail evaluation per asset class.

Capital preservation first. A FAIL here is an absolute VETO —
the ticker never reaches the scoring engine regardless of yield.

Asset classes supported:
  - DIVIDEND_STOCK  : credit rating + FCF + dividend history
  - COVERED_CALL_ETF: AUM + track record + distribution history
  - BOND            : credit rating + duration + issuer type
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────────

class AssetClass(str, Enum):
    DIVIDEND_STOCK = "DIVIDEND_STOCK"
    COVERED_CALL_ETF = "COVERED_CALL_ETF"
    BOND = "BOND"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ── Credit rating ordering ────────────────────────────────────────────────────

CREDIT_RATING_ORDER = [
    "AAA", "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",   # ← minimum acceptable (investment grade floor)
    "BB+", "BB", "BB-",      # ← below this: FAIL
    "B+", "B", "B-",
    "CCC+", "CCC", "CCC-",
    "CC", "C", "D",
]

def credit_rating_meets_minimum(rating: str, minimum: str = "BBB-") -> bool:
    """Return True if rating is at or above the minimum threshold."""
    if not rating:
        return False
    rating_upper = rating.upper().strip()
    minimum_upper = minimum.upper().strip()
    try:
        rating_idx = CREDIT_RATING_ORDER.index(rating_upper)
        minimum_idx = CREDIT_RATING_ORDER.index(minimum_upper)
        return rating_idx <= minimum_idx   # lower index = better rating
    except ValueError:
        logger.warning(f"Unknown credit rating: {rating!r}")
        return False


# ── Input / Output dataclasses ────────────────────────────────────────────────

@dataclass
class DividendStockGateInput:
    ticker: str
    credit_rating: Optional[str] = None
    consecutive_positive_fcf_years: Optional[int] = None
    dividend_history_years: Optional[int] = None
    # Optional enrichment
    payout_ratio: Optional[float] = None
    debt_to_ebitda: Optional[float] = None


@dataclass
class CoveredCallETFGateInput:
    ticker: str
    aum_millions: Optional[float] = None
    track_record_years: Optional[float] = None
    distribution_history_months: Optional[int] = None
    underlying_index: Optional[str] = None
    expense_ratio: Optional[float] = None


@dataclass
class BondGateInput:
    ticker: str
    credit_rating: Optional[str] = None
    duration_years: Optional[float] = None
    issuer_type: Optional[str] = None      # GOVERNMENT | CORPORATE | MUNICIPAL
    yield_to_maturity: Optional[float] = None
    years_to_maturity: Optional[float] = None


@dataclass
class GateResult:
    ticker: str
    asset_class: AssetClass
    status: GateStatus
    passed: bool
    fail_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Raw check outcomes (stored for audit)
    checks: dict = field(default_factory=dict)

    # Metadata
    data_quality_score: float = 100.0      # drops when fields are missing
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: datetime = None

    def __post_init__(self):
        if self.valid_until is None:
            self.valid_until = self.evaluated_at + timedelta(
                seconds=settings.cache_ttl_quality_gate
            )


# ── Quality Gate Engine ───────────────────────────────────────────────────────

class QualityGateEngine:
    """
    Evaluates whether a ticker meets minimum income investment standards.

    Rules are strict by design — the Income Fortress methodology prioritises
    capital safety above yield generation.
    """

    def evaluate_dividend_stock(self, data: DividendStockGateInput) -> GateResult:
        """
        Quality gate for dividend-paying stocks.

        Checks:
          1. Credit rating ≥ BBB- (investment grade)
          2. Positive FCF for ≥ 3 consecutive years
          3. Dividend maintained/grown for ≥ 10 years
        """
        fail_reasons = []
        warnings = []
        checks = {}
        missing_fields = 0
        total_fields = 3

        # ── Check 1: Credit rating ────────────────────────────────────────────
        if data.credit_rating is None:
            missing_fields += 1
            checks["credit_rating"] = {"passed": None, "reason": "data_missing"}
            warnings.append("Credit rating unavailable — check skipped")
        else:
            passed = credit_rating_meets_minimum(
                data.credit_rating, settings.min_credit_rating
            )
            checks["credit_rating"] = {
                "value": data.credit_rating,
                "minimum": settings.min_credit_rating,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Credit rating {data.credit_rating} below minimum {settings.min_credit_rating}"
                )

        # ── Check 2: Consecutive positive FCF ────────────────────────────────
        if data.consecutive_positive_fcf_years is None:
            missing_fields += 1
            checks["fcf"] = {"passed": None, "reason": "data_missing"}
            warnings.append("FCF history unavailable — check skipped")
        else:
            passed = data.consecutive_positive_fcf_years >= settings.min_consecutive_fcf_years
            checks["fcf"] = {
                "value": data.consecutive_positive_fcf_years,
                "minimum": settings.min_consecutive_fcf_years,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Only {data.consecutive_positive_fcf_years} years positive FCF "
                    f"(need {settings.min_consecutive_fcf_years})"
                )

        # ── Check 3: Dividend history ─────────────────────────────────────────
        if data.dividend_history_years is None:
            missing_fields += 1
            checks["dividend_history"] = {"passed": None, "reason": "data_missing"}
            warnings.append("Dividend history unavailable — check skipped")
        else:
            passed = data.dividend_history_years >= settings.min_dividend_history_years
            checks["dividend_history"] = {
                "value": data.dividend_history_years,
                "minimum": settings.min_dividend_history_years,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Only {data.dividend_history_years} years dividend history "
                    f"(need {settings.min_dividend_history_years})"
                )

        # ── Data quality score ────────────────────────────────────────────────
        data_quality = round((1 - missing_fields / total_fields) * 100, 1)

        # Insufficient data → cannot evaluate (not a FAIL, but not a PASS)
        if missing_fields == total_fields:
            return GateResult(
                ticker=data.ticker,
                asset_class=AssetClass.DIVIDEND_STOCK,
                status=GateStatus.INSUFFICIENT_DATA,
                passed=False,
                fail_reasons=["All required fields missing — cannot evaluate"],
                warnings=warnings,
                checks=checks,
                data_quality_score=data_quality,
            )

        gate_passed = len(fail_reasons) == 0
        return GateResult(
            ticker=data.ticker,
            asset_class=AssetClass.DIVIDEND_STOCK,
            status=GateStatus.PASS if gate_passed else GateStatus.FAIL,
            passed=gate_passed,
            fail_reasons=fail_reasons,
            warnings=warnings,
            checks=checks,
            data_quality_score=data_quality,
        )

    def evaluate_covered_call_etf(self, data: CoveredCallETFGateInput) -> GateResult:
        """
        Quality gate for covered call ETFs.

        Checks:
          1. AUM ≥ $500M (liquidity / survivorship floor)
          2. Track record ≥ 3 years (enough NAV history for Monte Carlo)
          3. Distribution history ≥ 12 months (pattern established)
        """
        fail_reasons = []
        warnings = []
        checks = {}
        missing_fields = 0
        total_fields = 3

        # ── Check 1: AUM ──────────────────────────────────────────────────────
        if data.aum_millions is None:
            missing_fields += 1
            checks["aum"] = {"passed": None, "reason": "data_missing"}
            warnings.append("AUM unavailable — check skipped")
        else:
            passed = data.aum_millions >= settings.min_etf_aum_millions
            checks["aum"] = {
                "value_millions": data.aum_millions,
                "minimum_millions": settings.min_etf_aum_millions,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"AUM ${data.aum_millions:.0f}M below minimum "
                    f"${settings.min_etf_aum_millions:.0f}M"
                )

        # ── Check 2: Track record ─────────────────────────────────────────────
        if data.track_record_years is None:
            missing_fields += 1
            checks["track_record"] = {"passed": None, "reason": "data_missing"}
            warnings.append("Track record unavailable — check skipped")
        else:
            passed = data.track_record_years >= settings.min_etf_track_record_years
            checks["track_record"] = {
                "value_years": data.track_record_years,
                "minimum_years": settings.min_etf_track_record_years,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Only {data.track_record_years:.1f} years track record "
                    f"(need {settings.min_etf_track_record_years})"
                )

        # ── Check 3: Distribution history ─────────────────────────────────────
        if data.distribution_history_months is None:
            missing_fields += 1
            checks["distribution_history"] = {"passed": None, "reason": "data_missing"}
            warnings.append("Distribution history unavailable — check skipped")
        else:
            passed = data.distribution_history_months >= 12
            checks["distribution_history"] = {
                "value_months": data.distribution_history_months,
                "minimum_months": 12,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Only {data.distribution_history_months} months distribution history (need 12)"
                )

        data_quality = round((1 - missing_fields / total_fields) * 100, 1)

        if missing_fields == total_fields:
            return GateResult(
                ticker=data.ticker,
                asset_class=AssetClass.COVERED_CALL_ETF,
                status=GateStatus.INSUFFICIENT_DATA,
                passed=False,
                fail_reasons=["All required fields missing — cannot evaluate"],
                warnings=warnings,
                checks=checks,
                data_quality_score=data_quality,
            )

        gate_passed = len(fail_reasons) == 0
        return GateResult(
            ticker=data.ticker,
            asset_class=AssetClass.COVERED_CALL_ETF,
            status=GateStatus.PASS if gate_passed else GateStatus.FAIL,
            passed=gate_passed,
            fail_reasons=fail_reasons,
            warnings=warnings,
            checks=checks,
            data_quality_score=data_quality,
        )

    def evaluate_bond(self, data: BondGateInput) -> GateResult:
        """
        Quality gate for bonds.

        Checks:
          1. Credit rating ≥ BBB- (investment grade only)
          2. Duration ≤ 15 years (avoid excessive rate sensitivity)
          3. Not in default / distressed category
        """
        fail_reasons = []
        warnings = []
        checks = {}
        missing_fields = 0
        total_fields = 2   # credit + duration (issuer type is enrichment only)

        # ── Check 1: Credit rating ────────────────────────────────────────────
        if data.credit_rating is None:
            missing_fields += 1
            checks["credit_rating"] = {"passed": None, "reason": "data_missing"}
            warnings.append("Credit rating unavailable — check skipped")
        else:
            passed = credit_rating_meets_minimum(
                data.credit_rating, settings.min_credit_rating
            )
            checks["credit_rating"] = {
                "value": data.credit_rating,
                "minimum": settings.min_credit_rating,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Bond credit rating {data.credit_rating} below minimum {settings.min_credit_rating}"
                )

        # ── Check 2: Duration ─────────────────────────────────────────────────
        max_duration = 15.0
        if data.duration_years is None:
            missing_fields += 1
            checks["duration"] = {"passed": None, "reason": "data_missing"}
            warnings.append("Duration unavailable — check skipped")
        else:
            passed = data.duration_years <= max_duration
            checks["duration"] = {
                "value_years": data.duration_years,
                "maximum_years": max_duration,
                "passed": passed,
            }
            if not passed:
                fail_reasons.append(
                    f"Duration {data.duration_years:.1f}y exceeds maximum {max_duration}y"
                )

        # ── Enrichment: issuer type warning ───────────────────────────────────
        if data.issuer_type == "CORPORATE":
            warnings.append("Corporate bond — verify spread vs comparable Treasury")

        data_quality = round((1 - missing_fields / total_fields) * 100, 1)

        if missing_fields == total_fields:
            return GateResult(
                ticker=data.ticker,
                asset_class=AssetClass.BOND,
                status=GateStatus.INSUFFICIENT_DATA,
                passed=False,
                fail_reasons=["All required fields missing — cannot evaluate"],
                warnings=warnings,
                checks=checks,
                data_quality_score=data_quality,
            )

        gate_passed = len(fail_reasons) == 0
        return GateResult(
            ticker=data.ticker,
            asset_class=AssetClass.BOND,
            status=GateStatus.PASS if gate_passed else GateStatus.FAIL,
            passed=gate_passed,
            fail_reasons=fail_reasons,
            warnings=warnings,
            checks=checks,
            data_quality_score=data_quality,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
quality_gate_engine = QualityGateEngine()
