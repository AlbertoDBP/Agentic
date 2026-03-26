"""
Agent 07 — Opportunity Scanner Service
ORM models — scan_results table in platform_shared schema.
"""
from __future__ import annotations

import uuid
from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScanResult(Base):
    """Persisted scan run: filters used + ranked ticker list."""
    __tablename__ = "scan_results"
    __table_args__ = (
        Index("ix_scan_results_created_at", "created_at"),
        {"schema": "platform_shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    total_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    total_passed: Mapped[int] = mapped_column(Integer, nullable=False)
    total_vetoed: Mapped[int] = mapped_column(Integer, nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False)   # List[ScanItem dicts]
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


class ProposalDraft(Base):
    """Proposal draft written by scanner before Agent 12 picks it up."""
    __tablename__ = "proposal_drafts"
    __table_args__ = (
        Index("ix_proposal_drafts_created_at", "created_at"),
        {"schema": "platform_shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_shared.scan_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_shared.portfolios.id"),
        nullable=False,
    )
    tickers: Mapped[list] = mapped_column(JSONB, nullable=False)       # [{ticker, entry_limit, exit_limit}]
    entry_limits: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {ticker: entry_limit}
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
