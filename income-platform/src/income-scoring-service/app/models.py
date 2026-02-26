"""
Agent 03 — Income Scoring Service
ORM Models: SQLAlchemy table definitions.

Tables:
  - income_scores          — scored results per ticker per run
  - quality_gate_results   — binary pass/fail gate checks
  - scoring_runs           — audit log of each scoring batch
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Text, JSON, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
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
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)       # cache expiry
    scoring_run_id = Column(UUID(as_uuid=True), ForeignKey("scoring_runs.id"), nullable=True)

    __table_args__ = (
        Index("ix_qg_ticker_evaluated", "ticker", "evaluated_at"),
        {"schema": None},  # resolved by search_path
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
    scored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)
    scoring_run_id = Column(UUID(as_uuid=True), ForeignKey("scoring_runs.id"), nullable=True)
    quality_gate_id = Column(UUID(as_uuid=True), ForeignKey("quality_gate_results.id"), nullable=True)

    __table_args__ = (
        Index("ix_income_scores_ticker_scored", "ticker", "scored_at"),
        Index("ix_income_scores_recommendation", "recommendation"),
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
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
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
    )

    def __repr__(self):
        return (
            f"<ScoringRun {self.id} [{self.run_type}] "
            f"status={self.status} scored={self.tickers_scored}>"
        )
