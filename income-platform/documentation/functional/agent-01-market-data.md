# Functional Specification — Agent 01: Market Data Service

**Version:** 1.1.0
**Date:** 2026-03-09
**Status:** v1.0.0 deployed → v1.1.0 pending deploy
**Port:** 8001
**Service directory:** `src/market-data-service/`

---

## Purpose & Scope

Agent 01 is the data foundation of the Income Fortress Platform. It fetches,
caches, and persists market data from multiple external providers. In v1.1.0 it
gains two new responsibilities:

1. **Securities registry population** — auto-upserts to `platform_shared.securities`
   on every fundamentals and ETF fetch (lazy, fire-and-forget)
2. **Feature history writing** — full feature sync via `POST /stocks/{symbol}/sync`,
   writing to `platform_shared.features_historical` including Chowder Number,
   5yr avg yield, and credit quality proxy

---

## Responsibilities

### v1.0.0 (existing, unchanged)
- Fetch current prices — Polygon → FMP → yfinance cascade
- Fetch historical OHLCV prices
- Fetch dividend history
- Fetch fundamentals (PE, payout ratio, debt/equity, FCF, market cap, sector)
- Fetch ETF metadata and top holdings
- Cache all responses in Valkey (TTL configurable)
- Persist price and price history to database

### v1.1.0 (new)
- Fetch credit ratings from Finnhub (4th provider)
- Compute `credit_quality_proxy` from rating or FMP `interest_coverage` fallback
- Compute `chowder_number` = `yield_trailing_12m + div_cagr_5y`
- Compute `yield_5yr_avg` from last 5 years of annual dividend yield history
- Auto-upsert symbol metadata to `platform_shared.securities` (lazy, on fundamentals + ETF)
- Write full feature vector to `platform_shared.features_historical` (via /sync)

---

## Provider Cascade

### Price data
```
Polygon.io → FMP → yfinance
```

### Fundamentals & dividends
```
FMP → yfinance
```

### Credit rating (v1.1.0)
```
Finnhub → None
    ↓ if None: FMP interest_coverage proxy
        ≥ 3.0   → INVESTMENT_GRADE
        1.5–2.9  → BORDERLINE
        < 1.5   → SPECULATIVE_GRADE
        None    → NULL (credit_quality_proxy = NULL)
```

---

## Endpoints

### Existing (unchanged response contracts)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/stocks/{symbol}/price` | — |
| GET | `/stocks/{symbol}/history` | — |
| GET | `/stocks/{symbol}/history/stats` | — |
| POST | `/stocks/{symbol}/history/refresh` | — |
| GET | `/stocks/{symbol}/dividends` | — |
| GET | `/stocks/{symbol}/fundamentals` | + lazy securities upsert (v1.1.0) |
| GET | `/stocks/{symbol}/etf` | + lazy securities upsert (v1.1.0) |
| GET | `/api/v1/providers/status` | + Finnhub status (v1.1.0) |
| GET | `/api/v1/cache/stats` | — |

### New (v1.1.0)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/stocks/{symbol}/sync` | Full feature sync → securities + features_historical |

---

## `/stocks/{symbol}/sync` Sequence

```
1. get_fundamentals()      → name, sector, payout_ratio, pe_ratio, interest_coverage
2. get_dividend_history()  → yield_trailing_12m, div_cagr_5y, yield_5yr_avg
3. get_credit_rating()     → Finnhub credit_rating TEXT
4. Compute derived fields:
   - chowder_number       = yield_trailing_12m + div_cagr_5y (NULL if either absent)
   - yield_5yr_avg        = avg of last 5 annual yields (from dividend history)
   - credit_quality_proxy = from rating → from interest_coverage → NULL
5. upsert_security()       → platform_shared.securities (ON CONFLICT UPDATE)
6. upsert_features()       → platform_shared.features_historical (ON CONFLICT UPDATE)
```

### SyncResponse model

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

`missing_fields` — lists every field that returned None. Gives Agent 03 and
Agent 12 full visibility into data gaps per symbol before scoring.

---

## Lazy Securities Upsert (Option C)

`GET /fundamentals` and `GET /etf` both call `SecuritiesRepository.upsert_security()`
after a successful fetch. Pattern:

- Fire-and-forget: exceptions caught, logged, never raised to API caller
- Fields: `name`, `sector`, `exchange`, `expense_ratio` (ETF), `aum_millions` (ETF)
- `ON CONFLICT (symbol) DO UPDATE WHERE EXCLUDED.name IS NOT NULL`
- Safe to call on every request — idempotent

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| Polygon.io | Price data (primary) |
| FMP | Fundamentals, dividends, ETF (primary) |
| yfinance | Fallback for all FMP endpoints |
| Finnhub | Credit ratings (NEW v1.1.0) |
| Valkey | Response cache |
| PostgreSQL `platform_shared` | `securities`, `features_historical`, price tables |

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| `/sync` latency | ≤ 5s p95 (4 sequential external calls) |
| Lazy upsert overhead | ≤ 50ms added to fundamentals/ETF endpoints |
| Existing endpoint latency | Unchanged from v1.0.0 |
| DB write failure isolation | Never affects API response — logged only |
| `chowder_number` nullability | NULL when either `yield_trailing_12m` or `div_cagr_5y` absent |
