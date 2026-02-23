"""SQLAlchemy ORM models for the Market Data Service.

MarketDataDaily  — maps to the existing market_data_daily table created by
                   V3.0__complete_platform_schema.sql. Uses extend_existing=True
                   so SQLAlchemy never attempts DDL against it.

PriceHistory     — new table managed by this service via Alembic migrations.
"""
import uuid

from sqlalchemy import BigInteger, Column, Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class MarketDataDaily(Base):
    __tablename__ = "market_data_daily"
    __table_args__ = {"extend_existing": True}

    data_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker_symbol = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    open_price = Column(Numeric(10, 2), nullable=True)
    high_price = Column(Numeric(10, 2), nullable=True)
    low_price = Column(Numeric(10, 2), nullable=True)
    close_price = Column(Numeric(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=True)
    adjusted_close = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceHistory(Base):
    """
    Historical OHLCV price bars managed by this service.
    Created and migrated via Alembic (see migrations/versions/).
    """
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_price_history_symbol_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open_price = Column(Numeric(12, 4), nullable=True)
    high_price = Column(Numeric(12, 4), nullable=True)
    low_price = Column(Numeric(12, 4), nullable=True)
    close_price = Column(Numeric(12, 4), nullable=True)
    adjusted_close = Column(Numeric(12, 4), nullable=True)
    volume = Column(BigInteger, nullable=True)
    data_source = Column(String(50), nullable=False, server_default="alpha_vantage")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
