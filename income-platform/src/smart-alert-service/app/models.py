"""ORM models for the Smart Alert Service."""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UnifiedAlert(Base):
    __tablename__ = "unified_alerts"
    __table_args__ = {"schema": "platform_shared"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    source_agent: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="PENDING")
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
