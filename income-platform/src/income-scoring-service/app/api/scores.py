"""
Agent 03 — Income Scoring Service
API: Scores endpoints — Phase 2 full implementation.

Endpoints:
  POST /scores/evaluate   — run quality gate + scoring, persist result
  GET  /scores/           — last 20 scores (optional ?recommendation= filter)
  GET  /scores/{ticker}   — latest score for a ticker
"""
import asyncio
import logging
import time as _time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from sqlalchemy import text
from app.database import get_db, get_db_context
from app.models import IncomeScore, QualityGateResult, SignalPenaltyConfig, SignalPenaltyLog
from app.scoring import newsletter_client
from app.scoring.classification_client import get_asset_class as _classify_ticker
from app.scoring.shadow_portfolio import shadow_portfolio_manager
from app.scoring.classification_feedback import (
    classification_feedback_tracker,
    SOURCE_AGENT04,
    SOURCE_MANUAL,
)
from app.scoring.data_client import MarketDataClient
from app.scoring.income_scorer import IncomeScorer, ScoreResult
from app.scoring.nav_erosion import NAVErosionAnalyzer
from app.scoring.signal_penalty import SignalPenaltyEngine
from app.scoring.weight_profile_loader import weight_profile_loader
from app.scoring.quality_gate import (
    AssetClass,
    BondGateInput,
    CoveredCallETFGateInput,
    DividendStockGateInput,
    GateStatus,
    QualityGateEngine,
)

logger = logging.getLogger(__name__)

_HHS_UNSAFE_THRESHOLD = 20  # durability pillar ≤ this → UNSAFE flag

router          = APIRouter()
_scorer          = IncomeScorer()
_analyzer        = NAVErosionAnalyzer()
_gate            = QualityGateEngine()
_client          = MarketDataClient()
_penalty_engine  = SignalPenaltyEngine()


# ── Data Quality Gate helpers (Agent 14) ──────────────────────────────────────

async def _dq_gate_check(ticker: str) -> dict:
    """
    Check the data quality gate for a ticker before scoring.
    Returns {"status": "passed"|"blocked", "blocking_issue_count": N}.
    Falls through (returns passed) if gate service is unreachable.
    """
    if not settings.data_quality_gate_enabled:
        return {"status": "passed", "blocking_issue_count": 0}
    try:
        now = int(_time.time())
        token = jwt.encode(
            {"sub": "income-scoring", "iat": now, "exp": now + 60},
            settings.jwt_secret, algorithm="HS256",
        )
        async with httpx.AsyncClient(timeout=settings.data_quality_timeout) as client:
            resp = await client.get(
                f"{settings.data_quality_service_url}/data-quality/gate/symbol/{ticker}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Data quality gate unreachable for {ticker}: {e} — proceeding without gate")
    return {"status": "passed", "blocking_issue_count": 0}


async def _dq_mark_scoring_complete(ticker: str):
    """Notify agent-14 that scoring completed for this ticker."""
    try:
        now = int(_time.time())
        token = jwt.encode(
            {"sub": "income-scoring", "iat": now, "exp": now + 60},
            settings.jwt_secret, algorithm="HS256",
        )
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{settings.data_quality_service_url}/data-quality/gate/{ticker}/scoring-complete",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception:
        pass  # non-critical


# ── Pydantic request / response models ────────────────────────────────────────

class GateData(BaseModel):
    """Optional inline gate fields — mirrors QualityGateRequest (minus ticker/asset_class)."""
    credit_rating: Optional[str] = None
    consecutive_positive_fcf_years: Optional[int] = None
    dividend_history_years: Optional[int] = None
    aum_millions: Optional[float] = None
    track_record_years: Optional[float] = None
    distribution_history_months: Optional[int] = None
    duration_years: Optional[float] = None
    issuer_type: Optional[str] = None


class ScoreRequest(BaseModel):
    ticker: str
    asset_class: Optional[str] = None   # auto-resolved via Agent 04 if omitted
    gate_data: Optional[GateData] = None


class ScoreResponse(BaseModel):
    ticker: str
    asset_class: str
    valuation_yield_score: float
    financial_durability_score: float
    technical_entry_score: float
    total_score_raw: float
    nav_erosion_penalty: float
    total_score: float
    grade: str
    recommendation: str
    factor_details: dict
    nav_erosion_details: Optional[dict] = None
    chowder_number: Optional[float] = None
    chowder_signal: Optional[str] = None
    data_quality_score: float
    data_completeness_pct: float
    scored_at: datetime
    tax_efficiency: Optional[dict] = None   # populated by Agent 04; 0% composite weight
    # v2.0: weight profile provenance
    weight_profile_version: Optional[int] = None
    weight_profile_id: Optional[str] = None
    # v2.0: signal penalty layer
    signal_penalty: float = 0.0
    signal_penalty_details: Optional[dict] = None
    # v2.1: human-readable score explanation
    score_commentary: str = ""

    # ── HHS pillars (v3.0) ────────────────────────────────────────────────────
    hhs_score: Optional[float] = None
    income_pillar_score: Optional[float] = None
    durability_pillar_score: Optional[float] = None
    income_weight: Optional[float] = None
    durability_weight: Optional[float] = None
    unsafe_flag: Optional[bool] = None               # None = not evaluated
    unsafe_threshold: int = 20                        # snapshot of threshold at score time
    hhs_status: Optional[str] = None                 # STRONG|GOOD|WATCH|CONCERN|UNSAFE|INSUFFICIENT

    # ── IES ──────────────────────────────────────────────────────────────────
    ies_score: Optional[float] = None
    ies_calculated: bool = False
    ies_blocked_reason: Optional[str] = None         # UNSAFE_FLAG|HHS_BELOW_THRESHOLD|INSUFFICIENT_DATA

    # ── Quality gate surface ──────────────────────────────────────────────────
    quality_gate_status: str = "PASS"
    quality_gate_reasons: Optional[list] = None

    # ── HHS commentary ────────────────────────────────────────────────────────
    hhs_commentary: Optional[str] = None
    valid_until: Optional[datetime] = None            # expose for broker-service staleness check


