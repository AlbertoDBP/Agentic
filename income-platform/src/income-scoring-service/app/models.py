"""
Agent 03 — Income Scoring Service
ORM Models: SQLAlchemy table definitions.

Tables:
  - income_scores              — scored results per ticker per run
  - quality_gate_results       — binary pass/fail gate checks
  - scoring_runs               — audit log of each scoring batch
  - scoring_weight_profiles    — versioned class-specific pillar weights (v2.0)
  - weight_change_audit        — immutable log of weight changes (v2.0)
  - signal_penalty_config      — configurable signal penalty rules (v2.0)
  - signal_penalty_log         — audit log of per-score signal penalties (v2.0)
  - shadow_portfolio_entries   — learning loop: forward outcomes per scored ticker (v2.0)
  - weight_review_runs         — learning loop: quarterly weight adjustment log (v2.0)
  - classification_feedback    — detector confidence: Agent 04 accuracy tracking (v2.0 Phase 4)
  - classifier_accuracy_runs   — detector confidence: monthly rollup stats (v2.0 Phase 4)
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Text, JSON, ForeignKey, UniqueConstraint, Index, SmallInteger, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.database import Base


# ── Quality Gate Results ──────────────────────────────────────────────────────

class QualityGateResult(Base):
    """
    Binary pass/fail quality gate evaluation per ticker.

    The quality gate is VETO-power: a FAIL here means the ticker
    is excluded from scoring entirely regardless of other factors.
    Results cached for 24h (stable fundamentals don't change intraday).
    """
    __tablename__ = "quality_gate_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(30), nullable=False)  # DIVIDEND_STOCK | COVERED_CALL_ETF | BOND

    # Gate outcome
    passed = Column(Boolean, nullable=False)
    fail_reasons = Column(JSON, nullable=True)          # list of strings if failed

    # Gate checks (stored for transparency / audit)
    credit_rating = Column(String(10), nullable=True)
    credit_rating_passed = Column(Boolean, nullable=True)

    consecutive_fcf_years = Column(Integer, nullable=True)
    fcf_passed = Column(Boolean, nullable=True)

    dividend_history_years = Column(Integer, nullable=True)
    dividend_history_passed = Column(Boolean, nullable=True)

    # ETF-specific checks
    etf_aum_millions = Column(Float, nullable=True)
    etf_aum_passed = Column(Boolean, nullable=True)
    etf_track_record_years = Column(Float, nullable=True)
    etf_track_record_passed = Column(Boolean, nullable=True)

    # REIT-specific checks
    reit_coverage_ratio = Column(Float, nullable=True)
    reit_coverage_passed = Column(Boolean, nullable=True)

    # Metadata
    data_quality_score = Column(Float, nullable=True)  # 0-100 confidence
    evaluated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime, nullable=True)       # cache expiry
    scoring_run_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_runs.id"), nullable=True)

    __table_args__ = (
        Index("ix_qg_ticker_evaluated", "ticker", "evaluated_at"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"<QualityGateResult {self.ticker} [{self.asset_class}] {status}>"


# ── Income Scores ─────────────────────────────────────────────────────────────

class IncomeScore(Base):
    """
    Full income score for a ticker — only created if quality gate passed.

    Score breakdown:
      - valuation_yield_score    (0-40): yield attractiveness vs history/benchmarks
      - financial_durability_score (0-40): payout safety, debt, volatility
      - technical_entry_score    (0-20): RSI, support proximity
      ─────────────────────────────────
      - total_score              (0-100): sum of above
      - nav_erosion_penalty      (0-30): deducted for covered call ETFs

    Final score = total_score - nav_erosion_penalty (floor 0).
    """
    __tablename__ = "income_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(30), nullable=False)

    # ── Component scores ──────────────────────────────────────────────────────
    valuation_yield_score = Column(Float, nullable=False)        # 0-40
    financial_durability_score = Column(Float, nullable=False)   # 0-40
    technical_entry_score = Column(Float, nullable=False)        # 0-20

    total_score_raw = Column(Float, nullable=False)              # sum before penalty
    nav_erosion_penalty = Column(Float, nullable=False, default=0.0)  # 0-30
    total_score = Column(Float, nullable=False)                  # final adjusted score

    # ── Grade & recommendation ────────────────────────────────────────────────
    grade = Column(String(5), nullable=False)    # A+, A, B+, B, C, D, F
    recommendation = Column(String(20), nullable=False)  # AGGRESSIVE_BUY | ACCUMULATE | WATCH

    # ── Factor detail (stored for SHAP-style explainability) ─────────────────
    factor_details = Column(JSON, nullable=True)
    # Example:
    # {
    #   "yield_vs_5yr_avg": {"value": 1.15, "score": 18, "weight": 0.4},
    #   "yield_spread_vs_treasury": {"value": 3.2, "score": 14, "weight": 0.3},
    #   "payout_ratio": {"value": 0.62, "score": 20, "weight": 0.5},
    #   ...
    # }

    # ── NAV erosion detail (covered call ETFs only) ───────────────────────────
    nav_erosion_details = Column(JSON, nullable=True)
    # Example:
    # {
    #   "prob_erosion_gt_5pct": 0.45,
    #   "median_annual_nav_change_pct": -2.1,
    #   "risk_classification": "MODERATE",
    #   "penalty_applied": 10
    # }

    # ── Data quality ──────────────────────────────────────────────────────────
    data_quality_score = Column(Float, nullable=True)   # 0-100
    data_completeness_pct = Column(Float, nullable=True) # % of features populated

    # ── Metadata ──────────────────────────────────────────────────────────────
    scored_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime, nullable=True)
    scoring_run_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_runs.id"), nullable=True)
    quality_gate_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.quality_gate_results.id"), nullable=True)

    # ── v2.0 Adaptive Intelligence fields ────────────────────────────────────
    weight_profile_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=True)
    signal_penalty = Column(Float, nullable=False, default=0.0)          # points deducted
    signal_penalty_details = Column(JSONB, nullable=True)                # signal context dict

    # ── HHS / IES fields (v3.0) ───────────────────────────────────────────────
    hhs_score = Column(Float, nullable=True)
    income_pillar_score = Column(Float, nullable=True)
    durability_pillar_score = Column(Float, nullable=True)
    income_weight = Column(Float, nullable=True)
    durability_weight = Column(Float, nullable=True)
    unsafe_flag = Column(Boolean, nullable=True)           # None = not evaluated
    unsafe_threshold = Column(Integer, nullable=True, default=20)
    hhs_status = Column(String(20), nullable=True)         # STRONG|GOOD|WATCH|CONCERN|UNSAFE|INSUFFICIENT

    ies_score = Column(Float, nullable=True)
    ies_calculated = Column(Boolean, nullable=False, default=False)
    ies_blocked_reason = Column(String(30), nullable=True) # UNSAFE_FLAG|HHS_BELOW_THRESHOLD|INSUFFICIENT_DATA

    quality_gate_status = Column(String(20), nullable=True, default="PASS")
    quality_gate_reasons = Column(JSONB, nullable=True)
    hhs_commentary = Column(Text, nullable=True)           # persisted at score time

    __table_args__ = (
        Index("ix_income_scores_ticker_scored", "ticker", "scored_at"),
        Index("ix_income_scores_recommendation", "recommendation"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<IncomeScore {self.ticker} [{self.asset_class}] "
            f"score={self.total_score:.1f} grade={self.grade}>"
        )


# ── Scoring Runs ──────────────────────────────────────────────────────────────

class ScoringRun(Base):
    """
    Audit log for each scoring batch or individual scoring request.
    Provides traceability for all score generation.
    """
    __tablename__ = "scoring_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_type = Column(String(20), nullable=False)  # SINGLE | BATCH | SCHEDULED
    triggered_by = Column(String(50), nullable=True)  # user_id | scheduler | api

    # Run stats
    tickers_requested = Column(Integer, nullable=False, default=0)
    tickers_gate_passed = Column(Integer, nullable=False, default=0)
    tickers_gate_failed = Column(Integer, nullable=False, default=0)
    tickers_scored = Column(Integer, nullable=False, default=0)
    tickers_errored = Column(Integer, nullable=False, default=0)

    # Timing
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="RUNNING")  # RUNNING | COMPLETE | FAILED
    error_summary = Column(Text, nullable=True)

    # Config snapshot (for reproducibility)
    config_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_scoring_runs_started", "started_at"),
        Index("ix_scoring_runs_status", "status"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<ScoringRun {self.id} [{self.run_type}] "
            f"status={self.status} scored={self.tickers_scored}>"
        )


# ── v2.0: Scoring Weight Profiles ────────────────────────────────────────────

class ScoringWeightProfile(Base):
    """
    Versioned class-specific pillar weight profiles.

    Each asset class has exactly one active profile at any time.
    Pillar weights (yield + durability + technical) must sum to 100.
    Sub-weights within each pillar are stored as percentages summing to 100.

    The scorer computes sub-component ceiling as:
        ceiling = pillar_budget * sub_weight_pct / 100
    """
    __tablename__ = "scoring_weight_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class = Column(String(50), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    # Top-level pillar weights (integers summing to 100)
    weight_yield = Column(SmallInteger, nullable=False)
    weight_durability = Column(SmallInteger, nullable=False)
    weight_technical = Column(SmallInteger, nullable=False)

    # Sub-component weights within each pillar (JSON %, sum=100 per pillar)
    # e.g. {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25}
    yield_sub_weights = Column(JSONB, nullable=False)
    durability_sub_weights = Column(JSONB, nullable=False)
    technical_sub_weights = Column(JSONB, nullable=False)

    # Provenance
    source = Column(String(30), nullable=False, default="MANUAL")
    # MANUAL | LEARNING_LOOP | INITIAL_SEED
    benchmark_ticker = Column(String(20), nullable=True)
    change_reason = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime, nullable=True)
    superseded_at = Column(DateTime, nullable=True)
    superseded_by_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=True)

    __table_args__ = (
        Index("ix_swp_asset_class_history", "asset_class", "created_at"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        status = "ACTIVE" if self.is_active else "SUPERSEDED"
        return (
            f"<ScoringWeightProfile {self.asset_class} v{self.version} "
            f"[{status}] Y={self.weight_yield}/D={self.weight_durability}/T={self.weight_technical}>"
        )


# ── v2.0: Weight Change Audit ─────────────────────────────────────────────────

class WeightChangeAudit(Base):
    """
    Immutable audit log of every weight profile change.
    Created whenever a new ScoringWeightProfile version is activated.
    """
    __tablename__ = "weight_change_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class = Column(String(50), nullable=False, index=True)
    old_profile_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=True)
    new_profile_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=False)

    # Deltas (new - old)
    delta_weight_yield = Column(SmallInteger, nullable=True)
    delta_weight_durability = Column(SmallInteger, nullable=True)
    delta_weight_technical = Column(SmallInteger, nullable=True)

    # Why it changed
    trigger_type = Column(String(30), nullable=False)
    # MANUAL | QUARTERLY_REVIEW | CONVERGENCE_CLAMP | INITIAL_SEED
    trigger_details = Column(JSONB, nullable=True)

    changed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    changed_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_wca_asset_class_changed", "asset_class", "changed_at"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<WeightChangeAudit {self.asset_class} [{self.trigger_type}] "
            f"dY={self.delta_weight_yield} dD={self.delta_weight_durability} dT={self.delta_weight_technical}>"
        )


# ── v2.0: Signal Penalty Config ───────────────────────────────────────────────

class SignalPenaltyConfig(Base):
    """
    Configurable penalty rules for the signal penalty layer.
    Exactly one row is active at any time.

    Architecture constraint: bullish_strong_bonus_cap = 0.0 enforced in v2.0.
    Signals can only reduce scores, never inflate them.
    """
    __tablename__ = "signal_penalty_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)

    # Penalty amounts (score points on 0-100 scale)
    bearish_strong_penalty = Column(Numeric(4, 1), nullable=False, default=8.0)
    bearish_moderate_penalty = Column(Numeric(4, 1), nullable=False, default=5.0)
    bearish_weak_penalty = Column(Numeric(4, 1), nullable=False, default=2.0)
    bullish_strong_bonus_cap = Column(Numeric(4, 1), nullable=False, default=0.0)
    # Architecture constraint: always 0.0 in v2.0 risk-conservative mode

    # Applicability thresholds
    min_n_analysts = Column(Integer, nullable=False, default=1)
    min_decay_weight = Column(Numeric(5, 4), nullable=False, default=0.30)
    consensus_bearish_threshold = Column(Numeric(4, 3), nullable=False, default=-0.20)
    consensus_bullish_threshold = Column(Numeric(4, 3), nullable=False, default=0.20)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_spc_active", "is_active"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return (
            f"<SignalPenaltyConfig v{self.version} [{status}] "
            f"bearish_strong={self.bearish_strong_penalty}>"
        )


# ── v2.0: Signal Penalty Log ──────────────────────────────────────────────────

class SignalPenaltyLog(Base):
    """
    Immutable audit record for each signal penalty applied (or not) per score.

    One row is written per POST /scores/evaluate call — even when penalty=0.0.
    This allows analysis of how often signals are BEARISH, how often eligibility
    fails, and how much Agent 02 availability affects scoring.
    """
    __tablename__ = "signal_penalty_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    income_score_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.income_scores.id"), nullable=True)
    ticker = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(50), nullable=False)

    # Signal data from Agent 02 (null when agent02_available=False)
    signal_type = Column(String(20), nullable=False)        # BEARISH | NEUTRAL | BULLISH | INSUFFICIENT | UNAVAILABLE
    signal_strength = Column(String(20), nullable=True)     # strong | moderate | weak | insufficient
    consensus_score = Column(Numeric(5, 3), nullable=True)  # -1.000 to +1.000
    n_analysts = Column(Integer, nullable=True)
    decay_weight = Column(Numeric(5, 4), nullable=True)

    # Penalty computation
    penalty_applied = Column(Numeric(4, 1), nullable=False, default=0.0)
    score_before = Column(Float, nullable=False)
    score_after = Column(Float, nullable=False)
    eligible = Column(Boolean, nullable=False, default=False)

    # Context
    config_version = Column(Integer, nullable=True)         # SignalPenaltyConfig.version used
    agent02_available = Column(Boolean, nullable=False, default=True)

    logged_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_spl_ticker_logged", "ticker", "logged_at"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<SignalPenaltyLog {self.ticker} [{self.signal_type}] "
            f"penalty={self.penalty_applied} {self.score_before:.1f}→{self.score_after:.1f}>"
        )


# ── v2.0: Shadow Portfolio Entries ────────────────────────────────────────────

class ShadowPortfolioEntry(Base):
    """
    One entry per scored ticker where recommendation >= ACCUMULATE.

    The learning loop uses these to assess prediction accuracy after the hold
    period (default 90 days). Outcome label is populated by the
    populate-outcomes job once exit_date passes.

    Outcome labels:
      PENDING   — hold period not yet elapsed
      CORRECT   — actual_return_pct >= +5.0 (bullish call was right)
      INCORRECT — actual_return_pct <= -5.0 (bullish call was wrong)
      NEUTRAL   — return between -5% and +5% (inconclusive)
    """
    __tablename__ = "shadow_portfolio_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    income_score_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.income_scores.id"), nullable=True)
    ticker = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(50), nullable=False)
    weight_profile_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=True)

    # Score snapshot at entry
    entry_score = Column(Float, nullable=False)
    entry_grade = Column(String(5), nullable=False)
    entry_recommendation = Column(String(20), nullable=False)
    valuation_yield_score = Column(Float, nullable=False)
    financial_durability_score = Column(Float, nullable=False)
    technical_entry_score = Column(Float, nullable=False)

    # Entry price (from market data at scoring time)
    entry_price = Column(Float, nullable=True)
    entry_date = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    hold_period_days = Column(Integer, nullable=False, default=90)

    # ── v3.0: per-pillar entry-time capture ───────────────────────────────
    benchmark_ticker          = Column(String(20),  nullable=True)
    benchmark_entry_price     = Column(Float,        nullable=True)
    durability_score_at_entry = Column(Float,        nullable=True)
    income_ttm_at_entry       = Column(Float,        nullable=True)
    # hold_period_days set to 365 for new entries (longest pillar hold)

    # ── v3.0: Technical outcome (T+60) ───────────────────────────────────
    technical_exit_price            = Column(Float,       nullable=True)
    benchmark_exit_price            = Column(Float,       nullable=True)
    technical_return_pct            = Column(Float,       nullable=True)
    technical_benchmark_return_pct  = Column(Float,       nullable=True)
    technical_alpha_pct             = Column(Float,       nullable=True)
    technical_outcome_label         = Column(String(20),  nullable=True)
    # PENDING | CORRECT | INCORRECT | NEUTRAL
    technical_outcome_at            = Column(DateTime,    nullable=True)

    # ── v3.0: Income outcome (T+365) ─────────────────────────────────────
    income_ttm_at_exit    = Column(Float,       nullable=True)
    income_change_pct     = Column(Float,       nullable=True)
    income_outcome_label  = Column(String(20),  nullable=True)
    # PENDING | CORRECT | INCORRECT | NEUTRAL
    income_outcome_at     = Column(DateTime,    nullable=True)

    # ── v3.0: Durability outcome (T+365, derived from Income) ────────────
    durability_score_at_exit  = Column(Float,       nullable=True)
    durability_outcome_label  = Column(String(20),  nullable=True)
    # PENDING | CORRECT | INCORRECT | NEUTRAL
    durability_outcome_at     = Column(DateTime,    nullable=True)

    # Outcome (populated after hold period)
    exit_price = Column(Float, nullable=True)
    exit_date = Column(DateTime, nullable=True)
    actual_return_pct = Column(Float, nullable=True)
    outcome_label = Column(String(20), nullable=False, default="PENDING")
    # PENDING | CORRECT | INCORRECT | NEUTRAL
    outcome_populated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_spe_ticker_entry", "ticker", "entry_date"),
        Index("ix_spe_outcome_label", "outcome_label"),
        Index("ix_spe_asset_class", "asset_class"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<ShadowPortfolioEntry {self.ticker} [{self.asset_class}] "
            f"score={self.entry_score:.1f} outcome={self.outcome_label}>"
        )


# ── v2.0: Weight Review Runs ──────────────────────────────────────────────────

class WeightReviewRun(Base):
    """
    Audit record for each quarterly weight review attempt.

    Records whether weights were adjusted, how many outcomes were analyzed,
    what the proposed changes were, and why if the review was skipped.
    """
    __tablename__ = "weight_review_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class = Column(String(50), nullable=False, index=True)

    triggered_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    triggered_by = Column(String(100), nullable=True)
    pillar_reviewed = Column(String(30), nullable=True)
    # "technical" | "income_durability" | "all"

    status = Column(String(20), nullable=False, default="RUNNING")
    # RUNNING | COMPLETE | SKIPPED | FAILED

    # Inputs
    outcomes_analyzed = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    incorrect_count = Column(Integer, nullable=False, default=0)
    neutral_count = Column(Integer, nullable=False, default=0)

    # Before profile
    profile_before_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=True)
    weight_yield_before = Column(SmallInteger, nullable=True)
    weight_durability_before = Column(SmallInteger, nullable=True)
    weight_technical_before = Column(SmallInteger, nullable=True)

    # After profile (null if no change applied)
    profile_after_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.scoring_weight_profiles.id"), nullable=True)
    weight_yield_after = Column(SmallInteger, nullable=True)
    weight_durability_after = Column(SmallInteger, nullable=True)
    weight_technical_after = Column(SmallInteger, nullable=True)

    # Deltas (after - before)
    delta_yield = Column(SmallInteger, nullable=True)
    delta_durability = Column(SmallInteger, nullable=True)
    delta_technical = Column(SmallInteger, nullable=True)

    skip_reason = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_wrr_asset_class_triggered", "asset_class", "triggered_at"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<WeightReviewRun {self.asset_class} [{self.status}] "
            f"outcomes={self.outcomes_analyzed} dY={self.delta_yield}>"
        )


# ── v2.0 Phase 4: Classification Feedback ─────────────────────────────────────

class ClassificationFeedback(Base):
    """
    One row per POST /scores/evaluate call capturing how the asset class was
    determined — by Agent 04 auto-classify or by caller manual override.

    When classification_verify_overrides=True and source=MANUAL_OVERRIDE, the
    scoring service also calls Agent 04 to see what it would have said, allowing
    mismatch detection (is_mismatch=True when Agent 04 disagrees with the override).

    This data feeds monthly classifier accuracy rollups.
    """
    __tablename__ = "classification_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    income_score_id = Column(UUID(as_uuid=True), ForeignKey("platform_shared.income_scores.id"), nullable=True)
    ticker = Column(String(20), nullable=False, index=True)

    # What was actually used for scoring
    asset_class_used = Column(String(50), nullable=False)
    # How it was determined: AGENT04 (auto-classified) | MANUAL_OVERRIDE (caller provided)
    source = Column(String(20), nullable=False)

    # What Agent 04 said (null when not called — e.g. manual override without verify)
    agent04_class = Column(String(50), nullable=True)
    agent04_confidence = Column(Float, nullable=True)

    # Mismatch flag (populated when source=MANUAL_OVERRIDE and agent04_class is available)
    # True = Agent 04 disagreed with the manual override
    is_mismatch = Column(Boolean, nullable=True)

    captured_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_cf_ticker_captured", "ticker", "captured_at"),
        Index("ix_cf_source", "source"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        mismatch = f" MISMATCH({self.agent04_class})" if self.is_mismatch else ""
        return (
            f"<ClassificationFeedback {self.ticker} [{self.source}] "
            f"{self.asset_class_used}{mismatch}>"
        )


# ── v2.0 Phase 4: Classifier Accuracy Runs ────────────────────────────────────

class ClassifierAccuracyRun(Base):
    """
    Monthly rollup of Agent 04 classification accuracy per asset class.

    One row per (period_month, asset_class) computed by the monthly rollup job.
    Also includes an aggregate row where asset_class IS NULL covering all classes.

    Metrics:
      - agent04_trusted:   calls where source=AGENT04 (no override)
      - manual_overrides:  calls where source=MANUAL_OVERRIDE
      - mismatches:        overrides where Agent 04 disagreed (is_mismatch=True)
      - accuracy_rate:     agent04_trusted / total_calls
      - override_rate:     manual_overrides / total_calls
    """
    __tablename__ = "classifier_accuracy_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_month = Column(String(7), nullable=False)    # "YYYY-MM"
    asset_class = Column(String(50), nullable=True)     # null = all-classes aggregate

    total_calls = Column(Integer, nullable=False, default=0)
    agent04_trusted = Column(Integer, nullable=False, default=0)
    manual_overrides = Column(Integer, nullable=False, default=0)
    mismatches = Column(Integer, nullable=False, default=0)

    accuracy_rate = Column(Float, nullable=True)    # agent04_trusted / total_calls
    override_rate = Column(Float, nullable=True)    # manual_overrides / total_calls
    mismatch_rate = Column(Float, nullable=True)    # mismatches / manual_overrides

    computed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    computed_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_car_period_asset", "period_month", "asset_class"),
        {"schema": "platform_shared"},
    )

    def __repr__(self):
        return (
            f"<ClassifierAccuracyRun {self.period_month} [{self.asset_class or 'ALL'}] "
            f"trusted={self.agent04_trusted} overrides={self.manual_overrides} "
            f"accuracy={self.accuracy_rate:.2%}>"
            if self.accuracy_rate is not None
            else f"<ClassifierAccuracyRun {self.period_month} [{self.asset_class or 'ALL'}]>"
        )
