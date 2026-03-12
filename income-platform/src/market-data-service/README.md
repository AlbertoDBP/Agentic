# Market Data Service — Agent 01

Real-time and historical market data API with multi-provider fallback strategy (Polygon → FMP → yfinance → Finnhub) and Redis caching.

## Overview

Agent 01 is the foundational data layer for the income platform. It aggregates market data from multiple sources, providing current prices, historical OHLCV, dividends, fundamentals, and ETF holdings to downstream agents. A dynamic provider router implements graceful degradation—if Polygon is down, it falls back to FMP, then yfinance. Redis caching reduces API calls and improves latency for frequently requested symbols.

This service is called by Agent 03 (scoring), Agent 02 (newsletters), Agent 05 (tax), and Agent 06 (scenarios).

## Port & Health Check

- **Port:** 8001
- **Health:** `GET /health` — checks database and Redis connectivity
- **Docs:** `GET /docs` (OpenAPI/Swagger UI)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check with DB + cache status |
| GET | `/stocks/{symbol}/price` | Current price (cached 5 min) |
| GET | `/stocks/{symbol}/history` | OHLCV data for date range |
| GET | `/stocks/{symbol}/history/stats` | Min/max/avg/volatility/returns |
| POST | `/stocks/{symbol}/history/refresh` | Force-fetch & persist full history |
| GET | `/stocks/{symbol}/dividends` | Dividend payment history (FMP → yfinance) |
| GET | `/stocks/{symbol}/fundamentals` | P/E, debt/equity, payout ratio, FCF, market cap, sector |
| GET | `/stocks/{symbol}/etf` | ETF metadata, expense ratio, AUM, covered call flag, top 20 holdings |
| GET | `/api/v1/providers/status` | Health & last-used timestamp for each provider |
| POST | `/stocks/{symbol}/sync` | Fetch & persist fundamentals, dividends, credit rating to DB |

## Dependencies

**Upstream services:** None (data source only)

**External dependencies:**
- PostgreSQL (schema: `platform_shared`) — stores securities, price_history, features_historical
- Redis/Valkey — caching with configurable TTL
- **Polygon.io** (primary stock data provider)
- **Financial Modeling Prep** (dividends, fundamentals, ETF holdings)
- **yfinance** (fallback for dividends & fundamentals)
- **Finnhub** (credit ratings for bonds)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string (schema: platform_shared) |
| REDIS_URL | Yes | Redis/Valkey URL for cache |
| MARKET_DATA_API_KEY | Yes | Alpha Vantage API key (legacy, kept as reference) |
| POLYGON_API_KEY | No | Polygon.io API key (primary provider) |
| FMP_API_KEY | No | Financial Modeling Prep API key (secondary) |
| FINNHUB_API_KEY | No | Finnhub API key (credit ratings) |
| JWT_SECRET | Yes | Shared JWT signing secret |
| SERVICE_PORT | No | Default: 8001 |
| LOG_LEVEL | No | Default: INFO |
| CACHE_TTL_CURRENT_PRICE | No | Default: 300 seconds |

## Running Locally

```bash
cd src/market-data-service

# Install dependencies
pip install -r requirements.txt

# Run with direct Python execution
export DATABASE_URL="postgresql://user:pass@localhost/income_platform"
export REDIS_URL="redis://localhost:6379"
export POLYGON_API_KEY="your_key"
export FMP_API_KEY="your_key"
export MARKET_DATA_API_KEY="your_key"
export JWT_SECRET="dev-secret"

python main.py
# or via uvicorn:
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Running Tests

```bash
cd src/market-data-service
pytest tests/ -v
# Note: Unit tests include test_polygon_client.py, test_fmp_client.py, test_finnhub_client.py, test_features_repository.py
```

## Project Structure

```
market-data-service/
├── main.py                   # FastAPI entry point; custom importlib loader
├── config.py                 # Settings: API keys, DB, Redis, TTL
├── auth.py                   # JWT verification
├── models.py                 # Pydantic request/response schemas
├── cache.py                  # CacheManager (Redis wrapper)
├── database.py               # DatabaseManager (SQLAlchemy pool)
├── orm_models.py             # SQLAlchemy ORM for platform_shared schema
├── fetchers/
│   ├── base_provider.py      # BaseProvider abstract class
│   ├── polygon_client.py     # Polygon.io client (primary)
│   ├── fmp_client.py         # FMP client (secondary)
│   ├── yfinance_client.py    # yfinance client (tertiary)
│   ├── finnhub_client.py     # Finnhub client (credit ratings)
│   ├── provider_router.py    # Dynamic routing: Polygon → FMP → yfinance
│   └── alpha_vantage.py      # Deprecated reference implementation
├── repositories/
│   ├── price_repository.py          # Current price queries
│   ├── price_history_repository.py  # Historical OHLCV queries
│   ├── securities_repository.py     # Security metadata (upsert)
│   └── features_repository.py       # Historical features (upsert)
├── services/
│   ├── price_service.py             # Current price resolution logic
│   └── market_data_service.py       # Orchestrator: coordinates fetchers & repos
├── requirements.txt
├── Dockerfile
└── tests/
    ├── unit/
    │   ├── test_polygon_client.py
    │   ├── test_fmp_client.py
    │   ├── test_finnhub_client.py
    │   ├── test_features_repository.py
    │   └── test_market_data_service_helpers.py
    └── ...
```

## Key Design Decisions

- **Provider Router Pattern:** Implements graceful degradation via sequential fallback. If Polygon fails, the router automatically tries FMP, then yfinance, without surfacing the failure to the caller. This ensures the platform degrades gracefully during provider outages.
- **Dynamic Importlib Loader:** Custom `_load()` function in main.py registers modules by file path instead of using relative imports, enabling the service to be run directly as `python main.py` without needing uvicorn wrapper scripts.
- **Fire-and-Forget Persistence:** Calls to `/fundamentals` and `/etf` trigger background upserts to `securities_repository` and `features_repository` using `asyncio.ensure_future()`, keeping latency under control while enriching the database asynchronously.
- **Redis TTL Stratification:** Current prices (5 min), historical data (6 h), quality gate results (24 h) — balances freshness with API quota conservation based on how frequently each data type changes.