class ScoreListItem(BaseModel):
    ticker: str
    asset_class: str
    total_score: float
    grade: str
    recommendation: str
    scored_at: datetime


# ── Internal helpers ───────────────────────────────────────────────────────────

_COMPONENT_LABELS = {
    "payout_sustainability": "payout sustainability",
    "yield_vs_market":       "yield vs market",
    "fcf_coverage":          "free cash flow coverage",
    "debt_safety":           "debt safety",
    "dividend_consistency":  "dividend consistency",
    "volatility_score":      "price volatility",
    "price_momentum":        "price momentum",
    "price_range_position":  "price range position",
}

_PILLAR_COMPONENTS = {
    "valuation & yield":    ["payout_sustainability", "yield_vs_market", "fcf_coverage"],
    "financial durability": ["debt_safety", "dividend_consistency", "volatility_score"],
    "technical entry":      ["price_momentum", "price_range_position"],
}


def _generate_commentary(
    factor_details: dict,
    signal_penalty: float,
    signal_penalty_details: Optional[dict],
    nav_erosion_penalty: float,
    nav_erosion_details: Optional[dict],
    total_score: float,
    grade: str,
    recommendation: str,
    chowder_signal: Optional[str],
    chowder_number: Optional[float],
    data_completeness_pct: float,
) -> str:
    """Generate a 2-3 sentence human-readable explanation of the score decision."""
    try:
        # Collect per-component (score, max, ratio) from factor_details
        components: dict[str, tuple[float, float, float]] = {}
        for key in _COMPONENT_LABELS:
            comp = factor_details.get(key)
            if isinstance(comp, dict):
                sc = float(comp.get("score", 0.0))
                mx = float(comp.get("max", 1.0) or 1.0)
                components[key] = (sc, mx, sc / mx)

        # Strongest / weakest by normalised ratio
        strongest = weakest = None
        if components:
            strongest = max(components, key=lambda k: components[k][2])
            weakest   = min(components, key=lambda k: components[k][2])

        # Leading pillar by raw score sum
        pillar_scores = {
            p: sum(components[k][0] for k in keys if k in components)
            for p, keys in _PILLAR_COMPONENTS.items()
        }
        leading_pillar = max(pillar_scores, key=pillar_scores.get) if pillar_scores else None

        # Sentence 1 — overall result + leading pillar
        rec_label = recommendation.replace("_", " ").title()
        s1 = f"Score {total_score:.0f} ({grade}) — {rec_label}."
        if leading_pillar:
            s1 += f" {leading_pillar.title()} leads this assessment."

        # Sentence 2 — strength and weakness
        s2 = ""
        if strongest and weakest and strongest != weakest:
            ss, sm, _ = components[strongest]
            ws, wm, _ = components[weakest]
            s2 = (
                f"Strongest driver: {_COMPONENT_LABELS[strongest]} ({ss:.1f}/{sm:.0f}); "
                f"weakest: {_COMPONENT_LABELS[weakest]} ({ws:.1f}/{wm:.0f})."
            )
        elif strongest:
            ss, sm, _ = components[strongest]
            s2 = f"Strongest driver: {_COMPONENT_LABELS[strongest]} ({ss:.1f}/{sm:.0f})."

        # Sentence 3 — penalties, chowder, data quality
        notes: list[str] = []
        if signal_penalty > 0:
            strength = (signal_penalty_details or {}).get("signal_strength", "")
            slabel = f"{strength.lower()} " if strength else ""
            notes.append(
                f"a {slabel}analyst BEARISH signal applied a {signal_penalty:.0f}-point penalty"
            )
        if nav_erosion_penalty > 0:
            risk = (nav_erosion_details or {}).get("risk_classification", "")
            notes.append(
                f"NAV erosion risk ({risk}) applied a {nav_erosion_penalty:.0f}-point penalty"
            )
        if chowder_signal and chowder_number is not None:
            notes.append(f"Chowder signal {chowder_signal} at {chowder_number:.1f}")
        if data_completeness_pct < 80.0:
            notes.append(f"data completeness {data_completeness_pct:.0f}% — score may be understated")

        s3 = ""
        if notes:
            s3 = notes[0].capitalize()
            for n in notes[1:]:
                s3 += "; " + n
            s3 += "."

        return " ".join(p for p in [s1, s2, s3] if p).strip()

    except Exception:
        return f"Score {total_score:.0f} ({grade}) — {recommendation.replace('_', ' ').title()}."


def _compute_hhs(result: ScoreResult, profile: dict, gate_status: str) -> dict:
    """Compute HHS score, pillar normalizations, and UNSAFE flag.

    gate_status: "PASS" (normal) or "INSUFFICIENT_DATA" (provisional pass —
    scoring proceeded but gate lacked data to fully evaluate).
    Hard-fail gates never reach this function (vetoed with HTTP 422 in evaluate_score).
    """
    provisional = gate_status == "INSUFFICIENT_DATA"

    wy = float(profile["weight_yield"])
    wd = float(profile["weight_durability"])

    # Normalize each pillar to 0–100 using its budget as the max; clamp to [0, 100]
    # valuation_yield_score includes yield_vs_market + payout_sustainability + fcf_coverage
    # financial_durability_score includes debt_safety + dividend_consistency + volatility_score
    inc_norm = max(0.0, min(100.0, round((result.valuation_yield_score / wy) * 100, 2))) if wy > 0 else 0.0
    dur_norm = max(0.0, min(100.0, round((result.financial_durability_score / wd) * 100, 2))) if wd > 0 else 0.0

    total_hhs_budget = wy + wd
    income_w = round(wy / total_hhs_budget, 4) if total_hhs_budget > 0 else 0.5
    dur_w = round(1.0 - income_w, 4)

    hhs = round((inc_norm * income_w) + (dur_norm * dur_w), 2)
    unsafe = dur_norm <= _HHS_UNSAFE_THRESHOLD

    if unsafe:
        hhs_status = "UNSAFE"
    elif hhs >= 85:
        hhs_status = "STRONG"
    elif hhs >= 70:
        hhs_status = "GOOD"
    elif hhs >= 50:
        hhs_status = "WATCH"
    else:
        hhs_status = "CONCERN"

    # Provisional: gate lacked data — score is computed but flagged
    if provisional:
        hhs_status = "~" + hhs_status

    return {
        "hhs_score": hhs,
        "income_pillar_score": inc_norm,
        "durability_pillar_score": dur_norm,
        "income_weight": income_w,
        "durability_weight": dur_w,
        "unsafe_flag": unsafe,
        "unsafe_threshold": _HHS_UNSAFE_THRESHOLD,
        "hhs_status": hhs_status,
    }


