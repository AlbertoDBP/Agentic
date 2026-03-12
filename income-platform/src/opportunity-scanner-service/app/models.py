"""
Agent 07 — Opportunity Scanner Service
ORM models — scan_results table in platform_shared schema.
"""
from __future__ import annotations

import uuid
from sqlalchemy import Index, Integer, String, text
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
