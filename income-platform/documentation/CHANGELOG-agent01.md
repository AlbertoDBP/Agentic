# CHANGELOG — Agent 01: Market Data Service

---

## [1.1.0] — 2026-03-09

### Added
- **Finnhub credit rating fetcher** (`fetchers/finnhub_client.py`)
  - Fetches S&P/Moody's credit ratings via Finnhub `/stock/metric` endpoint
  - Graceful degradation: returns None on 401/403/429/any error
  - Added to `/api/v1/providers/status` response
- **Securities repository** (`repositories/securities_repository.py`)
  - Upserts to `platform_shared.securities` (TEXT PK)
  - ON CONFLICT (symbol) DO UPDATE pattern — idempotent
  - Fire-and-forget: errors logged, never raised
- **Features repository** (`repositories/features_repository.py`)
  - Upserts to `platform_shared.features_historical`
  - Credit quality proxy computation: rating → interest_coverage → NULL
  - Chowder Number stored as NULL (not 0.0) when inputs missing
- **`POST /stocks/{symbol}/sync` endpoint**
  - Full feature sync: fundamentals → dividends → credit rating → upsert
  - Returns SyncResponse with `missing_fields` for every NULL value
  - Computes: `chowder_number`, `yield_5yr_avg`, `credit_quality_proxy`
- **`SyncResponse` model** (`models.py`)
- **Lazy securities upsert** on `GET /fundamentals` and `GET /etf` (fire-and-forget)
- **76 new unit tests** (all passing):
  - `test_finnhub_client.py` — 13 tests
  - `test_features_repository.py` — 23 tests
  - `test_market_data_service_helpers.py` — 40 tests

### Changed
- `config.py` — `finnhub_api_key: str = ""` added (reads from existing `.env`)
- `services/market_data_service.py` — `get_credit_rating()` + `sync_symbol()` added
- `main.py` — 3 new `_load()` calls, lifespan wiring, `/sync` endpoint

### Fixed
- `credit_rating` NULL rate reduced — Finnhub provides ratings for most
  investment-grade securities (previously all 3 providers returned NULL)
- Agent 03 BBB- quality gate now operational

### No breaking changes
- All existing endpoint response contracts unchanged
- Existing provider cascade (Polygon → FMP → yfinance) unchanged

---

## [1.0.0] — 2025-12-XX

### Added
- Market Data Service initial deployment
- Multi-provider price cascade: Polygon.io → FMP → yfinance
- Endpoints: price, history, history/stats, history/refresh, dividends,
  fundamentals, etf, providers/status, cache/stats
- Valkey cache integration
- PostgreSQL persistence for price and price_history