def _compute_ies_gate(result: ScoreResult, profile: dict, hhs_fields: dict) -> dict:
    """Compute IES (Income Entry Score) if HHS gate allows.

    IES = Valuation 60% + Technical 40% (fixed weights per HHS spec §4.2).
    Gate: hhs_score > 50 AND unsafe_flag is explicitly False (not None).
    """
    hhs_score = hhs_fields["hhs_score"]
    unsafe_flag = hhs_fields["unsafe_flag"]

    if hhs_score is not None and hhs_score > 50 and unsafe_flag is False:
        wy = float(profile["weight_yield"])
        wt = float(profile["weight_technical"])
        raw = result.valuation_yield_score * 0.60 + result.technical_entry_score * 0.40
        mx = wy * 0.60 + wt * 0.40
        ies = max(0.0, min(100.0, round((raw / mx) * 100, 2))) if mx > 0 else 0.0
        return {"ies_score": ies, "ies_calculated": True, "ies_blocked_reason": None}

    if hhs_score is None:
        reason = "INSUFFICIENT_DATA"
    elif unsafe_flag is True:
        reason = "UNSAFE_FLAG"
    else:
        reason = "HHS_BELOW_THRESHOLD"

    return {"ies_score": None, "ies_calculated": False, "ies_blocked_reason": reason}


def _generate_hhs_commentary(hhs_fields: dict, factor_details: dict, asset_class: str) -> Optional[str]:
    """Generate a plain-English HHS commentary referencing only INC/DUR pillars."""
    hhs_score = hhs_fields.get("hhs_score")
    if hhs_score is None:
        return None

    hhs_status = hhs_fields.get("hhs_status", "")
    inc = hhs_fields.get("income_pillar_score", 0)
    dur = hhs_fields.get("durability_pillar_score", 0)
    unsafe = hhs_fields.get("unsafe_flag", False)

    parts = []
    if unsafe:
        parts.append(f"UNSAFE: Durability pillar {dur:.0f}/100 is at or below the safety threshold.")
    else:
        parts.append(f"HHS {hhs_score:.0f} ({hhs_status}): Income {inc:.0f}/100 · Durability {dur:.0f}/100.")

    # Highlight weakest sub-component
    fd = factor_details or {}
    dur_factors = {k: v for k, v in fd.items() if k in ("debt_safety", "dividend_consistency", "volatility_score")}
    if dur_factors:
        weakest = min(dur_factors, key=lambda k: (dur_factors[k] or {}).get("score", 99))
        w_score = (dur_factors[weakest] or {}).get("score", 0)
        w_max = (dur_factors[weakest] or {}).get("max", 1)
        if w_max and (w_score / w_max) < 0.5:
            parts.append(f"Weakest durability factor: {weakest.replace('_', ' ')} ({w_score:.0f}/{w_max:.0f} pts).")

    return " ".join(parts)


def _orm_to_response(score: IncomeScore, tax_efficiency: Optional[dict] = None) -> ScoreResponse:
    fd = score.factor_details or {}
    sp = score.signal_penalty or 0.0
    nep = score.nav_erosion_penalty or 0.0
    dcp = score.data_completeness_pct or 0.0
    return ScoreResponse(
        ticker=score.ticker,
        asset_class=score.asset_class,
        valuation_yield_score=score.valuation_yield_score,
        financial_durability_score=score.financial_durability_score,
        technical_entry_score=score.technical_entry_score,
        total_score_raw=score.total_score_raw,
        nav_erosion_penalty=nep,
        total_score=score.total_score,
        grade=score.grade,
        recommendation=score.recommendation,
        factor_details=fd,
        nav_erosion_details=score.nav_erosion_details,
        chowder_number=fd.get("chowder_number"),
        chowder_signal=fd.get("chowder_signal"),
        data_quality_score=score.data_quality_score or 0.0,
        data_completeness_pct=dcp,
        scored_at=score.scored_at,
        tax_efficiency=tax_efficiency,
        weight_profile_version=None,   # not stored on ORM row in v2.0 (captured via FK)
        weight_profile_id=str(score.weight_profile_id) if score.weight_profile_id else None,
        signal_penalty=sp,
        signal_penalty_details=score.signal_penalty_details,
        score_commentary=_generate_commentary(
            factor_details=fd,
            signal_penalty=sp,
            signal_penalty_details=score.signal_penalty_details,
            nav_erosion_penalty=nep,
            nav_erosion_details=score.nav_erosion_details,
            total_score=score.total_score,
            grade=score.grade,
            recommendation=score.recommendation,
            chowder_signal=fd.get("chowder_signal"),
            chowder_number=fd.get("chowder_number"),
            data_completeness_pct=dcp,
        ),
        # HHS/IES fields (v3.0)
        hhs_score=score.hhs_score,
        income_pillar_score=score.income_pillar_score,
        durability_pillar_score=score.durability_pillar_score,
        income_weight=score.income_weight,
        durability_weight=score.durability_weight,
        unsafe_flag=score.unsafe_flag,
        unsafe_threshold=score.unsafe_threshold or 20,
        hhs_status=score.hhs_status,
        ies_score=score.ies_score,
        ies_calculated=score.ies_calculated or False,
        ies_blocked_reason=score.ies_blocked_reason,
        quality_gate_status=score.quality_gate_status or "PASS",
        quality_gate_reasons=score.quality_gate_reasons,
        hhs_commentary=score.hhs_commentary,
        valid_until=score.valid_until,
    )


