"""ORM model for income_projections table."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, JSON, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class IncomeProjection(Base):
    __tablename__ = "income_projections"
    __table_args__ = {"schema": "platform_shared"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    computed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    horizon_months = Column(Integer, nullable=False, default=12)
    total_projected_annual = Column(Numeric(12, 2), nullable=True)
    total_projected_monthly_avg = Column(Numeric(12, 2), nullable=True)
    yield_used = Column(String(20), nullable=True)
    positions_included = Column(Integer, nullable=True)
    positions_missing_data = Column(Integer, nullable=True)
    position_detail = Column(JSON, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
