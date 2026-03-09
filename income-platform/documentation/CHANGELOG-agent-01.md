# CHANGELOG — Agent 01: Market Data Service

---

## [1.1.0] — 2026-03-09

### Added
- **Finnhub client** (`fetchers/finnhub_client.py`) — credit rating via
  `/stock/metric` endpoint; graceful degradation (None on any error)
- **Securities repository** (`repositories/securities_repository.py`) — upserts
  to `platform_shared.securities` ON CONFLICT; fire-and-forget safe
- **Features repository** (`repositories/features_repository.py`) — writes full
  feature vector to `platform_shared.features_historical`; credit quality proxy
  logic with full S&P rating bucket mapping
- **`POST /stocks/{symbol}/sync`** — full feature sync endpoint; calls
  fundamentals → dividends → Finnhub → upsert securities + features_historical
- **`finnhub_api_key`** config field (reads `FINNHUB_API_KEY` from `.env`)
- **`SyncResponse`** model with `missing_fields` list
- **Lazy securities upsert** on `GET /fundamentals` and `GET /etf` (fire-and-forget)
- **Finnhub** added to `/api/v1/providers/status` response
- **76 new unit tests** across 3 new test files (all passing)

### Changed
- `services/market_data_service.py` — added `get_credit_rating()` and
  `sync_symbol()` methods
- `main.py` — 3 new module loads, lifespan wiring for new repos, new endpoint

### Fixed
- `credit_rating` was returning NULL from all providers — resolved via Finnhub
- Agent 03 BBB- quality gate now unblocked for investment-grade issuers

### Derived Computations
- `chowder_number = yield_trailing_12m + div_cagr_5y` (NULL if either input NULL)
- `yield_5yr_avg` = mean of last 5 annual dividend yields
- `credit_quality_proxy` from Finnhub rating → interest_coverage fallback → NULL

---

## [1.0.0] — 2025-12-XX

### Added
- Initial deployment
- Multi-provider architecture: Polygon → FMP → yfinance
- Alpha Vantage for current price (legacy)
- Endpoints: price, history, history/stats, history/refresh, dividends,
  fundamentals, etf, providers/status, cache/stats
