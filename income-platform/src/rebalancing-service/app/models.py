"""ORM model — rebalancing_results table."""
from __future__ import annotations
import uuid
from sqlalchemy import Index, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RebalancingResult(Base):
    """Persisted rebalance run."""
    __tablename__ = "rebalancing_results"
    __table_args__ = (
        Index("ix_rebalancing_results_portfolio_id", "portfolio_id"),
        Index("ix_rebalancing_results_created_at", "created_at"),
        {"schema": "platform_shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    violations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    proposals: Mapped[list] = mapped_column(JSONB, nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_tax_savings: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False,
    )