def _result_to_response(
    result: ScoreResult,
    nav_erosion_details: Optional[dict],
    scored_at: datetime,
    tax_efficiency: Optional[dict] = None,
    signal_penalty: float = 0.0,
    signal_penalty_details: Optional[dict] = None,
) -> ScoreResponse:
    return ScoreResponse(
        ticker=result.ticker,
        asset_class=result.asset_class,
        valuation_yield_score=result.valuation_yield_score,
        financial_durability_score=result.financial_durability_score,
        technical_entry_score=result.technical_entry_score,
        total_score_raw=result.total_score_raw,
        nav_erosion_penalty=result.nav_erosion_penalty,
        total_score=result.total_score,
        grade=result.grade,
        recommendation=result.recommendation,
        factor_details=result.factor_details,
        nav_erosion_details=nav_erosion_details,
        chowder_number=result.chowder_number,
        chowder_signal=result.chowder_signal,
        data_quality_score=result.data_quality_score,
        data_completeness_pct=result.data_completeness_pct,
        scored_at=scored_at,
        tax_efficiency=tax_efficiency,
        weight_profile_version=result.weight_profile_version,
        weight_profile_id=result.weight_profile_id,
        signal_penalty=signal_penalty,
        signal_penalty_details=signal_penalty_details,
        score_commentary=_generate_commentary(
            factor_details=result.factor_details,
            signal_penalty=signal_penalty,
            signal_penalty_details=signal_penalty_details,
            nav_erosion_penalty=result.nav_erosion_penalty,
            nav_erosion_details=nav_erosion_details,
            total_score=result.total_score,
            grade=result.grade,
            recommendation=result.recommendation,
            chowder_signal=result.chowder_signal,
            chowder_number=result.chowder_number,
            data_completeness_pct=result.data_completeness_pct,
        ),
    )


async def _fetch_market_data(ticker: str, asset_class: str) -> dict:
    """Fetch all required market data from Agent 01 concurrently."""
    today      = date.today()
    start_date = (today - timedelta(days=settings.score_history_days)).isoformat()
    end_date   = today.isoformat()

    tasks: dict[str, object] = {
        "fundamentals":    _client.get_fundamentals(ticker),
        "dividend_history": _client.get_dividend_history(ticker),
        "history_stats":   _client.get_history_stats(ticker, start_date, end_date),
        "current_price":   _client.get_current_price(ticker),
        "features":        _client.get_features(ticker),
    }
    if asset_class in (AssetClass.COVERED_CALL_ETF, "COVERED_CALL_ETF"):
        tasks["etf_data"] = _client.get_etf_data(ticker)

    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
    market_data: dict = {}
    for key, res in zip(tasks.keys(), gathered):
        if isinstance(res, Exception):
            logger.warning("Failed to fetch %s for %s: %s", key, ticker, res)
            market_data[key] = [] if key == "dividend_history" else {}
        else:
            market_data[key] = res
    return market_data


def _run_gate_from_data(ticker: str, asset_class: str, gate_data: GateData):
    """Run quality gate using explicitly provided GateData fields.

    Returns a GateResult with dynamically attached ``dividend_history_years`` and
    ``consecutive_positive_fcf_years`` attributes so the scorer can read them.
    """
    ac = asset_class.upper()

    # Derive distribution_history_years from months (for income vehicle gates)
    dist_years: int | None = None
    if gate_data.distribution_history_months is not None:
        dist_years = gate_data.distribution_history_months // 12
    elif gate_data.dividend_history_years is not None:
        dist_years = gate_data.dividend_history_years

    if ac in (AssetClass.DIVIDEND_STOCK, "DIVIDEND_STOCK"):
        gate_result = _gate.evaluate_dividend_stock(DividendStockGateInput(
            ticker=ticker,
            credit_rating=gate_data.credit_rating,
            consecutive_positive_fcf_years=gate_data.consecutive_positive_fcf_years,
            dividend_history_years=gate_data.dividend_history_years,
        ))

    elif ac in (AssetClass.COVERED_CALL_ETF, "COVERED_CALL_ETF"):
        gate_result = _gate.evaluate_covered_call_etf(CoveredCallETFGateInput(
            ticker=ticker,
            aum_millions=gate_data.aum_millions,
            track_record_years=gate_data.track_record_years or (float(dist_years) if dist_years else None),
            distribution_history_months=gate_data.distribution_history_months,
        ))

    elif ac == "BDC":
        gate_result = _gate.evaluate_bdc(ticker, dist_years, gate_data.credit_rating)

    elif ac == "CEF":
        gate_result = _gate.evaluate_cef(ticker, dist_years, gate_data.credit_rating)

    elif ac in ("MORTGAGE_REIT", "MORTGAGE REIT"):
        gate_result = _gate.evaluate_mortgage_reit(ticker, dist_years, gate_data.credit_rating)

    elif ac in ("EQUITY_REIT", "REIT"):
        gate_result = _gate.evaluate_equity_reit(ticker, dist_years, gate_data.credit_rating)

    elif ac == "MLP":
        gate_result = _gate.evaluate_mlp(ticker, dist_years, gate_data.credit_rating)

    elif ac in ("PREFERRED_STOCK", "PREFERRED"):
        gate_result = _gate.evaluate_preferred(ticker, dist_years, gate_data.credit_rating)

    elif ac in (AssetClass.BOND, "BOND"):
        gate_result = _gate.evaluate_bond(BondGateInput(
            ticker=ticker,
            credit_rating=gate_data.credit_rating,
            duration_years=gate_data.duration_years,
            issuer_type=gate_data.issuer_type,
        ))

    else:
        # Unknown asset class — use bond gate as conservative fallback
        logger.warning("No gate defined for asset_class=%s (%s) — falling back to bond gate", ac, ticker)
        gate_result = _gate.evaluate_bond(BondGateInput(
            ticker=ticker,
            credit_rating=gate_data.credit_rating,
            duration_years=gate_data.duration_years,
            issuer_type=gate_data.issuer_type,
        ))

    # Attach for scorer consumption via getattr
    gate_result.dividend_history_years = gate_data.dividend_history_years or dist_years
    gate_result.consecutive_positive_fcf_years = gate_data.consecutive_positive_fcf_years
    return gate_result


