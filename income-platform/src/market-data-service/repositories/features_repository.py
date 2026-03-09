"""Repository for platform_shared.features_historical upserts."""
import logging
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)

# Credit rating → ordinal bucket mapping (investment-grade threshold: BBB-)
# Standard S&P / Fitch scale.  Moody's equivalents mapped to S&P notation.
_INVESTMENT_GRADE = {
    "AAA", "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
}
_BORDERLINE = {"BB+", "BB", "BB-"}


def _credit_quality_from_rating(rating: Optional[str]) -> Optional[str]:
    """Map a credit rating string to a quality bucket.

    BBB- and above → INVESTMENT_GRADE
    BB+/BB/BB-     → BORDERLINE
    B+ and below   → SPECULATIVE_GRADE
    None           → None (caller should fall back to interest_coverage)
    """
    if not rating:
        return None
    normalised = rating.strip().upper()
    if normalised in _INVESTMENT_GRADE:
        return "INVESTMENT_GRADE"
    if normalised in _BORDERLINE:
        return "BORDERLINE"
    return "SPECULATIVE_GRADE"


def _credit_quality_from_coverage(interest_coverage: Optional[float]) -> Optional[str]:
    """Derive credit quality proxy from interest coverage ratio.

    >= 3.0  → INVESTMENT_GRADE
    1.5–2.99 → BORDERLINE
    < 1.5   → SPECULATIVE_GRADE
    None    → None
    """
    if interest_coverage is None:
        return None
    if interest_coverage >= 3.0:
        return "INVESTMENT_GRADE"
    if interest_coverage >= 1.5:
        return "BORDERLINE"
    return "SPECULATIVE_GRADE"


def compute_credit_quality_proxy(
    credit_rating: Optional[str],
    interest_coverage: Optional[float],
) -> Optional[str]:
    """Return credit quality proxy, preferring rating over coverage ratio."""
    proxy = _credit_quality_from_rating(credit_rating)
    if proxy is not None:
        return proxy
    return _credit_quality_from_coverage(interest_coverage)


class FeaturesRepository:
    """Async repository for the platform_shared.features_historical table."""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def upsert_features(
        self,
        symbol: str,
        as_of_date: date,
        yield_trailing_12m: Optional[float],
        yield_5yr_avg: Optional[float],
        div_cagr_5y: Optional[float],
        chowder_number: Optional[float],
        payout_ratio: Optional[float],
        pe_ratio: Optional[float],
        credit_rating: Optional[str],
        credit_quality_proxy: Optional[str],
        interest_coverage: Optional[float],
        advisor_coverage_count: Optional[int],
        missing_feature_ratio: Optional[float],
    ) -> None:
        """Upsert a row in platform_shared.features_historical.

        If credit_quality_proxy is not provided, it is computed here from
        credit_rating and interest_coverage.

        Fire-and-forget safe: all exceptions are caught, logged, and
        suppressed — this method never raises.
        """
        try:
            # Compute proxy if caller did not supply one
            if credit_quality_proxy is None:
                credit_quality_proxy = compute_credit_quality_proxy(
                    credit_rating, interest_coverage
                )

            stmt = text("""
                INSERT INTO platform_shared.features_historical (
                    symbol, as_of_date,
                    yield_trailing_12m, yield_5yr_avg, div_cagr_5y,
                    chowder_number, payout_ratio, pe_ratio,
                    credit_rating, credit_quality_proxy, interest_coverage,
                    advisor_coverage_count, missing_feature_ratio,
                    updated_at
                ) VALUES (
                    :symbol, :as_of_date,
                    :yield_trailing_12m, :yield_5yr_avg, :div_cagr_5y,
                    :chowder_number, :payout_ratio, :pe_ratio,
                    :credit_rating, :credit_quality_proxy, :interest_coverage,
                    :advisor_coverage_count, :missing_feature_ratio,
                    NOW()
                )
                ON CONFLICT (symbol, as_of_date) DO UPDATE SET
                    yield_trailing_12m     = COALESCE(EXCLUDED.yield_trailing_12m,
                                                      platform_shared.features_historical.yield_trailing_12m),
                    yield_5yr_avg          = COALESCE(EXCLUDED.yield_5yr_avg,
                                                      platform_shared.features_historical.yield_5yr_avg),
                    div_cagr_5y            = COALESCE(EXCLUDED.div_cagr_5y,
                                                      platform_shared.features_historical.div_cagr_5y),
                    chowder_number         = COALESCE(EXCLUDED.chowder_number,
                                                      platform_shared.features_historical.chowder_number),
                    payout_ratio           = COALESCE(EXCLUDED.payout_ratio,
                                                      platform_shared.features_historical.payout_ratio),
                    pe_ratio               = COALESCE(EXCLUDED.pe_ratio,
                                                      platform_shared.features_historical.pe_ratio),
                    credit_rating          = COALESCE(EXCLUDED.credit_rating,
                                                      platform_shared.features_historical.credit_rating),
                    credit_quality_proxy   = COALESCE(EXCLUDED.credit_quality_proxy,
                                                      platform_shared.features_historical.credit_quality_proxy),
                    interest_coverage      = COALESCE(EXCLUDED.interest_coverage,
                                                      platform_shared.features_historical.interest_coverage),
                    advisor_coverage_count = COALESCE(EXCLUDED.advisor_coverage_count,
                                                      platform_shared.features_historical.advisor_coverage_count),
                    missing_feature_ratio  = EXCLUDED.missing_feature_ratio,
                    updated_at             = NOW()
            """)
            async with self.session_factory() as session:
                async with session.begin():
                    await session.execute(stmt, {
                        "symbol":                symbol.upper(),
                        "as_of_date":            as_of_date,
                        "yield_trailing_12m":    yield_trailing_12m,
                        "yield_5yr_avg":         yield_5yr_avg,
                        "div_cagr_5y":           div_cagr_5y,
                        "chowder_number":        chowder_number,
                        "payout_ratio":          payout_ratio,
                        "pe_ratio":              pe_ratio,
                        "credit_rating":         credit_rating,
                        "credit_quality_proxy":  credit_quality_proxy,
                        "interest_coverage":     interest_coverage,
                        "advisor_coverage_count": advisor_coverage_count,
                        "missing_feature_ratio": missing_feature_ratio,
                    })
            logger.info(
                f"✅ Upserted features for {symbol.upper()} as of {as_of_date}"
            )
        except Exception as e:
            logger.error(
                f"FeaturesRepository.upsert_features({symbol}, {as_of_date}) failed: {e}"
            )
