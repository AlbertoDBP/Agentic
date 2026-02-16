# Market Data Service

FastAPI microservice for fetching and caching market data.

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://..."
export REDIS_URL="rediss://..."
export MARKET_DATA_API_KEY="your_alpha_vantage_key"

# Run service
python -m src.market-data-service.main
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/price/{ticker}` - Get current price
- `GET /api/v1/cache/stats` - Cache statistics

## Features

- ✅ Alpha Vantage integration with rate limiting
- ✅ Redis caching (5-minute TTL)
- ✅ Async/await for performance
- ✅ Pydantic validation
- ✅ Automatic ticker normalization
