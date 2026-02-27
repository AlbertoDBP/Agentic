"""
Agent 04 — Data Client
Calls Agent 01 for security enrichment when confidence < threshold.
Only invoked for the second pass (confidence < 0.70).
"""
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class MarketDataClient:
    """Async HTTP client for Agent 01 enrichment calls."""

    def __init__(self):
        self.base_url = settings.market_data_service_url
        self.timeout = settings.market_data_timeout

    async def get_enrichment_data(self, ticker: str) -> dict:
        """
        Fetch fundamentals + ETF data for enrichment.
        Returns merged dict of available fields.
        On any error: returns {} (graceful degradation).
        """
        data = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Fundamentals
            try:
                r = await client.get(f"{self.base_url}/stocks/{ticker}/fundamentals")
                if r.status_code == 200:
                    data.update(r.json())
            except Exception as e:
                logger.warning(f"Agent 01 fundamentals unavailable for {ticker}: {e}")

            # ETF data
            try:
                r = await client.get(f"{self.base_url}/stocks/{ticker}/etf")
                if r.status_code == 200:
                    etf = r.json()
                    # Map ETF fields to detection-friendly keys
                    if etf.get("covered_call"):
                        data["options_strategy_present"] = True
                        data["is_etf"] = True
                    if etf.get("aum"):
                        data["aum_millions"] = etf["aum"]
                    data.update(etf)
            except Exception as e:
                logger.warning(f"Agent 01 ETF data unavailable for {ticker}: {e}")

        return data
