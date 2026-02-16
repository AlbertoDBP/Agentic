"""Alpha Vantage API Client - FREE tier compatible"""
import aiohttp
import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class AlphaVantageClient:
    """Async client for Alpha Vantage API (FREE tier)"""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str, calls_per_minute: int = 5):
        self.api_key = api_key
        self.min_interval = 60.0 / calls_per_minute
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_request_time: Optional[datetime] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_daily_prices(
        self, 
        ticker: str,
        outputsize: str = "compact"
    ) -> List[Dict]:
        """
        Fetch daily price data (FREE endpoint)
        
        Args:
            ticker: Stock symbol
            outputsize: "compact" (100 days) or "full" (20+ years)
        
        Returns:
            List of price dictionaries
        """
        params = {
            "function": "TIME_SERIES_DAILY",  # FREE endpoint
            "symbol": ticker.upper(),
            "apikey": self.api_key,
            "outputsize": outputsize
        }
        
        try:
            data = await self._make_request(params)
            
            time_series = data.get("Time Series (Daily)", {})
            
            if not time_series:
                logger.warning(f"No price data returned for {ticker}")
                return []
            
            results = []
            for date_str, values in time_series.items():
                try:
                    results.append({
                        "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                        "open": float(values["1. open"]),
                        "high": float(values["2. high"]),
                        "low": float(values["3. low"]),
                        "close": float(values["4. close"]),
                        "volume": int(values["5. volume"]),
                        "adjusted_close": float(values["4. close"])  # Same as close for free tier
                    })
                except (ValueError, KeyError) as e:
                    logger.error(f"Failed to parse {ticker} data for {date_str}: {e}")
                    continue
            
            results.sort(key=lambda x: x["date"], reverse=True)
            
            logger.info(f"✅ Fetched {len(results)} days for {ticker}")
            return results
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch {ticker}: {e}")
            raise
    
    async def get_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get current quote (FREE endpoint, real-time)
        
        Args:
            ticker: Stock symbol
        
        Returns:
            Dictionary with current quote data
        """
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker.upper(),
            "apikey": self.api_key
        }
        
        try:
            data = await self._make_request(params)
            quote = data.get("Global Quote", {})
            
            if not quote:
                logger.warning(f"No quote data for {ticker}")
                return None
            
            return {
                "ticker": ticker.upper(),
                "price": float(quote.get("05. price", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day"),
                "previous_close": float(quote.get("08. previous close", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%").rstrip("%")
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch quote for {ticker}: {e}")
            return None
    
    async def _make_request(self, params: Dict) -> Dict:
        """Make HTTP request with rate limiting"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        await self._rate_limit()
        
        try:
            async with self.session.get(
                self.BASE_URL, 
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Check for errors
                if "Error Message" in data:
                    raise ValueError(f"API Error: {data['Error Message']}")
                
                if "Note" in data:
                    logger.warning(f"Rate limit warning: {data['Note']}")
                    raise RuntimeError(f"Rate limited: {data['Note']}")
                
                if "Information" in data and "premium" in data["Information"].lower():
                    raise ValueError(f"Premium endpoint not available: {data['Information']}")
                
                self.last_request_time = datetime.now()
                return data
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            raise
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"⏱️  Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
