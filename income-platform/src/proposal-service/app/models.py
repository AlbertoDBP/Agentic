"""ORM model for platform_shared.proposals."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, Integer, Numeric, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = {"schema": "platform_shared"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False)
    analyst_signal_id = Column(Integer, nullable=True)
    analyst_id = Column(Integer, nullable=True)
    platform_score = Column(Numeric(5, 1), nullable=True)
    platform_alignment = Column(String(20), nullable=True)
    veto_flags = Column(JSONB, nullable=True)
    divergence_notes = Column(Text, nullable=True)

    # Lens 1: Analyst
    analyst_recommendation = Column(String(20), nullable=True)
    analyst_sentiment = Column(Numeric(6, 4), nullable=True)
    analyst_thesis_summary = Column(Text, nullable=True)
    analyst_yield_estimate = Column(Numeric(8, 4), nullable=True)
    analyst_safety_grade = Column(String(10), nullable=True)

    # Lens 2: Platform
    platform_yield_estimate = Column(Numeric(8, 4), nullable=True)
    platform_safety_result = Column(JSONB, nullable=True)
    platform_income_grade = Column(String(5), nullable=True)

    # Execution Parameters
    entry_price_low = Column(Numeric(10, 2), nullable=True)
    entry_price_high = Column(Numeric(10, 2), nullable=True)
    position_size_pct = Column(Numeric(5, 2), nullable=True)
    recommended_account = Column(String(50), nullable=True)
    sizing_rationale = Column(Text, nullable=True)

    # State
    status = Column(String(30), default="pending", nullable=False)
    trigger_mode = Column(String(30), nullable=True)
    trigger_ref_id = Column(Text, nullable=True)
    override_rationale = Column(Text, nullable=True)
    user_acknowledged_veto = Column(Boolean, default=False, nullable=False)
    reviewed_by = Column(Text, nullable=True)
    decided_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