def _persist_gate_result(db: Session, gate_result, asset_class: str):
    """Persist a GateResult dataclass to the database.

    Returns the saved ORM QualityGateResult (with .id set) or None on failure.
    """
    checks = gate_result.checks
    now = gate_result.evaluated_at
    try:
        db_gate = QualityGateResult(
            ticker=gate_result.ticker,
            asset_class=asset_class.upper(),
            passed=gate_result.passed,
            fail_reasons=gate_result.fail_reasons or [],
            credit_rating=checks.get("credit_rating", {}).get("value"),
            credit_rating_passed=checks.get("credit_rating", {}).get("passed"),
            consecutive_fcf_years=checks.get("fcf", {}).get("value"),
            fcf_passed=checks.get("fcf", {}).get("passed"),
            dividend_history_years=checks.get("dividend_history", {}).get("value"),
            dividend_history_passed=checks.get("dividend_history", {}).get("passed"),
            etf_aum_millions=checks.get("aum", {}).get("value_millions"),
            etf_aum_passed=checks.get("aum", {}).get("passed"),
            etf_track_record_years=checks.get("track_record", {}).get("value_years"),
            etf_track_record_passed=checks.get("track_record", {}).get("passed"),
            data_quality_score=gate_result.data_quality_score,
            evaluated_at=now,
            valid_until=gate_result.valid_until,
        )
        db.add(db_gate)
        db.commit()
        db.refresh(db_gate)
        return db_gate
    except Exception as e:
        db.rollback()
        logger.warning("Failed to persist inline gate result for %s: %s", gate_result.ticker, e)
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ScoreListItem])
def list_scores(
    recommendation: Optional[str] = Query(None, description="Filter by recommendation"),
    db: Session = Depends(get_db),
):
    """Return the last 20 income scores, optionally filtered by recommendation."""
    query = db.query(IncomeScore).order_by(IncomeScore.scored_at.desc())
    if recommendation:
        query = query.filter(IncomeScore.recommendation == recommendation.upper())
    scores = query.limit(20).all()
    return [
        ScoreListItem(
            ticker=s.ticker,
            asset_class=s.asset_class,
            total_score=s.total_score,
            grade=s.grade,
            recommendation=s.recommendation,
            scored_at=s.scored_at,
        )
        for s in scores
    ]


