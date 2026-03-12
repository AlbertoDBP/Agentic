# Agent 01: Market Data Service

Real-time and historical market data API for stocks, ETFs, and funds. Provides current prices, historical OHLCV data, dividend history, fundamental metrics, and ETF holdings.

**Port:** 8001
**Base URL:** `http://<host>:8001`

## Health Check

### GET /health

Service health check. Does not require authentication.

**Response 200:**
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected"
}
```

**Possible statuses:** `healthy`, `degraded`, `unhealthy`

---

## Current Price

### GET /stocks/{symbol}/price

Fetch the latest market price for a stock or ETF symbol.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol (case-insensitive, normalized to uppercase) |

**Response 200:**
```json
{
  "symbol": "AAPL",
  "price": 182.50,
  "source": "alpha_vantage",
  "cached": false,
  "timestamp": "2026-03-12T10:00:00Z"
}
```

**Errors:**
- 404: Symbol not found
- 500: All market data providers unreachable

---

## Historical Prices

### GET /stocks/{symbol}/history

Retrieve historical OHLCV (open, high, low, close, volume) prices for a symbol over a date range.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol (case-insensitive) |

**Query parameters:**
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| start_date | date | Yes | - | Start date (YYYY-MM-DD format) |
| end_date | date | Yes | - | End date (YYYY-MM-DD format) |
| limit | integer | No | 90 | Max records to return (1-365) |

**Response 200:**
```json
{
  "symbol": "AAPL",
  "start_date": "2026-01-01",
  "end_date": "2026-03-12",
  "count": 52,
  "prices": [
    {
      "date": "2026-01-01",
      "open": 185.25,
      "high": 186.50,
      "low": 184.75,
      "close": 185.80,
      "volume": 52000000
    }
  ],
  "source": "alpha_vantage"
}
```

**Errors:**
- 400: `start_date` is after `end_date`
- 404: Symbol not found
- 500: Provider unreachable

---

## Historical Statistics

### GET /stocks/{symbol}/history/stats

Calculate min, max, average, volatility, and price change percentage for a stock over a date range.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol |

**Query parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| start_date | date | Yes | Start date (YYYY-MM-DD) |
| end_date | date | Yes | End date (YYYY-MM-DD) |

**Response 200:**
```json
{
  "symbol": "AAPL",
  "period_days": 71,
  "min_price": 178.50,
  "max_price": 190.25,
  "avg_price": 184.37,
  "volatility": 3.42,
  "price_change_pct": 2.85
}
```

Volatility is calculated as the standard deviation of daily closing prices. Price change is `(last_close - first_close) / first_close * 100`.

**Errors:**
- 400: `start_date` is after `end_date`
- 404: Symbol not found or insufficient data

---

## Refresh Historical Data

### POST /stocks/{symbol}/history/refresh

Force-fetch historical price data from the source and persist to the database. Bypasses cache.

**Auth:** Required
**Method:** POST

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol |

**Request body:**
```json
{
  "full_history": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| full_history | boolean | false | If true, request up to 20 years of data (slower, higher API quota usage) |

**Response 200:**
```json
{
  "symbol": "AAPL",
  "records_saved": 100,
  "source": "alpha_vantage",
  "message": "Refreshed recent 100 days for AAPL: 100 records saved"
}
```

**Errors:**
- 502: API provider (Alpha Vantage) unreachable
- 500: Database write failure

---

## Dividend History

### GET /stocks/{symbol}/dividends

Retrieve dividend payment history for a stock symbol.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol |

**Response 200:**
```json
{
  "symbol": "JNJ",
  "count": 48,
  "dividends": [
    {
      "ex_dividend_date": "2026-03-12",
      "payment_date": "2026-03-20",
      "record_date": "2026-03-15",
      "dividend_per_share": 1.73
    }
  ],
  "source": "fmp"
}
```

Provider strategy: **FMP (primary) → yfinance (fallback)**

**Errors:**
- 404: Symbol not found or no dividend history available

---

## Fundamentals

### GET /stocks/{symbol}/fundamentals

Retrieve key fundamental metrics for a stock symbol.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol |

**Response 200:**
```json
{
  "symbol": "JNJ",
  "pe_ratio": 28.45,
  "debt_to_equity": 0.65,
  "payout_ratio": 0.62,
  "free_cash_flow": 27500000000,
  "market_cap": 420000000000,
  "sector": "Healthcare",
  "source": "fmp"
}
```

Provider strategy: **FMP (primary) → yfinance (fallback)**

Any unavailable field is returned as `null`.

**Errors:**
- 404: Symbol not found

---

## ETF Holdings & Data

### GET /stocks/{symbol}/etf

Retrieve ETF metadata and top holdings for a fund symbol.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Fund symbol (e.g., JEPI, SCHD) |

**Response 200:**
```json
{
  "symbol": "JEPI",
  "expense_ratio": 0.0035,
  "aum": 18500000000,
  "covered_call": true,
  "top_holdings": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "sector": "Technology",
      "weight_pct": 3.25
    }
  ],
  "source": "fmp"
}
```

Provider strategy: **FMP (primary) → yfinance (fallback)**

**Returns:** Expense ratio (decimal %), AUM (dollars), covered call flag, up to 20 top holdings

**Errors:**
- 404: Symbol not found or not a recognized ETF

---

## Provider Status

### GET /api/v1/providers/status

Return health and activity status for all configured market data providers.

**Auth:** Required
**Method:** GET

**Response 200:**
```json
{
  "polygon": {
    "healthy": true,
    "last_used": "2026-03-12T09:58:30Z"
  },
  "fmp": {
    "healthy": true,
    "last_used": "2026-03-12T09:59:15Z"
  },
  "yfinance": {
    "healthy": true,
    "last_used": null
  },
  "finnhub": {
    "healthy": true,
    "last_used": "2026-03-12T09:57:00Z"
  }
}
```

| Field | Description |
|-------|-------------|
| healthy | True when the provider was successfully initialized at startup |
| last_used | ISO-8601 UTC timestamp of the most recent API call, or null if no call yet |

---

## Sync Symbol

### POST /stocks/{symbol}/sync

Fetch and persist key features for a stock symbol to platform-wide tables (fundamentals, dividends, credit rating).

**Auth:** Required
**Method:** POST

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| symbol | string | Ticker symbol |

**Request body:** Empty (POST with no body)

**Response 200:**
```json
{
  "symbol": "JNJ",
  "features_synced": 8,
  "message": "Synced fundamentals, dividends, and credit rating for JNJ"
}
```

Calls: fundamentals → dividend history → credit rating (via Finnhub), then upserts to platform_shared tables. All DB writes are fire-and-forget; errors are logged but not surfaced in the response.

**Errors:**
- 500: Unexpected sync error

---

## Cache Statistics

### GET /api/v1/cache/stats

Retrieve Redis cache statistics and hit rates (development/debugging endpoint).

**Auth:** Required
**Method:** GET

**Response 200:**
```json
{
  "hits": 1250,
  "misses": 340,
  "hit_rate": 0.786,
  "keys": 145,
  "memory_used_mb": 12.5
}
```

**Errors:**
- 500: Cache not initialized or unavailable
