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
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
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

router          = APIRouter()
_scorer          = IncomeScorer()
_analyzer        = NAVErosionAnalyzer()
_gate            = QualityGateEngine()
_client          = MarketDataClient()
_penalty_engine  = SignalPenaltyEngine()


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

    Returns a GateResult with a dynamically attached ``dividend_history_years``
    attribute so the scorer can read it without caring about the object type.
    """
    ac = asset_class.upper()
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
            track_record_years=gate_data.track_record_years,
            distribution_history_months=gate_data.distribution_history_months,
        ))

    else:  # BOND or unknown
        gate_result = _gate.evaluate_bond(BondGateInput(
            ticker=ticker,
            credit_rating=gate_data.credit_rating,
            duration_years=gate_data.duration_years,
            issuer_type=gate_data.issuer_type,
        ))

    # Attach dividend_history_years so the scorer can read it via getattr
    gate_result.dividend_history_years = gate_data.dividend_history_years
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

    # 3. Gate resolution: DB hit → use it; no DB record → require gate_data or 422
    gate_proxy = gate_db
    if gate_proxy is None:
        if req.gate_data is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"No passing quality gate record found for {ticker}. "
                    "Run POST /quality-gate/evaluate first, or include gate data in this request."
                ),
            )
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