@router.post("/evaluate", response_model=ScoreResponse)
async def evaluate_score(req: ScoreRequest, db: Session = Depends(get_db)):
    """Score a ticker using quality gate + weighted scoring engine.

    Flow:
    1. Look up the latest passing quality gate result from DB (24-h cache hit).
    2. Fetch market data from Agent 01 concurrently.
    3. Gate resolution: DB hit → use it; no record + no gate_data → 422;
       gate_data provided → run inline gate, persist result, 422 if fails.
    4. Run the income scoring engine.
    5. Apply NAV erosion penalty for COVERED_CALL_ETF.
    6. Persist IncomeScore to DB.
    7. Return full score breakdown.
    """
    ticker     = req.ticker.upper()
    logger.debug("evaluate_score request: ticker=%s asset_class=%s gate_data=%s",
                 ticker, req.asset_class, req.gate_data)

    # 0. Auto-classify via Agent 04 if asset_class not provided
    tax_efficiency: Optional[dict] = None
    _feedback_source: str = SOURCE_AGENT04
    _feedback_agent04_class: Optional[str] = None
    if req.asset_class is None:
        resolved_class, tax_efficiency = await _classify_ticker(ticker)
        if resolved_class is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"asset_class not provided and Agent 04 (Asset Classification Service) "
                    f"could not classify {ticker}. Provide asset_class explicitly or ensure "
                    "Agent 04 is running."
                ),
            )
        asset_class = resolved_class.upper()
        _feedback_agent04_class = asset_class
        logger.info("Auto-classified %s → %s via Agent 04", ticker, asset_class)
    else:
        asset_class = req.asset_class.upper()
        _feedback_source = SOURCE_MANUAL
        # Optionally verify with Agent 04 to detect mismatches
        if settings.classification_verify_overrides:
            try:
                check_class, _ = await _classify_ticker(ticker)
                _feedback_agent04_class = check_class.upper() if check_class else None
            except Exception as _verify_exc:
                logger.debug("Agent 04 verify call failed for %s: %s", ticker, _verify_exc)

    # 1. Latest passing gate result from DB
    gate_db = (
        db.query(QualityGateResult)
        .filter(
            QualityGateResult.ticker == ticker,
            QualityGateResult.passed.is_(True),
        )
        .order_by(QualityGateResult.evaluated_at.desc())
        .first()
    )

    # 2. Fetch market data concurrently
    try:
        market_data = await _fetch_market_data(ticker, asset_class)
    except Exception as e:
        logger.error("Failed to fetch market data for %s: %s", ticker, e)
        market_data = {}

    # 3. Gate resolution: DB hit → use it; no record + no gate_data → provisional proxy
    gate_proxy = gate_db
    if gate_proxy is None:
        if req.gate_data is None:
            # No gate record and no inline data.
            # Derive gate inputs from already-fetched market data and run the gate engine.
            div_history = market_data.get("dividend_history") or []
            derived_div_years: int | None = None
            if div_history:
                years = {
                    d["ex_date"][:4]
                    for d in div_history
                    if isinstance(d.get("ex_date"), str) and len(d["ex_date"]) >= 4
                }
                derived_div_years = len(years) if years else None

            fundamentals = market_data.get("fundamentals") or {}
            raw_fcf_years = fundamentals.get("consecutive_positive_fcf_years")
            derived_fcf_years: int | None = int(raw_fcf_years) if raw_fcf_years is not None else None

            # Preferred stock fallback: FMP/yfinance rarely cover preferred dividends.
            # If the ticker has a valid price in market_data_cache (e.g. from broker sync),
            # the preferred is actively trading and paying its stated contractual dividend.
            # Infer the minimum gate threshold rather than leaving it as INSUFFICIENT_DATA.
            if derived_div_years is None and asset_class.upper() in ("PREFERRED_STOCK", "PREFERRED"):
                try:
                    cache_row = db.execute(
                        text("SELECT price FROM platform_shared.market_data_cache WHERE symbol = :s AND price IS NOT NULL LIMIT 1"),
                        {"s": ticker},
                    ).fetchone()
                    if cache_row:
                        derived_div_years = 2   # minimum gate threshold; inferred from active price
                        logger.info(
                            "PREFERRED_STOCK %s: no dividend history from provider; "
                            "inferred div_years=2 from active market_data_cache price (contractual dividend)",
                            ticker,
                        )
                except Exception as _pref_exc:
                    logger.debug("PREFERRED_STOCK price cache check failed for %s: %s", ticker, _pref_exc)

            # BOND / CUSIP fallback: FMP does not support CUSIP lookup on our plan.
            # Use OpenFIGI (free, no key required) to resolve CUSIP → bond ticker string,
            # then parse the maturity date to derive duration_years for the bond gate.
            # Credit rating is left as None (gate skips that check rather than failing).
            import re as _re
            _CUSIP_RE = _re.compile(r"^[0-9]{2}[A-Z0-9]{7}$")
            derived_duration_years: float | None = None
            if asset_class.upper() == "BOND" and _CUSIP_RE.match(ticker):
                try:
                    import httpx as _httpx
                    async with _httpx.AsyncClient(timeout=5) as _figi_client:
                        _figi_resp = await _figi_client.post(
                            "https://api.openfigi.com/v3/mapping",
                            json=[{"idType": "ID_CUSIP", "idValue": ticker}],
                            headers={"Content-Type": "application/json"},
                        )
                    if _figi_resp.status_code == 200:
                        _figi_data = _figi_resp.json()
                        _bond_ticker = (_figi_data[0].get("data") or [{}])[0].get("ticker", "")
                        # bond_ticker format: "PSEC 3.437 10/15/28" or "HTGC 2 5/8 09/16/26"
                        _mat = _re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$", _bond_ticker)
                        if _mat:
                            from datetime import date as _date
                            _m, _d, _y = int(_mat.group(1)), int(_mat.group(2)), int(_mat.group(3))
                            _year = 2000 + _y if _y < 100 else _y
                            _maturity = _date(_year, _m, _d)
                            _days = (_maturity - _date.today()).days
                            derived_duration_years = max(0.0, round(_days / 365.25, 2))
                            logger.info(
                                "BOND CUSIP %s: OpenFIGI '%s' → maturity %s, duration=%.2fy",
                                ticker, _bond_ticker, _maturity, derived_duration_years,
                            )
                except Exception as _cusip_exc:
                    logger.warning("OpenFIGI CUSIP lookup failed for %s: %s", ticker, _cusip_exc)

            logger.info(
                "No gate record for %s (%s) — derived div_years=%s fcf_years=%s duration_years=%s; running gate",
                ticker, asset_class, derived_div_years, derived_fcf_years, derived_duration_years,
            )

            derived_gate_data = GateData(
                dividend_history_years=derived_div_years,
                consecutive_positive_fcf_years=derived_fcf_years,
                duration_years=derived_duration_years,
                # distribution_history_months derived inside _run_gate_from_data from dividend_history_years
            )
            try:
                derived_result = _run_gate_from_data(ticker, asset_class, derived_gate_data)
            except Exception as _ge:
                logger.warning("Derived gate run failed for %s: %s — falling back to INSUFFICIENT_DATA", ticker, _ge)
                derived_result = None

            if derived_result is not None:
                # Persist derived gate result so next scoring run can use it from DB
                gate_db = _persist_gate_result(db, derived_result, asset_class)
                gate_proxy = derived_result
            else:
                # Last resort fallback — should rarely happen
                gate_proxy = type("_ProvisionalGate", (), {
                    "status": GateStatus.INSUFFICIENT_DATA,
                    "passed": False,
                    "fail_reasons": ["Gate derivation failed — score is provisional"],
                    "id": None,
                    "dividend_history_years": derived_div_years,
                    "consecutive_positive_fcf_years": derived_fcf_years,
                })()
                gate_db = None
        else:
            pass  # fall through to inline gate evaluation below
    if gate_proxy is None and req.gate_data is not None:
        # Run gate inline from caller-supplied data
        try:
            inline_result = _run_gate_from_data(ticker, asset_class, req.gate_data)
        except Exception as e:
            logger.warning("Inline gate error for %s: %s", ticker, e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Quality gate evaluation error: {e}",
            )
        # Hard-veto only when gate actually found failing data.
        # INSUFFICIENT_DATA means we have no data to evaluate — treat as provisional pass
        # so income-specific classes (MORTGAGE_REIT, BDC, MLP, CEF, PREFERRED) can still score.
        if not inline_result.passed and inline_result.status != GateStatus.INSUFFICIENT_DATA:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": f"Quality gate failed for {ticker}",
                    "fail_reasons": inline_result.fail_reasons,
                },
            )
        # Persist the passing inline result; update gate_db so quality_gate_id is set
        gate_db = _persist_gate_result(db, inline_result, asset_class)
        gate_proxy = inline_result

    # 4. Load class-specific weight profile (v2.0) then score
    weight_profile = weight_profile_loader.get_active_profile(asset_class, db)
    logger.debug(
        "Weight profile for %s: v%s source=%s (Y=%s/D=%s/T=%s)",
        asset_class,
        weight_profile.get("version"),
        weight_profile.get("source"),
        weight_profile.get("weight_yield"),
        weight_profile.get("weight_durability"),
        weight_profile.get("weight_technical"),
    )

    try:
        result: ScoreResult = _scorer.score(
            ticker, asset_class, gate_proxy, market_data, weight_profile=weight_profile
        )
    except Exception as e:
        logger.error("Scoring engine error for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=f"Scoring engine error: {e}")

    # 5. NAV erosion penalty (covered call ETFs only)
    nav_erosion_details: Optional[dict] = None
    if asset_class in (AssetClass.COVERED_CALL_ETF, "COVERED_CALL_ETF"):
        try:
            erosion = _analyzer.analyze(ticker, market_data.get("history_stats") or {})
            result.nav_erosion_penalty = float(erosion.penalty)
            result.total_score        = max(0.0, result.total_score_raw - result.nav_erosion_penalty)
            result.grade              = IncomeScorer._grade(result.total_score)
            result.recommendation     = IncomeScorer._recommendation(result.total_score)
            nav_erosion_details = {
                "prob_erosion_gt_5pct":      erosion.prob_erosion_gt_5pct,
                "median_annual_nav_change_pct": erosion.median_annual_nav_change_pct,
                "risk_classification":       erosion.risk_classification,
                "penalty_applied":           erosion.penalty,
            }
        except Exception as e:
            logger.warning("NAV erosion analysis failed for %s: %s", ticker, e)

    # 5b. Signal penalty layer (v2.0 Phase 2) — non-blocking
    signal_penalty_amt = 0.0
    signal_penalty_details: Optional[dict] = None
    signal_config = None
    try:
        signal_config = (
            db.query(SignalPenaltyConfig)
            .filter(SignalPenaltyConfig.is_active.is_(True))
            .first()
        )
        if signal_config is not None:
            signal_response = await newsletter_client.fetch_signal(ticker)
            pr = _penalty_engine.compute(result.total_score, signal_response, signal_config)
            signal_penalty_amt = pr.penalty
            signal_penalty_details = pr.details
            if signal_penalty_amt > 0:
                result.total_score    = pr.score_after
                result.grade          = IncomeScorer._grade(result.total_score)
                result.recommendation = IncomeScorer._recommendation(result.total_score)
                logger.info(
                    "Signal penalty for %s: %s %s → %.1f pts deducted (%.1f → %.1f)",
                    ticker, pr.signal_type, pr.signal_strength,
                    signal_penalty_amt, pr.score_before, pr.score_after,
                )
        else:
            logger.warning("No active signal penalty config found — skipping signal layer for %s", ticker)
    except Exception as exc:
        logger.warning("Signal penalty layer error for %s: %s", ticker, exc)

    # 5c. HHS / IES computation
    _inline_status = getattr(gate_proxy, "status", None)
    _gate_status = (
        "INSUFFICIENT_DATA"
        if _inline_status == GateStatus.INSUFFICIENT_DATA
        else "PASS"
    )
    hhs_fields = _compute_hhs(result, weight_profile, _gate_status)
    ies_fields = _compute_ies_gate(result, weight_profile, hhs_fields)
    quality_gate_status_str = _gate_status
    quality_gate_reasons_list = getattr(gate_proxy, "fail_reasons", None) or []
    hhs_commentary_str = _generate_hhs_commentary(
        hhs_fields=hhs_fields,
        factor_details=result.factor_details or {},
        asset_class=asset_class,
    )

    # 6. Persist to DB
    now        = datetime.now(timezone.utc)
    valid_until = now + timedelta(seconds=settings.cache_ttl_score)
    quality_gate_id = getattr(gate_db, "id", None)

    # Resolve weight_profile_id UUID (only present when loaded from DB, not fallback)
    import uuid as _uuid
    _wp_id_raw = weight_profile.get("id")
    weight_profile_id = None
    if _wp_id_raw:
        try:
            weight_profile_id = _uuid.UUID(str(_wp_id_raw))
        except (ValueError, AttributeError):
            pass

    # Merge chowder_number / chowder_signal into factor_details so that
    # _orm_to_response (used by GET /scores/{ticker}) can retrieve them
    # when serving cached scores without re-running evaluate.
    _factor_details = dict(result.factor_details or {})
    _factor_details["chowder_number"] = result.chowder_number
    _factor_details["chowder_signal"] = result.chowder_signal

    db_score = IncomeScore(
        ticker=ticker,
        asset_class=asset_class,
        valuation_yield_score=result.valuation_yield_score,
        financial_durability_score=result.financial_durability_score,
        technical_entry_score=result.technical_entry_score,
        total_score_raw=result.total_score_raw,
        nav_erosion_penalty=result.nav_erosion_penalty,
        total_score=result.total_score,
        grade=result.grade,
        recommendation=result.recommendation,
        factor_details=_factor_details,
        nav_erosion_details=nav_erosion_details,
        data_quality_score=result.data_quality_score,
        data_completeness_pct=result.data_completeness_pct,
        scored_at=now,
        valid_until=valid_until,
        quality_gate_id=quality_gate_id,
        weight_profile_id=weight_profile_id,
        signal_penalty=signal_penalty_amt,
        signal_penalty_details=signal_penalty_details,
        hhs_score=hhs_fields["hhs_score"],
        income_pillar_score=hhs_fields["income_pillar_score"],
        durability_pillar_score=hhs_fields["durability_pillar_score"],
        income_weight=hhs_fields["income_weight"],
        durability_weight=hhs_fields["durability_weight"],
        unsafe_flag=hhs_fields["unsafe_flag"],
        unsafe_threshold=hhs_fields["unsafe_threshold"],
        hhs_status=hhs_fields["hhs_status"],
        ies_score=ies_fields["ies_score"],
        ies_calculated=ies_fields["ies_calculated"],
        ies_blocked_reason=ies_fields["ies_blocked_reason"],
        quality_gate_status=quality_gate_status_str,
        quality_gate_reasons=quality_gate_reasons_list or None,
        hhs_commentary=hhs_commentary_str,
    )
    try:
        db.add(db_score)
        db.flush()  # get db_score.id before writing the penalty log

        # 6b. Write signal_penalty_log row (one per evaluate call)
        if signal_config is not None:
            try:
                # Reconstruct PenaltyResult fields from details dict (or defaults)
                d = signal_penalty_details or {}
                spl = SignalPenaltyLog(
                    income_score_id=db_score.id,
                    ticker=ticker,
                    asset_class=asset_class,
                    signal_type=d.get("signal_type", "UNAVAILABLE"),
                    signal_strength=d.get("signal_strength"),
                    consensus_score=d.get("consensus_score"),
                    n_analysts=d.get("n_analysts", 0),
                    decay_weight=d.get("decay_weight"),
                    penalty_applied=signal_penalty_amt,
                    score_before=d.get("score_before", result.total_score),
                    score_after=d.get("score_after", result.total_score),
                    eligible=d.get("eligible", False),
                    config_version=signal_config.version,
                    agent02_available=d.get("signal_type") != "UNAVAILABLE",
                    logged_at=now,
                )
                db.add(spl)
            except Exception as log_exc:
                logger.warning("Failed to create signal_penalty_log for %s: %s", ticker, log_exc)

        # 6c. Shadow portfolio entry (v2.0 Phase 3 — non-blocking)
        try:
            entry_price = (
                (market_data.get("current_price") or {}).get("price")
                if market_data else None
            )
            shadow_portfolio_manager.maybe_record_entry(
                db,
                income_score_id=db_score.id,
                ticker=ticker,
                asset_class=asset_class,
                entry_score=result.total_score,
                entry_grade=result.grade,
                entry_recommendation=result.recommendation,
                valuation_yield_score=result.valuation_yield_score,
                financial_durability_score=result.financial_durability_score,
                technical_entry_score=result.technical_entry_score,
                weight_profile_id=weight_profile_id,
                entry_price=entry_price,
            )
        except Exception as spe:
            logger.warning("Shadow portfolio entry failed for %s: %s", ticker, spe)

        # 6d. Classification feedback (v2.0 Phase 4 — non-blocking)
        try:
            classification_feedback_tracker.record(
                db,
                income_score_id=db_score.id,
                ticker=ticker,
                asset_class_used=asset_class,
                source=_feedback_source,
                agent04_class=_feedback_agent04_class,
                agent04_confidence=None,  # confidence not exposed by get_asset_class currently
            )
        except Exception as cfe:
            logger.warning("Classification feedback recording failed for %s: %s", ticker, cfe)

        db.commit()
        db.refresh(db_score)
        try:
            return _orm_to_response(db_score, tax_efficiency=tax_efficiency)
        except Exception as ser_err:
            logger.error(
                "Response serialization error for %s (ORM path): %s | "
                "factor_details=%s chowder_number=%r chowder_signal=%r",
                ticker, ser_err,
                db_score.factor_details,
                db_score.factor_details.get("chowder_number") if db_score.factor_details else None,
                db_score.factor_details.get("chowder_signal") if db_score.factor_details else None,
            )
            raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to persist score for %s: %s", ticker, e)
        # Return the in-memory result so the caller still gets a useful response
        try:
            return _result_to_response(
                result, nav_erosion_details, now, tax_efficiency=tax_efficiency,
                signal_penalty=signal_penalty_amt, signal_penalty_details=signal_penalty_details,
            )
        except Exception as ser_err:
            logger.error(
                "Response serialization error for %s (in-memory path): %s | "
                "chowder_number=%r (%s) chowder_signal=%r",
                ticker, ser_err,
                result.chowder_number, type(result.chowder_number).__name__,
                result.chowder_signal,
            )
            raise


@router.post("/refresh-portfolio")
async def refresh_portfolio_scores(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Queue background scoring for all active portfolio positions.
    Called by the scheduler daily at 19:00 ET after market cache refresh.
    Returns immediately; scoring runs in background.
    """
    rows = db.execute(
        text(
            "SELECT DISTINCT symbol FROM platform_shared.positions "
            "WHERE status = 'ACTIVE'"
        )
    ).fetchall()
    tickers = [r[0].upper() for r in rows]

    async def _score_ticker(ticker: str) -> None:
        # ── DATA QUALITY GATE CHECK ──────────────────────────────────────────
        gate = await _dq_gate_check(ticker)
        if gate.get("status") != "passed":
            logger.warning(
                "Portfolio refresh: scoring BLOCKED by data quality gate for %s "
                "(%s critical issues)",
                ticker,
                gate.get("blocking_issue_count", "?"),
            )
            return
        # ── END GATE CHECK ────────────────────────────────────────────────────
        try:
            with get_db_context() as bg_db:
                await evaluate_score(ScoreRequest(ticker=ticker), bg_db)
            await _dq_mark_scoring_complete(ticker)
        except Exception as exc:
            logger.warning("Portfolio refresh: scoring failed for %s: %s", ticker, exc)

    for ticker in tickers:
        background_tasks.add_task(_score_ticker, ticker)

    logger.info("Portfolio refresh: queued scoring for %d tickers", len(tickers))
    return {"queued": len(tickers)}


@router.get("/{ticker}", response_model=ScoreResponse)
def get_score(ticker: str, db: Session = Depends(get_db)):
    """Return the latest income score for a ticker from the database."""
    ticker = ticker.upper()
    score = (
        db.query(IncomeScore)
        .filter(IncomeScore.ticker == ticker)
        .order_by(IncomeScore.scored_at.desc())
        .first()
    )
    if score is None:
        raise HTTPException(
            status_code=404,
            detail=f"No score found for {ticker}. Run POST /scores/evaluate first.",
        )
    return _orm_to_response(score)
