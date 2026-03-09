# Functional Specification — Agent 01: Market Data Service

**Version:** 1.1.0
**Date:** 2026-03-09
**Port:** 8001
**Status:** ✅ Deployed — v1.1.0 update ready for deployment

---

## Purpose & Scope

Agent 01 is the data foundation of the Income Fortress Platform. It is the sole
service responsible for fetching, caching, and persisting market data from external
providers. All other agents consume data that Agent 01 has written to the shared
database or cache.

**v1.1.0 additions:**
- Finnhub as 4th provider for credit ratings
- `platform_shared.securities` auto-population (lazy upsert)
- `platform_shared.features_historical` population via `/sync` endpoint
- SEC EDGAR interest coverage proxy fallback for credit quality

---

## Responsibilities

1. Fetch current price data (Polygon → FMP → yfinance cascade)
2. Fetch and persist historical OHLCV price data
3. Fetch dividend history and compute yield metrics
4. Fetch fundamental metrics (PE, payout ratio, debt/equity, FCF)
5. Fetch ETF metadata and top holdings
6. **[v1.1.0]** Fetch credit ratings from Finnhub
7. **[v1.1.0]** Upsert ticker metadata to `platform_shared.securities` (lazy, on every fundamentals/ETF call)
8. **[v1.1.0]** Write full feature vector to `platform_shared.features_historical` (via `/sync`)
9. Manage Valkey cache with configurable TTL
10. Report provider health status

---

## Provider Cascade

| Data Type | Primary | Secondary | Tertiary | Quaternary |
|-----------|---------|-----------|----------|------------|
| Price (current) | Alpha Vantage (legacy) | — | — | — |
| Price (history) | Polygon | FMP | yfinance | — |
| Dividends | FMP | yfinance | — | — |
| Fundamentals | FMP | yfinance | — | — |
| ETF metadata | FMP | yfinance | — | — |
| Credit rating | Finnhub | — | — | — |
| Credit proxy | interest_coverage (FMP) | — | — | — |

---

## Endpoints

### Existing (unchanged)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stocks/{symbol}/price` | Current price (cache → DB → Alpha Vantage) |
| GET | `/stocks/{symbol}/history` | Historical OHLCV |
| GET | `/stocks/{symbol}/history/stats` | Price statistics over date range |
| POST | `/stocks/{symbol}/history/refresh` | Force-refresh from Alpha Vantage |
| GET | `/stocks/{symbol}/dividends` | Dividend payment history |
| GET | `/stocks/{symbol}/fundamentals` | Key fundamental metrics |
| GET | `/stocks/{symbol}/etf` | ETF metadata + top holdings |
| GET | `/api/v1/providers/status` | Provider health status |
| GET | `/api/v1/cache/stats` | Cache statistics |

### New (v1.1.0)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/stocks/{symbol}/sync` | Full feature sync → writes securities + features_historical |

---

## `/stocks/{symbol}/sync` — Detail

**Trigger:** Manual or scheduled. Called by Agent 03 pipeline before scoring
when features are stale.

**Sequence:**
```
1. get_fundamentals()      → name, sector, payout_ratio, pe_ratio, interest_coverage
2. get_dividend_history()  → yield_trailing_12m, div_cagr_5y, yield_5yr_avg
3. get_credit_rating()     → Finnhub → credit_rating TEXT
4. compute derived fields  → chowder_number, credit_quality_proxy
5. upsert_security()       → platform_shared.securities
6. upsert_features()       → platform_shared.features_historical
```

**Derived computations:**
- `chowder_number = yield_trailing_12m + div_cagr_5y` (NULL if either input NULL)
- `yield_5yr_avg` = mean of last 5 annual dividend yields from history
- `credit_quality_proxy`:
  - From Finnhub rating: BBB- and above → INVESTMENT_GRADE; BB+/BB/BB- → BORDERLINE; B+ and below → SPECULATIVE_GRADE
  - Fallback from `interest_coverage`: ≥3.0 → INVESTMENT_GRADE; 1.5–2.99 → BORDERLINE; <1.5 → SPECULATIVE_GRADE
  - NULL if no data available

**Response:**
```json
{
  "symbol": "JEPI",
  "as_of_date": "2026-03-09",
  "securities_updated": true,
  "features_updated": true,
  "credit_rating": "A-",
  "credit_quality_proxy": "INVESTMENT_GRADE",
  "chowder_number": 14.2,
  "yield_5yr_avg": 0.0821,
  "providers_used": ["fmp", "finnhub"],
  "missing_fields": []
}
```

---

## Lazy Securities Upsert

`GET /stocks/{symbol}/fundamentals` and `GET /stocks/{symbol}/etf` automatically
call `upsert_security()` after a successful provider response. Fire-and-forget —
errors logged, never surfaced to caller. This ensures `platform_shared.securities`
is populated for any ticker that has been queried, without requiring an explicit
`/sync` call.

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| Polygon.io API key | Historical prices |
| Financial Modeling Prep API key | Fundamentals, dividends, ETF |
| Alpha Vantage API key | Current price (legacy) |
| Finnhub API key | Credit ratings |
| PostgreSQL `platform_shared` schema | Persistence |
| Valkey cache | Price + score TTL management |

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| `/sync` latency | ≤ 5s p95 (3 sequential API calls) |
| Price endpoint latency | ≤ 500ms p95 (cache hit) |
| Securities upsert | Fire-and-forget, ≤ 50ms |
| Finnhub error handling | Returns None, never raises |
| Cache TTL | Configurable, default 300s (price), 24h (health score link) |

---

## Success Criteria

- `POST /sync` populates both `securities` and `features_historical` for any valid ticker
- `credit_rating` non-NULL for investment-grade issuers via Finnhub
- `credit_quality_proxy` non-NULL for any ticker with FMP fundamentals (coverage proxy fallback)
- `chowder_number` non-NULL for tickers with ≥5yr dividend history
- Lazy upsert does not increase latency of fundamentals/ETF endpoints by more than 50ms
- All 76 unit tests pass
- Zero breaking changes to existing endpoint contracts
