# Implementation Specification — Multi-Provider Data Architecture
**Component:** Market Data Service (Agent 01)
**Version:** 2.0.0
**Date:** 2026-02-23
**Status:** Implemented ✅

---

## Purpose & Scope

Replaces single-provider Alpha Vantage architecture with a dual-primary + fallback system. Enables Agent 03 Income Scorer to access dividend history, payout ratios, fundamentals, and ETF holdings data unavailable on Alpha Vantage free tier.

---

## Components

### BaseDataProvider (`fetchers/base_provider.py`)

Abstract base class defining the provider contract:

```python
class BaseDataProvider(ABC):
    @abstractmethod
    async def get_current_price(symbol: str) -> dict
    @abstractmethod
    async def get_daily_prices(symbol: str, outputsize: str) -> list[dict]
    @abstractmethod
    async def get_dividend_history(symbol: str) -> list[dict]
    @abstractmethod
    async def get_fundamentals(symbol: str) -> dict
    @abstractmethod
    async def get_etf_holdings(symbol: str) -> dict
```

Default `__aenter__`/`__aexit__` — subclasses override only when managing HTTP sessions.

**Exceptions:**
- `ProviderError` — network errors, auth failures, rate limit hits
- `DataUnavailableError(ProviderError)` — symbol not found or data not offered by provider

---

### PolygonClient (`fetchers/polygon_client.py`)

| Method | Endpoint | Cache TTL |
|--------|----------|-----------|
| `get_current_price` | `/v2/last/trade/{symbol}` → snapshot fallback | 5 min |
| `get_daily_prices` | `/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}` | 5 min |
| `get_dividend_history` | `/v3/reference/dividends?ticker={symbol}` | 4 hr |
| `get_fundamentals` | `/vX/reference/financials` + `/v3/reference/tickers/{symbol}` (concurrent) | 24 hr |
| `get_etf_holdings` | Raises `DataUnavailableError` — not available | — |

Rate limiting: 100 req/min, class variable `_last_request_time`, hard floor 0.6s.
Auth: `Authorization: Bearer {key}` header.
TTM fundamentals computed from 4 quarterly periods.

---

### FMPClient (`fetchers/fmp_client.py`)

**Base URL:** `https://financialmodelingprep.com/stable` (migrated from legacy `/api/v3/`)

| Method | Endpoints | Cache TTL |
|--------|-----------|-----------|
| `get_current_price` | `/quote-short/{symbol}` | 5 min |
| `get_daily_prices` | `/historical-price-full/{symbol}` | 5 min |
| `get_dividend_history` | `/dividends?symbol={symbol}` | 4 hr |
| `get_fundamentals` | `/ratios`, `/cash-flow-statement`, `/profile` (concurrent) | 24 hr |
| `get_etf_holdings` | `/etf-holder` → 404 on Starter → `DataUnavailableError` | — |

Rate limiting: 300 req/min, class variable `_last_request_time`, hard floor 0.2s.
Auth: `apikey={key}` query parameter.

**Critical pattern:** `asyncio.gather(return_exceptions=True)` — if `/ratios` fails, re-raise as `ProviderError`. Silent null returns prevent fallback chain from activating.

**Field mappings (stable API):**

| Field | Stable API name |
|-------|----------------|
| `pe_ratio` | `priceToEarningsRatio` |
| `debt_to_equity` | `debtToEquityRatio` |
| `payout_ratio` | `dividendPayoutRatio` |
| `market_cap` | `marketCap` |

**Covered call detection (ETF):**
- Description contains: "covered call", "buy-write", "selling call option", "equity-linked note", "option"
- Company name contains: "premium income", "equity premium", "buy-write"
- Symbol in: `["JEPI", "JEPQ", "XYLD", "QYLD", "RYLD", "DIVO", "PBP", "BXMX"]`

---

### YFinanceClient (`fetchers/yfinance_client.py`)

All methods use `asyncio.to_thread()` — yfinance is synchronous, must not block event loop.
No rate limiting. No Redis caching (stale fallback data worse than fresh fetch).

