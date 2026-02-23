"""create_price_history_table

Revision ID: a218ef2b914c
Revises:
Create Date: 2026-02-19 09:51:30.294753

Creates the price_history table for the Market Data Service.
This table stores historical OHLCV price bars fetched from data providers
(e.g. Alpha Vantage) and is distinct from the platform-wide market_data_daily
table which is managed by the V3.0 migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a218ef2b914c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("high_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("low_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("adjusted_close", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column(
            "data_source",
            sa.String(50),
            nullable=False,
            server_default="alpha_vantage",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("symbol", "date", name="uq_price_history_symbol_date"),
    )

    # Index on symbol for ticker-based lookups
    op.create_index("ix_price_history_symbol", "price_history", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_price_history_symbol", table_name="price_history")
    op.drop_table("price_history")
