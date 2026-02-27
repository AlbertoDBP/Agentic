"""Agent 04 — SQLAlchemy ORM Models"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, JSON, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class AssetClassification(Base):
    __tablename__ = "asset_classifications"
    __table_args__ = {"schema": "platform_shared"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_class: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_hybrid: Mapped[bool] = mapped_column(Boolean, default=False)
    characteristics: Mapped[dict] = mapped_column(JSON, nullable=True)
    benchmarks: Mapped[dict] = mapped_column(JSON, nullable=True)
    sub_scores: Mapped[dict] = mapped_column(JSON, nullable=True)
    tax_efficiency: Mapped[dict] = mapped_column(JSON, nullable=True)
    matched_rules: Mapped[dict] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="rule_engine_v1")
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class AssetClassRule(Base):
    __tablename__ = "asset_class_rules"
    __table_args__ = {"schema": "platform_shared"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    confidence_weight: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ClassificationOverride(Base):
    __tablename__ = "classification_overrides"
    __table_args__ = {"schema": "platform_shared"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    effective_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
