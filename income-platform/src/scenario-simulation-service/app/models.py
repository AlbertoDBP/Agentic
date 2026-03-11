"""
Agent 06 — Scenario Simulation Service
ORM model: ScenarioResult persisted to platform_shared.scenario_results.
"""
import uuid
from sqlalchemy import (
    Column, String, Numeric, Index, text,
)
from sqlalchemy.dialects.postgresql import UUID, JSON, TIMESTAMP

from app.database import Base


class ScenarioResult(Base):
    __tablename__ = "scenario_results"
    __table_args__ = (
        Index("ix_scenario_results_portfolio_created", "portfolio_id", "created_at"),
        {"schema": "platform_shared"},
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    portfolio_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    scenario_name = Column(String(50), nullable=False)
    scenario_type = Column(String(20), nullable=False)   # PREDEFINED | CUSTOM
    scenario_params = Column(JSON, nullable=True)
    result_summary = Column(JSON, nullable=False)
    vulnerability_ranking = Column(JSON, nullable=True)
    projected_income_p10 = Column(Numeric(12, 2), nullable=True)
    projected_income_p50 = Column(Numeric(12, 2), nullable=True)
    projected_income_p90 = Column(Numeric(12, 2), nullable=True)
    label = Column(String(200), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
