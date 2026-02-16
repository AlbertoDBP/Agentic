"""Alpha Vantage API Client"""
import aiohttp
import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class AlphaVantageClient:
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
    
    async def get_daily_prices(self, ticker: str, outputsize: str = "compact") -> List[Dict]:
        """Fetch daily price data"""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker.upper(),
            "apikey": self.api_key,
            "outputsize": outputsize
        }
        
        data = await self._make_request(params)
        time_series = data.get("Time Series (Daily)", {})
        
        results = []
        for date_str, values in time_series.items():
            results.append({
                "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
                "adjusted_close": float(values["5. adjusted close"]),
                "volume": int(values["6. volume"])
            })
        
        results.sort(key=lambda x: x["date"], reverse=True)
        return results
    
    async def _make_request(self, params: Dict) -> Dict:
        """Make HTTP request with rate limiting"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        await self._rate_limit()
        
        async with self.session.get(self.BASE_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            
            if "Error Message" in data:
                raise ValueError(f"API Error: {data['Error Message']}")
            
            self.last_request_time = datetime.now()
            return data
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
