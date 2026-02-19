"""SQLAlchemy ORM model mapping to the existing market_data_daily table.

The table is created by V3.0__complete_platform_schema.sql and must NOT be
recreated here. Use extend_existing=True so SQLAlchemy reflects the table
metadata without attempting DDL.
"""
import uuid

from sqlalchemy import BigInteger, Column, Date, DateTime, Numeric, String
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
