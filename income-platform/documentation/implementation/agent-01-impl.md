# Implementation Specification — Agent 01: Market Data Service v1.1.0

**Version:** 1.1.0
**Date:** 2026-03-09
**Status:** Built — 76/76 tests passing — Ready for deployment

---

## File Structure

```
src/market-data-service/           ← flat structure, no app/ subdirectory
├── config.py                      ← +finnhub_api_key
├── main.py                        ← +3 loads, +sync endpoint, +lazy upserts
├── models.py                      ← +SyncResponse
├── cache.py
├── database.py
├── orm_models.py
├── fetchers/
│   ├── base_provider.py
│   ├── alpha_vantage.py           (legacy/reference)
│   ├── polygon_client.py
│   ├── fmp_client.py
│   ├── yfinance_client.py
│   ├── finnhub_client.py          ← NEW v1.1.0
│   └── provider_router.py
├── repositories/
│   ├── price_repository.py
│   ├── price_history_repository.py
│   ├── securities_repository.py   ← NEW v1.1.0
│   └── features_repository.py    ← NEW v1.1.0
├── services/
│   ├── price_service.py
│   └── market_data_service.py     ← +get_credit_rating(), +sync_symbol()
└── tests/
    └── unit/
        └── market-data/
            ├── test_finnhub_client.py             ← NEW (13 tests)
            ├── test_features_repository.py        ← NEW (23 tests)
            └── test_market_data_service_helpers.py ← NEW (40 tests)
```

---

## New File Details

### `fetchers/finnhub_client.py`

```python
# Key API call
GET https://finnhub.io/api/v1/stock/metric
    ?symbol={symbol}&metric=all&token={api_key}

# Extraction path
response["metric"]["creditRating"]  # → "BBB-" | "A+" | None

# Error handling: all exceptions caught, None returned
# _last_request_time tracked (consistent with other clients)
```

### `repositories/securities_repository.py`

```python
# Core upsert — only updates non-NULL fields
INSERT INTO platform_shared.securities
    (symbol, name, asset_type, sector, exchange, currency,
     expense_ratio, aum_millions, updated_at)
VALUES ($1, $2, ...)
ON CONFLICT (symbol) DO UPDATE SET
    name = EXCLUDED.name,
    ...
    updated_at = NOW()
WHERE EXCLUDED.name IS NOT NULL

# Uses asyncpg directly via session_factory (consistent with existing repos)
# All exceptions caught and logged — never raised
```

### `repositories/features_repository.py`

```python
# Credit quality proxy logic (tested in 23 unit tests)
S&P rating buckets:
    AAA, AA+, AA, AA-, A+, A, A-, BBB+, BBB, BBB- → INVESTMENT_GRADE
    BB+, BB, BB-                                   → BORDERLINE
    B+, B, B-, CCC+, CCC, CCC-, CC, C, D          → SPECULATIVE_GRADE

Interest coverage fallback (when Finnhub returns None):
    >= 3.0   → INVESTMENT_GRADE
    1.5-2.99 → BORDERLINE
    < 1.5    → SPECULATIVE_GRADE

chowder_number:
    = yield_trailing_12m + div_cagr_5y  if both non-None
    = None                               if either is None
```

---

## Modified File Details

### `config.py`

```python
finnhub_api_key: str = ""   # reads FINNHUB_API_KEY from .env
```

### `models.py` — SyncResponse

```python
class SyncResponse(BaseModel):
    symbol: str
    as_of_date: date
    securities_updated: bool
    features_updated: bool
    credit_rating: Optional[str]
    credit_quality_proxy: Optional[str]
    chowder_number: Optional[float]
    yield_5yr_avg: Optional[float]
    providers_used: list[str]
    missing_fields: list[str]   # every field that returned None
```

### `services/market_data_service.py`

```python
# New method 1
async def get_credit_rating(symbol: str) -> Optional[str]:
    # Calls FinnhubClient
    # Returns rating string or None (never raises)

# New method 2
async def sync_symbol(symbol: str) -> dict:
    # 1. get_fundamentals()      → name, sector, pe_ratio,
    #                               payout_ratio, interest_coverage
    # 2. get_dividend_history()  → yield_trailing_12m, div_cagr_5y
    #                               yield_5yr_avg (computed from 5yr window)
    # 3. get_credit_rating()     → credit_rating
    # 4. compute chowder_number, credit_quality_proxy
    # 5. securities_repo.upsert_security()
    # 6. features_repo.upsert_features()
    # 7. return SyncResponse fields dict
    # missing_fields populated for every None value
```

### `main.py`

