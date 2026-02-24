"""
Agent 02 — Newsletter Ingestion Service
Schemas: Pydantic models for API request/response validation

Separate from SQLAlchemy models — these define the API contract,
not the database structure.
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class RecommendationLabel(str, Enum):
    STRONG_BUY  = "StrongBuy"
    BUY         = "Buy"
    HOLD        = "Hold"
    SELL        = "Sell"
    STRONG_SELL = "StrongSell"


class AssetClass(str, Enum):
    COMMON_STOCK = "CommonStock"
    REIT         = "REIT"
    MLP          = "MLP"
    BDC          = "BDC"
    PREFERRED    = "Preferred"
    CEF          = "CEF"
    ETF          = "ETF"


class PhilosophySource(str, Enum):
    LLM    = "llm"
    KMEANS = "kmeans"


class PlatformAlignment(str, Enum):
    ALIGNED   = "Aligned"
    PARTIAL   = "Partial"
    DIVERGENT = "Divergent"
    VETOED    = "Vetoed"


class OutcomeLabel(str, Enum):
    CORRECT       = "Correct"
    INCORRECT     = "Incorrect"
    PARTIAL       = "Partial"
    INCONCLUSIVE  = "Inconclusive"


# ── Analyst Schemas ───────────────────────────────────────────────────────────

class AnalystCreate(BaseModel):
    """Request body for POST /analysts — add new analyst by SA Publishing ID."""
    sa_publishing_id: str = Field(..., min_length=1, max_length=100)
    display_name: str     = Field(..., min_length=1, max_length=200)
    config: Optional[dict] = None


class AnalystResponse(BaseModel):
    """Response for GET /analysts and GET /analysts/{id}."""
    id: int
    sa_publishing_id: str
    display_name: str
    is_active: bool
    philosophy_cluster: Optional[int]
    philosophy_summary: Optional[str]
    philosophy_source: PhilosophySource
    philosophy_tags: Optional[dict]
    overall_accuracy: Optional[Decimal]
    sector_alpha: Optional[dict]
    article_count: int
    last_article_fetched_at: Optional[datetime]
    last_backtest_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnalystListResponse(BaseModel):
    analysts: List[AnalystResponse]
    total: int


# ── Recommendation Schemas ────────────────────────────────────────────────────

class RecommendationResponse(BaseModel):
    """Single recommendation — used in lists and signal objects."""
    id: int
    analyst_id: int
    ticker: str
    sector: Optional[str]
    asset_class: Optional[AssetClass]
    recommendation: Optional[RecommendationLabel]
    sentiment_score: Optional[Decimal]
    yield_at_publish: Optional[Decimal]
    payout_ratio: Optional[Decimal]
    dividend_cagr_3yr: Optional[Decimal]
    dividend_cagr_5yr: Optional[Decimal]
    safety_grade: Optional[str]
    source_reliability: Optional[str]
    metadata: Optional[dict]
    published_at: datetime
    expires_at: datetime
    decay_weight: Decimal
    is_active: bool
    superseded_by: Optional[int]
    platform_alignment: Optional[PlatformAlignment]
    platform_scored_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Consensus Schema ──────────────────────────────────────────────────────────

class ConsensusResponse(BaseModel):
    """Weighted consensus score for a ticker."""
    ticker: str
    score: Optional[Decimal] = Field(None, description="-1.0 to 1.0 weighted consensus")
    confidence: str           = Field(..., description="high|low|insufficient_data")
    n_analysts: int
    n_recommendations: int
    dominant_recommendation: Optional[RecommendationLabel]
    computed_at: datetime


# ── Analyst Signal Schema (consumed by Agent 12) ──────────────────────────────

class AnalystSignalRecommendation(BaseModel):
    """Recommendation subset embedded in the signal object."""
    id: int
    label: Optional[RecommendationLabel]
    sentiment_score: Optional[Decimal]
    yield_at_publish: Optional[Decimal]
    payout_ratio: Optional[Decimal]
    safety_grade: Optional[str]
    source_reliability: Optional[str]
    thesis_summary: Optional[str]   # extracted from metadata.bull_case + bear_case
    bull_case: Optional[str]
    bear_case: Optional[str]
    published_at: datetime
    decay_weight: Decimal


class AnalystSignalAnalyst(BaseModel):
    """Analyst context embedded in the signal object."""
    id: int
    display_name: str
    accuracy_overall: Optional[Decimal]
    sector_alpha: Optional[dict]
    philosophy_summary: Optional[str]
    philosophy_source: PhilosophySource
    philosophy_tags: Optional[dict]


class AnalystSignalResponse(BaseModel):
    """
    Complete proposal-ready signal for a ticker.
    Consumed by Agent 12 — Proposal Agent.
    """
    ticker: str
    asset_class: Optional[AssetClass]
    sector: Optional[str]
    signal_strength: str              # strong|moderate|weak|insufficient
    proposal_readiness: bool          # True if signal is fresh + analyst accuracy meets threshold
    analyst: AnalystSignalAnalyst
    recommendation: AnalystSignalRecommendation
    consensus: ConsensusResponse
    platform_alignment: Optional[PlatformAlignment]  # null until Agent 12 scores
    generated_at: datetime


# ── Health Schema ─────────────────────────────────────────────────────────────

class FlowStatus(BaseModel):
    last_run: Optional[datetime]
    last_run_status: Optional[str]   # success|failed|running
    next_scheduled: Optional[datetime]
    articles_processed_last_run: Optional[int]


class HealthResponse(BaseModel):
    status: str                       # healthy|degraded|unhealthy
    service: str
    version: str
    environment: str
    database: dict
    cache: dict
    harvester_flow: FlowStatus
    intelligence_flow: FlowStatus
    uptime_seconds: Optional[float]
    timestamp: datetime
