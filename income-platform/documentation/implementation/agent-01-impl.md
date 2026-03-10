# Implementation Specification — Agent 01: Market Data Service v1.1.0

**Version:** 1.1.0
**Date:** 2026-03-09
**Status:** Built + 76/76 tests passing — pending deploy

---

## File Changes Summary

### New files

| File | Lines est. | Purpose |
|------|-----------|---------|
| `fetchers/finnhub_client.py` | ~80 | Finnhub credit rating fetcher |
| `repositories/securities_repository.py` | ~90 | Upsert to `platform_shared.securities` |
| `repositories/features_repository.py` | ~110 | Upsert to `platform_shared.features_historical` |

### Modified files

| File | Change |
|------|--------|
| `config.py` | `finnhub_api_key: str = ""` added |
| `models.py` | `SyncResponse` Pydantic model added |
| `services/market_data_service.py` | `get_credit_rating()` + `sync_symbol()` added |
| `main.py` | 3 new `_load()` calls, lifespan wiring, `/sync` endpoint, lazy upserts |

---

## Technical Design

### File structure (flat — no app/ subdirectory)

```
src/market-data-service/
├── config.py                              ← + finnhub_api_key
├── main.py                                ← + loads, /sync endpoint, lazy upserts
├── models.py                              ← + SyncResponse
├── fetchers/
│   ├── base_provider.py                   (unchanged)
│   ├── polygon_client.py                  (unchanged)
│   ├── fmp_client.py                      (unchanged)
│   ├── yfinance_client.py                 (unchanged)
│   ├── alpha_vantage.py                   (legacy, unchanged)
│   └── finnhub_client.py                  ← NEW
├── repositories/
│   ├── price_repository.py                (unchanged)
│   ├── price_history_repository.py        (unchanged)
│   ├── securities_repository.py           ← NEW
│   └── features_repository.py             ← NEW
├── services/
│   ├── price_service.py                   (unchanged)
│   └── market_data_service.py             ← + 2 methods
└── tests/unit/market-data/
    ├── test_finnhub_client.py             ← NEW (13 tests)
    ├── test_features_repository.py        ← NEW (23 tests)
    └── test_market_data_service_helpers.py ← NEW (40 tests)
```

### Module load order in main.py

```python
# New loads — added after existing _router load
_finn  = _load("fetchers.finnhub_client",
               _DIR / "fetchers" / "finnhub_client.py")
_srep  = _load("repositories.securities_repository",
               _DIR / "repositories" / "securities_repository.py")
_frep  = _load("repositories.features_repository",
               _DIR / "repositories" / "features_repository.py")
```

### Lifespan wiring

```python
market_data_service = MarketDataService(
    price_history_repo=price_history_repo,
    cache_manager=cache_manager,
    polygon_api_key=settings.polygon_api_key,
    fmp_api_key=settings.fmp_api_key,
    finnhub_api_key=settings.finnhub_api_key,    # NEW
    securities_repo=SecuritiesRepository(...),   # NEW
    features_repo=FeaturesRepository(...),       # NEW
)
```

---

## `fetchers/finnhub_client.py`

```python
GET https://finnhub.io/api/v1/stock/metric
    ?symbol={symbol}&metric=all&token={api_key}

# Extraction path:
response["metric"]["creditRating"]  → "BBB-" | "A+" | None

# Error handling:
# HTTP 401/403  → log warning, return None (bad key)
# HTTP 429      → log warning, return None (rate limit)
# Any exception → log error, return None (never raise)
# _last_request_time tracked (consistent with other clients)
```

---

## `repositories/securities_repository.py`

```python
class SecuritiesRepository:
    async def upsert_security(
        symbol, name, asset_type, sector, exchange,
        currency, expense_ratio, aum_millions
    ) -> None

# SQL:
INSERT INTO platform_shared.securities
    (symbol, name, asset_type, sector, exchange,
     currency, expense_ratio, aum_millions, updated_at)
VALUES ($1, $2, ...)
ON CONFLICT (symbol) DO UPDATE SET
    name = EXCLUDED.name,
    asset_type = EXCLUDED.asset_type,
    sector = EXCLUDED.sector,
    exchange = EXCLUDED.exchange,
    expense_ratio = EXCLUDED.expense_ratio,
    aum_millions = EXCLUDED.aum_millions,
    updated_at = NOW()
WHERE EXCLUDED.name IS NOT NULL

# Always fire-and-forget: catch Exception, log, return None
```

---

## `repositories/features_repository.py`

```python
class FeaturesRepository:
    async def upsert_features(
        symbol, as_of_date, yield_trailing_12m,
        yield_5yr_avg, div_cagr_5y, chowder_number,
        payout_ratio, pe_ratio, credit_rating,
        credit_quality_proxy, interest_coverage,
        advisor_coverage_count, missing_feature_ratio
    ) -> None

# Credit quality helper (private):
def _credit_quality_from_rating(rating: str) -> str:
    # AAA, AA+, AA, AA-, A+, A, A-, BBB+, BBB, BBB- → INVESTMENT_GRADE
    # BB+, BB, BB-                                   → BORDERLINE
    # B+ and below, CCC, CC, C, D                   → SPECULATIVE_GRADE

def _credit_quality_from_coverage(coverage: float) -> str:
    # >= 3.0  → INVESTMENT_GRADE
    # 1.5–2.9 → BORDERLINE
    # < 1.5   → SPECULATIVE_GRADE

def compute_credit_quality_proxy(rating, coverage) -> Optional[str]:
    # rating takes precedence; coverage is fallback; None if both absent
```

