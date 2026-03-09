"""Repository for platform_shared.securities upserts."""
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class SecuritiesRepository:
    """Async repository for the platform_shared.securities table."""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def upsert_security(
        self,
        symbol: str,
        name: Optional[str],
        asset_type: Optional[str],
        sector: Optional[str],
        exchange: Optional[str],
        currency: Optional[str],
        expense_ratio: Optional[float],
        aum_millions: Optional[float],
    ) -> None:
        """Upsert a row in platform_shared.securities.

        Only updates columns when the incoming value is not NULL, so a
        partial sync (e.g., no name) will never overwrite a previously
        stored value with NULL.

        Fire-and-forget safe: all exceptions are caught, logged, and
        suppressed — this method never raises.
        """
        try:
            currency = currency or "USD"
            stmt = text("""
                INSERT INTO platform_shared.securities
                    (symbol, name, asset_type, sector, exchange, currency,
                     expense_ratio, aum_millions, updated_at)
                VALUES
                    (:symbol, :name, :asset_type, :sector, :exchange, :currency,
                     :expense_ratio, :aum_millions, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    name           = CASE WHEN EXCLUDED.name IS NOT NULL
                                         THEN EXCLUDED.name
                                         ELSE platform_shared.securities.name END,
                    asset_type     = COALESCE(EXCLUDED.asset_type,
                                             platform_shared.securities.asset_type),
                    sector         = COALESCE(EXCLUDED.sector,
                                             platform_shared.securities.sector),
                    exchange       = COALESCE(EXCLUDED.exchange,
                                             platform_shared.securities.exchange),
                    currency       = COALESCE(EXCLUDED.currency,
                                             platform_shared.securities.currency),
                    expense_ratio  = COALESCE(EXCLUDED.expense_ratio,
                                             platform_shared.securities.expense_ratio),
                    aum_millions   = COALESCE(EXCLUDED.aum_millions,
                                             platform_shared.securities.aum_millions),
                    updated_at     = NOW()
            """)
            async with self.session_factory() as session:
                async with session.begin():
                    await session.execute(stmt, {
                        "symbol":       symbol.upper(),
                        "name":         name,
                        "asset_type":   asset_type,
                        "sector":       sector,
                        "exchange":     exchange,
                        "currency":     currency,
                        "expense_ratio": expense_ratio,
                        "aum_millions": aum_millions,
                    })
            logger.info(f"✅ Upserted security: {symbol.upper()}")
        except Exception as e:
            logger.error(f"SecuritiesRepository.upsert_security({symbol}) failed: {e}")
