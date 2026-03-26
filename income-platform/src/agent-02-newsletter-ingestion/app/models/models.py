"""
Agent 02 — Newsletter Ingestion Service
Models: SQLAlchemy ORM models for all 6 database tables

Tables:
  - analysts                  Analyst registry + philosophy + accuracy
  - analyst_articles          Raw ingested articles with embeddings
  - analyst_recommendations   Extracted structured recommendations
  - analyst_accuracy_log      Backtest outcomes for learning
  - proposals                 Agent 12 proposals (read/write shared)
  - credit_overrides          Manual safety grade overrides

pgvector columns use String(mapped to vector type via raw DDL migration).
The Vector() type is declared via migration — models use mapped_column
with a custom type for compatibility.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Numeric,
    TIMESTAMP, ARRAY, ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.database import Base


# ── Analysts ──────────────────────────────────────────────────────────────────

class Analyst(Base):
    """
    Analyst registry. One row per tracked SA analyst.
    Philosophy fields are populated by the Intelligence Flow.
    """
    __tablename__ = "analysts"
    __table_args__ = {"schema": "platform_shared"}

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    sa_publishing_id         = Column(String(100), unique=True, nullable=False, index=True)
    display_name             = Column(String(200), nullable=False)
    is_active                = Column(Boolean, default=True, nullable=False)

    # Philosophy — populated by Intelligence Flow
    philosophy_cluster       = Column(Integer, nullable=True)          # K-Means cluster ID
    philosophy_summary       = Column(Text, nullable=True)             # LLM-generated summary
    philosophy_source        = Column(String(10), default="llm")       # 'llm' | 'kmeans'
    philosophy_vector        = Column(Vector(1536), nullable=True)     # centroid embedding
    philosophy_tags          = Column(JSONB, nullable=True)            # {style, sectors, ...}

    # Accuracy — updated by Intelligence Flow backtest
    overall_accuracy         = Column(Numeric(5, 4), nullable=True)    # 0.0 - 1.0
    churn_rate               = Column(Numeric(5, 4), nullable=True)    # superseded/total recs ratio
    sector_alpha             = Column(JSONB, nullable=True)            # {REIT: 0.81, ...}
    article_count            = Column(Integer, default=0)
    last_article_fetched_at  = Column(TIMESTAMP(timezone=True), nullable=True)
    last_backtest_at         = Column(TIMESTAMP(timezone=True), nullable=True)

    # Per-analyst config overrides (null = use user_preferences defaults)
    config                   = Column(JSONB, nullable=True)            # {fetch_limit, aging_days}

    created_at               = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at               = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                                      onupdate=func.now())

    # Relationships
    articles        = relationship("AnalystArticle", back_populates="analyst")
    recommendations = relationship("AnalystRecommendation", back_populates="analyst")
    accuracy_logs   = relationship("AnalystAccuracyLog", back_populates="analyst")

    def __repr__(self):
        return f"<Analyst id={self.id} name='{self.display_name}' sa_id='{self.sa_publishing_id}'>"


# ── Analyst Articles ──────────────────────────────────────────────────────────

class AnalystArticle(Base):
    """
    Raw ingested articles. One row per unique article.
    Dedup enforced via sa_article_id (SA internal ID) + url_hash + content_hash.
    """
    __tablename__ = "analyst_articles"
    __table_args__ = (
        Index("ix_analyst_articles_analyst_published",
              "analyst_id", "published_at"),
        Index("ix_analyst_articles_url_hash", "url_hash"),
        Index("ix_analyst_articles_content_hash", "content_hash"),
        {"schema": "platform_shared"},
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    analyst_id        = Column(Integer, ForeignKey("platform_shared.analysts.id"),
                               nullable=False, index=True)
    sa_article_id     = Column(String(100), unique=True, nullable=False)   # SA internal ID
    url_hash          = Column(String(64), nullable=True)                   # SHA-256 of URL
    content_hash      = Column(String(64), nullable=True)                   # SHA-256 of body

    title             = Column(Text, nullable=False)
    full_text         = Column(Text, nullable=True)
    published_at      = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    fetched_at        = Column(TIMESTAMP(timezone=True), server_default=func.now())

    content_embedding = Column(Vector(1536), nullable=True)
    tickers_mentioned = Column(ARRAY(String), nullable=True)               # quick-access
    article_metadata  = Column("metadata", JSONB, nullable=True)           # source, word_count

    created_at        = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    analyst         = relationship("Analyst", back_populates="articles")
    recommendations = relationship("AnalystRecommendation", back_populates="article")

    def __repr__(self):
        return f"<AnalystArticle id={self.id} sa_id='{self.sa_article_id}' analyst_id={self.analyst_id}>"


# ── Analyst Recommendations ───────────────────────────────────────────────────

class AnalystRecommendation(Base):
    """
    Extracted structured recommendations. One row per ticker per article.
    Supersession model: when analyst flips on a ticker, prior rec is marked
    superseded_by=new_id and is_active=False.
    Decay weight computed by Intelligence Flow staleness sweeper.
    """
    __tablename__ = "analyst_recommendations"
    __table_args__ = (
        Index("ix_analyst_rec_ticker_active_weight",
              "ticker", "is_active", "decay_weight"),
        Index("ix_analyst_rec_analyst_ticker_published",
              "analyst_id", "ticker", "published_at"),
        {"schema": "platform_shared"},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    analyst_id          = Column(Integer, ForeignKey("platform_shared.analysts.id"),
                                 nullable=False, index=True)
    article_id          = Column(Integer, ForeignKey("platform_shared.analyst_articles.id"),
                                 nullable=False, index=True)
    ticker              = Column(String(20), nullable=False, index=True)

    # Asset classification
    sector              = Column(String(50), nullable=True)             # GICS standard
    asset_class         = Column(String(20), nullable=True)             # CommonStock|REIT|MLP|BDC|Preferred|CEF|ETF

    # Recommendation core
    recommendation      = Column(String(20), nullable=True)             # StrongBuy|Buy|Hold|Sell|StrongSell
    sentiment_score     = Column(Numeric(4, 3), nullable=True)          # -1.0 to 1.0

    # Income Pillars (extracted by LLM)
    yield_at_publish    = Column(Numeric(6, 4), nullable=True)
    payout_ratio        = Column(Numeric(6, 4), nullable=True)
    dividend_cagr_3yr   = Column(Numeric(6, 4), nullable=True)
    dividend_cagr_5yr   = Column(Numeric(6, 4), nullable=True)
    safety_grade        = Column(String(5), nullable=True)              # SA Dividend Safety Grade
    source_reliability  = Column(String(20), nullable=True)             # EarningsCall|10K|10Q|...

    # Semantic content
    content_embedding   = Column(Vector(1536), nullable=True)
    rec_metadata        = Column("metadata", JSONB, nullable=True)      # price_target, risks[], thesis

    # Lifecycle
    published_at        = Column(TIMESTAMP(timezone=True), nullable=False)
    expires_at          = Column(TIMESTAMP(timezone=True), nullable=False)  # published_at + aging_days
    decay_weight        = Column(Numeric(5, 4), default=1.0)
    is_active           = Column(Boolean, default=True, nullable=False)
    superseded_by       = Column(Integer,
                                 ForeignKey("platform_shared.analyst_recommendations.id"),
                                 nullable=True)

    # Churn tracking (set at save time by Harvester Flow)
    flip_count          = Column(Integer, default=0)                    # prior flips on this analyst+ticker

    # Agent 02 alignment (written at harvest time by Harvester Flow via Agent 03)
    platform_alignment  = Column(String(20), nullable=True)             # Aligned|Partial|Divergent|Vetoed
    platform_scored_at  = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at          = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at          = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                                 onupdate=func.now())

    # Relationships
    analyst      = relationship("Analyst", back_populates="recommendations")
    article      = relationship("AnalystArticle", back_populates="recommendations")
    superseded   = relationship("AnalystRecommendation",
                                foreign_keys=[superseded_by], remote_side="AnalystRecommendation.id")
    accuracy_logs = relationship("AnalystAccuracyLog", back_populates="recommendation")

    def __repr__(self):
        return (f"<AnalystRecommendation id={self.id} ticker='{self.ticker}' "
                f"rec='{self.recommendation}' active={self.is_active}>")


# ── Analyst Accuracy Log ──────────────────────────────────────────────────────

class AnalystAccuracyLog(Base):
    """
    Backtest outcome records. Written by Intelligence Flow weekly.
    Compares original recommendation against market truth at T+30 and T+90.
    Powers analyst accuracy scoring and sector_alpha computation.
    """
    __tablename__ = "analyst_accuracy_log"
    __table_args__ = {"schema": "platform_shared"}

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    analyst_id               = Column(Integer, ForeignKey("platform_shared.analysts.id"),
                                      nullable=False, index=True)
    recommendation_id        = Column(Integer,
                                      ForeignKey("platform_shared.analyst_recommendations.id"),
                                      nullable=False, index=True)
    ticker                   = Column(String(20), nullable=False, index=True)
    sector                   = Column(String(50), nullable=True)
    asset_class              = Column(String(20), nullable=True)

    # Original signal
    original_recommendation  = Column(String(20), nullable=True)
    price_at_publish         = Column(Numeric(12, 4), nullable=True)

    # Market truth outcomes
    price_at_t30             = Column(Numeric(12, 4), nullable=True)
    price_at_t90             = Column(Numeric(12, 4), nullable=True)
    dividend_cut_occurred    = Column(Boolean, nullable=True)
    dividend_cut_at          = Column(TIMESTAMP(timezone=True), nullable=True)

    # Scoring
    outcome_label            = Column(String(20), nullable=True)        # Correct|Incorrect|Partial|Inconclusive
    accuracy_delta           = Column(Numeric(5, 4), nullable=True)     # +/- applied to analyst score
    sector_accuracy_before   = Column(Numeric(5, 4), nullable=True)
    sector_accuracy_after    = Column(Numeric(5, 4), nullable=True)

    # Override enrichment (written back by Agent 12 when user overrides)
    user_override_occurred   = Column(Boolean, default=False)
    override_outcome_label   = Column(String(20), nullable=True)        # outcome when user overrode platform

    backtest_run_at          = Column(TIMESTAMP(timezone=True), server_default=func.now())
    notes                    = Column(Text, nullable=True)

    # Relationships
    analyst        = relationship("Analyst", back_populates="accuracy_logs")
    recommendation = relationship("AnalystRecommendation", back_populates="accuracy_logs")

    def __repr__(self):
        return (f"<AnalystAccuracyLog id={self.id} analyst_id={self.analyst_id} "
                f"ticker='{self.ticker}' outcome='{self.outcome_label}'>")


# ── Credit Overrides ──────────────────────────────────────────────────────────

class CreditOverride(Base):
    """
    Manual safety grade overrides for edge cases.
    Used by Agent 03 credit rating priority chain when SA grade and
    FMP proxy are both unavailable.
    """
    __tablename__ = "credit_overrides"
    __table_args__ = {"schema": "platform_shared"}

    id             = Column(Integer, primary_key=True, autoincrement=True)
    ticker         = Column(String(20), unique=True, nullable=False, index=True)
    override_grade = Column(String(5), nullable=False)              # e.g. 'B', 'C+'
    reason         = Column(Text, nullable=True)
    set_by         = Column(String(100), nullable=True)
    reviewed_at    = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at     = Column(TIMESTAMP(timezone=True), nullable=True) # null = permanent

    created_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<CreditOverride ticker='{self.ticker}' grade='{self.override_grade}'>"


# ── Article Frameworks ──────────────────────────────────────────────────────

class ArticleFramework(Base):
    """Pass 2 (Sonnet) extraction output: analyst evaluation methodology per ticker."""
    __tablename__ = "article_frameworks"
    __table_args__ = {"schema": "platform_shared"}

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    article_id               = Column(Integer, ForeignKey("platform_shared.analyst_articles.id",
                                       ondelete="CASCADE"), nullable=False)
    analyst_id               = Column(Integer, ForeignKey("platform_shared.analysts.id",
                                       ondelete="CASCADE"), nullable=False)
    ticker                   = Column(String(20), nullable=False)
    valuation_metrics_cited  = Column(JSONB, nullable=True)
    thresholds_identified    = Column(JSONB, nullable=True)
    reasoning_structure      = Column(String(30), nullable=True)
    conviction_level         = Column(String(10), nullable=True)
    catalysts                = Column(JSONB, nullable=True)
    price_guidance_type      = Column(String(20), nullable=True)
    price_guidance_value     = Column(JSONB, nullable=True)
    risk_factors_cited       = Column(JSONB, nullable=True)
    macro_factors            = Column(JSONB, nullable=True)
    evaluation_narrative     = Column(Text, nullable=True)
    framework_embedding      = Column(Vector(1536), nullable=True)
    extracted_at             = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AnalystFrameworkProfile(Base):
    """Synthesized per-analyst, per-asset-class mental model. Updated by Intelligence Flow."""
    __tablename__ = "analyst_framework_profiles"
    __table_args__ = (
        UniqueConstraint("analyst_id", "asset_class", name="uq_analyst_framework_profiles"),
        {"schema": "platform_shared"},
    )

    id                        = Column(Integer, primary_key=True, autoincrement=True)
    analyst_id                = Column(Integer, ForeignKey("platform_shared.analysts.id",
                                        ondelete="CASCADE"), nullable=False)
    asset_class               = Column(String(30), nullable=False)
    metric_frequency          = Column(JSONB, nullable=True)
    typical_thresholds        = Column(JSONB, nullable=True)
    preferred_reasoning_style = Column(String(30), nullable=True)
    conviction_patterns       = Column(JSONB, nullable=True)
    catalyst_sensitivity      = Column(JSONB, nullable=True)
    framework_summary         = Column(Text, nullable=True)
    consistency_score         = Column(Numeric(5, 4), nullable=True)
    article_count             = Column(Integer, default=0)
    synthesized_at            = Column(TIMESTAMP(timezone=True), server_default=func.now())
    profile_embedding         = Column(Vector(1536), nullable=True)


class AnalystSuggestion(Base):
    """Investment idea queue: written by Agent 02 Harvester, read by Agent 07."""
    __tablename__ = "analyst_suggestions"
    __table_args__ = {"schema": "platform_shared"}

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    analyst_id           = Column(Integer, ForeignKey("platform_shared.analysts.id",
                                   ondelete="CASCADE"), nullable=False)
    article_framework_id = Column(Integer, ForeignKey("platform_shared.article_frameworks.id",
                                   ondelete="CASCADE"), nullable=False)
    ticker               = Column(String(20), nullable=False)
    asset_class          = Column(String(30), nullable=True)
    recommendation       = Column(String(20), nullable=False)
    sentiment_score      = Column(Numeric(5, 4), nullable=True)
    price_guidance_type  = Column(String(20), nullable=True)
    price_guidance_value = Column(JSONB, nullable=True)
    staleness_weight     = Column(Numeric(5, 4), default=1.0)
    is_active            = Column(Boolean, default=True, nullable=False)
    sourced_at           = Column(TIMESTAMP(timezone=True), nullable=False)
    expires_at           = Column(TIMESTAMP(timezone=True), nullable=False)


class FeatureGapLog(Base):
    """Metrics cited by analysts that are not tracked in feature_registry."""
    __tablename__ = "feature_gap_log"
    __table_args__ = (
        UniqueConstraint("metric_name_raw", "asset_class", name="uq_feature_gap_log"),
        {"schema": "platform_shared"},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    metric_name_raw     = Column(String(200), nullable=False)
    canonical_candidate = Column(String(200), nullable=True)
    asset_class         = Column(String(30), nullable=True)
    article_id          = Column(Integer, ForeignKey("platform_shared.analyst_articles.id",
                                  ondelete="SET NULL"), nullable=True)
    analyst_id          = Column(Integer, ForeignKey("platform_shared.analysts.id",
                                  ondelete="SET NULL"), nullable=True)
    occurrence_count    = Column(Integer, default=1)
    resolution_status   = Column(String(30), default="pending")
    resolved_at         = Column(TIMESTAMP(timezone=True), nullable=True)


class FeatureRegistry(Base):
    """Canonical feature catalog — drives Agent 01 dynamic feature fetch."""
    __tablename__ = "feature_registry"
    __table_args__ = {"schema": "platform_shared"}

    id                = Column(Integer, primary_key=True, autoincrement=True)
    feature_name      = Column(String(200), unique=True, nullable=False)
    aliases           = Column(JSONB, nullable=True)
    category          = Column(String(20), nullable=False)       # fetchable|derived|external
    source            = Column(String(30), nullable=True)        # fmp|polygon|yfinance|derived|manual
    asset_classes     = Column(JSONB, nullable=True)
    fetch_config      = Column(JSONB, nullable=True)
    computation_rule  = Column(Text, nullable=True)
    is_active         = Column(Boolean, default=False, nullable=False)
    validation_status = Column(String(20), default="pending")
    added_at          = Column(TIMESTAMP(timezone=True), server_default=func.now())