```python
# New loads (follow existing _load pattern)
_finn  = _load("fetchers.finnhub_client",
               _DIR / "fetchers" / "finnhub_client.py")
_srep  = _load("repositories.securities_repository",
               _DIR / "repositories" / "securities_repository.py")
_frep  = _load("repositories.features_repository",
               _DIR / "repositories" / "features_repository.py")

# Lifespan wiring: FinnhubClient + SecuritiesRepository + FeaturesRepository
# passed to MarketDataService constructor

# New endpoint
@app.post("/stocks/{symbol}/sync", response_model=SyncResponse)
async def sync_symbol(symbol: str): ...

# Lazy upsert (fire-and-forget) added to:
@app.get("/stocks/{symbol}/fundamentals")  # after successful response
@app.get("/stocks/{symbol}/etf")           # after successful response

# Provider status: Finnhub added to ProvidersStatusResponse
```

---

## Testing

### Test Coverage (76 tests)

| File | Tests | Coverage |
|------|-------|---------|
| `test_finnhub_client.py` | 13 | get_credit_rating happy path, HTTP 401/403/429, None paths, session lifecycle |
| `test_features_repository.py` | 23 | _credit_quality_from_rating (all S&P buckets + edge cases), _credit_quality_from_coverage (boundary values), compute_credit_quality_proxy |
| `test_market_data_service_helpers.py` | 40 | _normalise_dates, _filter_by_range, _compute_yield_trailing_12m, _compute_div_cagr_5y, _compute_yield_5yr_avg |

### Key Edge Cases Covered

| Edge Case | Expected Behavior |
|-----------|-----------------|
| Finnhub returns empty metric object | None returned |
| Finnhub HTTP 429 (rate limit) | None returned, logged |
| Finnhub HTTP 401 (bad key) | None returned, logged |
| `div_cagr_5y` is None | `chowder_number` = None (not 0.0) |
| `yield_trailing_12m` is None | `chowder_number` = None |
| < 5 years dividend history | `yield_5yr_avg` computed from available years |
| 0 years dividend history | `yield_5yr_avg` = None |
| `interest_coverage` exactly 3.0 | INVESTMENT_GRADE |
| `interest_coverage` exactly 1.5 | BORDERLINE |
| Unknown rating string | SPECULATIVE_GRADE (safe default) |
| Both Finnhub and coverage None | `credit_quality_proxy` = None |
| `upsert_security` DB error | Logged, never raised to caller |

### Acceptance Criteria (Testable)

- [ ] `POST /stocks/JEPI/sync` returns 200 with `securities_updated: true`
- [ ] `platform_shared.securities` contains JEPI row after sync
- [ ] `platform_shared.features_historical` contains JEPI row with today's date
- [ ] `credit_rating` non-NULL for JEPI (investment grade via Finnhub)
- [ ] `chowder_number` non-NULL for JEPI (≥5yr dividend history)
- [ ] `GET /stocks/JEPI/fundamentals` still returns same contract as v1.0.0
- [ ] `GET /api/v1/providers/status` includes `finnhub` key
- [ ] All 76 unit tests pass in CI

---

## Deployment

### Pre-deployment checks
```bash
# Verify FINNHUB_API_KEY in .env on server
ssh -i ~/.ssh/id_ed25519 root@legatoinvest.com \
  "grep FINNHUB .env /opt/Agentic/income-platform/.env"

# Verify new tables exist (migration already run)
# securities, features_historical confirmed in production
```

### Deploy commands
```bash
# Push from Mac
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform
git add src/market-data-service/
git commit -m "feat(agent-01): v1.1.0 - Finnhub + securities + features_historical"
git push origin main

# Pull and restart on server
ssh -i ~/.ssh/id_ed25519 root@legatoinvest.com
cd /opt/Agentic/income-platform
git pull origin main
docker compose restart agent-01-market-data
docker compose logs -f agent-01-market-data
```

### Smoke test after deploy
```bash
# Test sync endpoint
curl -X POST https://legatoinvest.com/api/agent-01/stocks/JEPI/sync

# Verify securities table populated
docker exec agent-01-market-data python3 -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ['DATABASE_URL'].split('?')[0]
    conn = await asyncpg.connect(url, ssl='require')
    row = await conn.fetchrow(
        \"SELECT * FROM platform_shared.securities WHERE symbol = 'JEPI'\"
    )
    print(row)
    await conn.close()
asyncio.run(check())
"
```

---

## Implementation Notes

- `yield_5yr_avg` computed from dividend history window — FMP provides up to 10yr
  history; if <5yr available, average over available years (not NULL)
- `missing_fields` in SyncResponse lists every field that returned None — allows
  Agent 03 to know data quality before scoring
- Lazy upsert on fundamentals/ETF endpoints adds ≤50ms (single asyncpg execute,
  fire-and-forget, does not block response)
- FinnhubClient follows identical pattern to `base_provider.py` — `_last_request_time`
  tracked for `/api/v1/providers/status` reporting
