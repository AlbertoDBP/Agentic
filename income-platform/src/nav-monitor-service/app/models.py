"""ORM model — nav_alerts table."""
from __future__ import annotations

from sqlalchemy import Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NavAlert(Base):
    """Persisted NAV erosion / premium-discount / score-divergence alert."""
    __tablename__ = "nav_alerts"
    __table_args__ = (
        Index("ix_nav_alerts_symbol", "symbol"),
        Index("ix_nav_alerts_alert_type", "alert_type"),
        Index("ix_nav_alerts_severity", "severity"),
        Index("ix_nav_alerts_created_at", "created_at"),
        {"schema": "platform_shared"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    score_at_alert: Mapped[float] = mapped_column(Numeric(5, 1), nullable=True)
    erosion_rate_used: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    threshold_used: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    resolved_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