---

## `services/market_data_service.py` additions

### `get_credit_rating(symbol) -> Optional[str]`

```python
async def get_credit_rating(self, symbol: str) -> Optional[str]:
    if not self._finnhub:
        return None
    return await self._finnhub.get_credit_rating(symbol)
```

### `sync_symbol(symbol) -> dict`

```python
async def sync_symbol(self, symbol: str) -> dict:
    providers_used = []
    missing_fields = []

    # Step 1: fundamentals
    fundamentals = await self.get_fundamentals(symbol)
    if fundamentals:
        providers_used.append("fmp")

    # Step 2: dividend history → compute yield metrics
    dividends = await self.get_dividend_history(symbol)
    yield_trailing_12m = _compute_yield_trailing_12m(dividends, current_price)
    div_cagr_5y        = _compute_div_cagr_5y(dividends)
    yield_5yr_avg      = _compute_yield_5yr_avg(dividends, price_history)

    # Step 3: credit rating
    credit_rating = await self.get_credit_rating(symbol)
    if credit_rating:
        providers_used.append("finnhub")

    # Step 4: derived fields
    chowder_number = (
        round(yield_trailing_12m + div_cagr_5y, 2)
        if yield_trailing_12m is not None and div_cagr_5y is not None
        else None    # NULL, not 0.0
    )
    credit_quality_proxy = compute_credit_quality_proxy(
        credit_rating,
        fundamentals.get("interest_coverage")
    )

    # Step 5–6: upsert (fire-and-forget wrappers)
    securities_updated = await self._securities_repo.upsert_security(...)
    features_updated   = await self._features_repo.upsert_features(...)

    # missing_fields: every field that is None
    for field_name, value in all_fields.items():
        if value is None:
            missing_fields.append(field_name)

    return {
        "symbol": symbol,
        "as_of_date": date.today().isoformat(),
        "securities_updated": securities_updated,
        "features_updated": features_updated,
        "credit_rating": credit_rating,
        "credit_quality_proxy": credit_quality_proxy,
        "chowder_number": chowder_number,
        "yield_5yr_avg": yield_5yr_avg,
        "providers_used": providers_used,
        "missing_fields": missing_fields,
    }
```

### Dividend helper functions (private)

```python
_normalise_dates(dividends)         → list with parsed date fields
_filter_by_range(dividends, years)  → filter to last N years
_compute_yield_trailing_12m(...)    → sum of last 12 months dividends / price
_compute_div_cagr_5y(...)           → CAGR of annual dividend over 5 years
_compute_yield_5yr_avg(...)         → avg annual yield over 5 years
```

---

## Testing

### New test files — 76 tests, all passing

| File | Tests | Coverage |
|------|-------|---------|
| `test_finnhub_client.py` | 13 | Happy path, HTTP 401/403/429, None paths, session lifecycle |
| `test_features_repository.py` | 23 | `_credit_quality_from_rating` all S&P buckets + edge cases, `_credit_quality_from_coverage` boundary values, `compute_credit_quality_proxy` |
| `test_market_data_service_helpers.py` | 40 | `_normalise_dates`, `_filter_by_range`, `_compute_yield_trailing_12m`, `_compute_div_cagr_5y`, `_compute_yield_5yr_avg` |

### Acceptance Criteria (Testable)

- [ ] `POST /stocks/JEPI/sync` returns 200 with `features_updated: true`
- [ ] `platform_shared.securities` has row for JEPI after sync
- [ ] `platform_shared.features_historical` has row for JEPI with today's date after sync
- [ ] `chowder_number` is NULL (not 0.0) when `div_cagr_5y` unavailable
- [ ] `GET /stocks/JEPI/fundamentals` populates `securities` row (lazy upsert)
- [ ] `GET /api/v1/providers/status` includes `finnhub` key
- [ ] Provider status failure does not affect price/history endpoints
- [ ] All 76 unit tests pass

### Known Edge Cases

| Edge Case | Handling |
|-----------|---------|
| IPO < 5 years | `yield_5yr_avg` uses available years only; `div_cagr_5y` → NULL |
| No dividend history | `chowder_number` → NULL; `missing_fields` includes both inputs |
| Finnhub rate limit (429) | Returns None; proxy computed from `interest_coverage` |
| Finnhub bad key (401) | Returns None; logged as warning |
| `interest_coverage` also None | `credit_quality_proxy` → NULL |
| DB down during sync | `securities_updated: false`, `features_updated: false`; API still returns 200 |
| Symbol not in Finnhub universe | Returns None gracefully |

---

## Deployment

### Environment variable
`FINNHUB_API_KEY` already present in `.env` on server — no change needed.

### Deploy command
```bash
ssh -i ~/.ssh/id_ed25519 root@legatoinvest.com \
  "cd /opt/Agentic/income-platform && \
   git pull origin main && \
   docker compose up -d --build agent-01-market-data"
```

### Verify
```bash
curl https://legatoinvest.com/api/agent-01/api/v1/providers/status
# Expect: finnhub key present in response

curl -X POST https://legatoinvest.com/api/agent-01/stocks/JEPI/sync
# Expect: securities_updated: true, features_updated: true
```
