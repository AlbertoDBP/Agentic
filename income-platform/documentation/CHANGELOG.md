# Changelog — Income Fortress Platform

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] — 2026-02-23

### Market Data Service — Session 2: Historical Price Queries

#### Added
- `PriceHistory` SQLAlchemy model with unique constraint on `(symbol, date)`
- `PriceHistoryRepository` with upsert, range query, bulk save, and latest price methods
- Alembic migration `a218ef2b914c` — create price_history table
- `GET /stocks/{symbol}/history` — fetch OHLCV price range with date filters
- `GET /stocks/{symbol}/history/stats` — min, max, avg, volatility, price change % for a period
- `POST /stocks/{symbol}/history/refresh` — force fetch from Alpha Vantage and persist
- `GET /stocks/{symbol}/price` — current price (consolidated from legacy route)

#### Changed
- Route structure consolidated to `/stocks/{symbol}/` pattern (Nginx strips `/api/market-data/` prefix)
- `AlphaVantageClient.last_request_time` changed to class variable `_last_request_time` — rate limiter now shared across all instances
- `get_historical_prices` uses `get_daily_prices` (free tier) instead of `fetch_daily_adjusted` (premium)
- Historical fetch limited to 140-day compact window; ranges older than cutoff return DB data only
- `refresh_historical_prices` always uses `outputsize="compact"` (full history is premium tier)
- `refresh_stock_history` endpoint catches `ValueError` and returns HTTP 502 with Alpha Vantage message

#### Removed
- Legacy routes: `/api/v1/price/{ticker}`, `/api/v1/price/{ticker}/history`, `/api/v1/price/{ticker}/refresh`, `/api/v1/price/{ticker}/statistics`

#### Fixed
- Redis `socket_connect_timeout=5, socket_timeout=5` added to prevent startup hang on VPC-only Valkey instance
- Rate limiter hard floor set to `max(60/calls_per_minute, 1.1)` seconds per request

#### Security
- Removed orphaned `redis:7-alpine` Docker container that was exposing port 6379 publicly
- Confirmed DigitalOcean Cloud Firewall blocks all ports except 22, 80, 443
- Production confirmed running on managed Valkey via `${REDIS_URL}` — no local Redis required

---

## [1.1.0] — 2026-02-19

### Market Data Service — Session 1: Database Persistence

#### Added
- FastAPI service with Alpha Vantage integration
- PostgreSQL database persistence via SQLAlchemy ORM
- Redis/Valkey caching layer
- `GET /health` endpoint with database and cache connectivity checks
- `GET /stocks/{symbol}/price` endpoint
- `GET /api/v1/cache/stats` endpoint
- Nginx reverse proxy with SSL at legatoinvest.com
- Production deployment on DigitalOcean

---
