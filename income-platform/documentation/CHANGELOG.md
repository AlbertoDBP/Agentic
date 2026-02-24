# Changelog — Income Fortress Platform

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] — 2026-02-23

### Market Data Service — Session 3: Multi-Provider Data Architecture

#### Added
- `fetchers/base_provider.py` — `BaseDataProvider` ABC with `ProviderError` and `DataUnavailableError` exceptions; default `__aenter__`/`__aexit__` lifecycle
- `fetchers/polygon_client.py` — Polygon.io Stocks Starter client; OHLCV, dividends, fundamentals; class-level rate limiter at 100 req/min; Redis caching
- `fetchers/fmp_client.py` — Financial Modeling Prep Starter client; dividends, fundamentals, ETF holdings; 300 req/min; concurrent endpoint fetches; `/stable/` base URL
- `fetchers/yfinance_client.py` — yfinance fallback client; all five `BaseDataProvider` methods via `asyncio.to_thread()`; no rate limiting; no caching
- `fetchers/provider_router.py` — priority chain router; graceful degradation on provider init failure; per-method routing; `_try_chain` with concatenated failure messages
- `GET /stocks/{symbol}/dividends` — dividend history with ex_date, payment_date, amount, frequency, yield_pct
- `GET /stocks/{symbol}/fundamentals` — pe_ratio, debt_to_equity, payout_ratio, free_cash_flow, market_cap, sector
- `GET /stocks/{symbol}/etf` — expense_ratio, aum, covered_call, top_holdings with ticker+name+weight_pct
- `GET /api/v1/providers/status` — healthy, last_used per provider
- Pydantic models: `DividendRecord`, `StockDividendResponse`, `StockFundamentalsResponse`, `ETFHolding`, `StockETFResponse`, `ProviderInfo`, `ProvidersStatusResponse`
- `config.py` — `polygon_api_key`, `fmp_api_key` (optional, graceful degradation if absent)
- `connect()` / `disconnect()` lifecycle methods on `MarketDataService`
- 33 unit tests across provider router, FMP client, Polygon client

#### Changed
- `market_data_service.py` — replaced `AlphaVantageClient` with `ProviderRouter`; history window extended from 140 to 730 days; `full_history=True` now works
- `docker-compose.yml` — added `POLYGON_API_KEY` and `FMP_API_KEY` to environment

#### Deprecated
- `AlphaVantageClient` — retained in codebase as reference, not wired into router

#### Fixed
- `asyncio.gather(return_exceptions=True)` silently swallowing FMP 403 errors — now re-raises as `ProviderError` so router falls back to yfinance
- FMP legacy `/api/v3/` endpoints returning 403 for post-Aug-2025 API keys — migrated to `/stable/` base URL
- FMP field name changes: `priceEarningsRatio` → `priceToEarningsRatio`, `payoutRatio` → `dividendPayoutRatio`, `mktCap` → `marketCap`
- yfinance `expense_ratio`: `annualReportExpenseRatio` (None) → `netExpenseRatio`
- yfinance `aum`: `totalNetAssets` (None) → `totalAssets`
- yfinance holdings ticker: DataFrame index is ticker symbol, not a column
- JEPI `covered_call` detection: added ELN, "selling call option", longName, known symbol list checks
- `POLYGON_API_KEY` and `FMP_API_KEY` missing from `docker-compose.yml` environment block

---

## [1.2.0] — 2026-02-23

### Market Data Service — Session 2: Historical Price Queries

#### Added
- `PriceHistory` model with unique constraint on `(symbol, date)`
- `PriceHistoryRepository` with upsert, range query, bulk save
- `GET /stocks/{symbol}/history` — OHLCV range query
- `GET /stocks/{symbol}/history/stats` — min, max, avg, volatility, price change %
- `POST /stocks/{symbol}/history/refresh` — force fetch from Alpha Vantage

#### Changed
- Route structure consolidated to `/stocks/{symbol}/` pattern
- Rate limiter changed to class variable `_last_request_time`
- Switched to free-tier `get_daily_prices` with 140-day cutoff

#### Security
- Removed orphaned `redis:7-alpine` container exposing port 6379 publicly

---

## [1.1.0] — 2026-02-19

### Market Data Service — Session 1: Database Persistence

#### Added
- FastAPI service with Alpha Vantage integration
- PostgreSQL persistence, Redis/Valkey caching
- `GET /health`, `GET /stocks/{symbol}/price`, `GET /api/v1/cache/stats`
- Production deployment on DigitalOcean at legatoinvest.com

---