| Method | yfinance source | Notes |
|--------|----------------|-------|
| `get_current_price` | `ticker.fast_info` | Lightweight |
| `get_daily_prices` | `ticker.history(period="3mo"/"2y", auto_adjust=True)` | `adjusted_close == close` |
| `get_dividend_history` | `ticker.dividends` + `ticker.actions` | `_infer_frequency` from avg gap |
| `get_fundamentals` | `ticker.info` | `trailingPE`, `debtToEquity`, `payoutRatio`, etc. |
| `get_etf_holdings` | `ticker.funds_data` + `ticker.info` | Primary for ETF data |

**ETF field mappings:**
- `expense_ratio` ← `ticker.info['netExpenseRatio']`
- `aum` ← `ticker.info['totalAssets']`
- `ticker` ← `funds_data.top_holdings` index (Symbol is the DataFrame index)
- `name` ← `funds_data.top_holdings['Name']` column

---

### ProviderRouter (`fetchers/provider_router.py`)

Async context manager. Calls `__aenter__`/`__aexit__` on each child provider. Failed init → provider set to `None`, silently skipped.

**Priority chains:**

| Method | Chain |
|--------|-------|
| `get_current_price` | Polygon → FMP → yfinance |
| `get_daily_prices` | Polygon → yfinance |
| `get_dividend_history` | FMP → yfinance |
| `get_fundamentals` | FMP → yfinance |
| `get_etf_holdings` | FMP → yfinance |

`_try_chain`: catches `ProviderError` and `DataUnavailableError` per attempt. Unexpected exceptions propagate immediately. On total failure, raises `ProviderError` with all failure messages concatenated.

Logging: `✅ get_current_price(AAPL) served by polygon` / `⚠️ get_current_price(AAPL): polygon failed`.

---

## Testing

### Unit Tests (33 passing)

**test_provider_router.py (8 tests)**
- `ProviderError` and `DataUnavailableError` both trigger fallback
- Polygon success skips FMP
- All-providers-fail raises combined `ProviderError`
- `get_daily_prices` chain is Polygon → yfinance (FMP not called)
- `get_dividend_history` chain is FMP → yfinance

**test_fmp_client.py (18 tests)**
- Dividend field mapping, frequency, yield_pct calculation
- ETF covered_call: JEPI true, SCHD false, buy-write, premium income, equity premium, ELN, known symbol list
- ETF weight decimal→percent conversion

**test_polygon_client.py (7 tests)**
- compact = 140-day window, full = 730-day window
- OHLCV field mapping, VWAP fallback, ms→date conversion

### Acceptance Criteria (Validated in Production 2026-02-23)

| Test | Result |
|------|--------|
| `GET /stocks/AAPL/fundamentals` | pe_ratio: 34.09, payout_ratio: 0.138, sector: Technology ✅ |
| `GET /stocks/AAPL/dividends` | 90 records back to 1987, payment_date populated ✅ |
| `GET /stocks/JEPI/etf` | covered_call: true, expense_ratio: 0.35, aum: $43.1B ✅ |
| `GET /stocks/SCHD/etf` | covered_call: false, expense_ratio: 0.06, aum: $78.4B ✅ |
| Polygon failure → FMP fallback | Confirmed via test suite ✅ |
| FMP failure → yfinance fallback | Confirmed via ETF holdings production behavior ✅ |

---

## Infrastructure Changes

- `docker-compose.yml` — added `POLYGON_API_KEY` and `FMP_API_KEY` to market-data-service environment
- `.env` (droplet + local) — `POLYGON_API_KEY`, `FMP_API_KEY` added
- `config.py` — both keys optional (empty string default); service starts gracefully with degraded provider set

---

## Known Issues / Future Work

- `credit_rating` — returns `None` from all providers on current tiers; Income Scorer Junk Filter blocked until resolved
- `requests_today` on `/api/v1/providers/status` — not yet implemented; needed for rate limit monitoring
- `docker-compose.yml` conflict — full-platform compose in GitHub conflicts with production-only version on droplet; needs permanent resolution

---
