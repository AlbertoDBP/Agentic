# Implementation Specification — Historical Price Queries
**Component:** Market Data Service (Agent 01)
**Version:** 1.2.0
**Date:** 2026-02-23
**Status:** Implemented ✅

---

## Purpose & Scope

Adds historical OHLCV price range query capability to the Market Data Service. Enables downstream agents — particularly Agent 03 Income Scorer and the NAV Erosion Analyzer — to retrieve, analyze, and compute statistics on historical price data.

---

## Components Implemented

### 1. PriceHistory ORM Model (`orm_models.py`)

```python
class PriceHistory(Base):
    __tablename__ = "price_history"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open_price = Column(Numeric(12, 4))
    high_price = Column(Numeric(12, 4))
    low_price = Column(Numeric(12, 4))
    close_price = Column(Numeric(12, 4))
    adjusted_close = Column(Numeric(12, 4))
    volume = Column(BigInteger)
    data_source = Column(String(50), default="alpha_vantage")
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_price_history_symbol_date"),
    )
```

**Key design:** Unique constraint on `(symbol, date)` enables safe upserts — duplicate inserts update existing records rather than failing.

---

### 2. PriceHistoryRepository (`repositories/price_history_repository.py`)

| Method | Description |
|--------|-------------|
| `save_price_record(symbol, date, data)` | Single record upsert |
| `get_price_range(symbol, start, end)` | Range query ordered by date ASC |
| `get_latest_price(symbol)` | Most recent record |
| `bulk_save_prices(symbol, records)` | Batch upsert for efficiency |

**Upsert pattern:** `INSERT ... ON CONFLICT (symbol, date) DO UPDATE` — idempotent, safe to call repeatedly.

---

### 3. Alpha Vantage Integration (`fetchers/alpha_vantage.py`)

**Endpoint used:** `TIME_SERIES_DAILY` (free tier)
**Endpoint avoided:** `TIME_SERIES_DAILY_ADJUSTED` (premium — returns 402)

**Rate limiter fix:**
```python
class AlphaVantageClient:
    _last_request_time: float = None  # CLASS variable — shared across all instances
    
    async def _rate_limit(self):
        min_interval = max(60 / self.calls_per_minute, 1.1)  # Hard floor: 1.1s
        # ... enforce interval
```

**Redis caching:** 4-hour TTL for historical data (changes less frequently than quotes).

---

### 4. Service Layer (`services/market_data_service.py`)

**`get_historical_prices(symbol, start_date, end_date)`**
- Check DB first for existing records in range
- If within 140-day window and DB empty: fetch from Alpha Vantage, upsert, return
- If older than 140 days: return DB data only (compact window limitation)

**`refresh_historical_prices(symbol, full_history=False)`**
- Always uses `outputsize="compact"` (full is premium)
- Force-fetches from Alpha Vantage regardless of DB state
- Bulk upserts all returned records

**`get_price_statistics(symbol, start_date, end_date)`**
- Computes from DB data: min, max, avg close, volatility (std dev), price change %
- Pure DB computation — no API call

---

### 5. API Endpoints (`main.py`)

**Final route structure:**
```
GET  /health
GET  /stocks/{symbol}/price
GET  /stocks/{symbol}/history       ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&limit=90
GET  /stocks/{symbol}/history/stats ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
POST /stocks/{symbol}/history/refresh
GET  /api/v1/cache/stats
```

**Nginx routing note:** Public URL is `https://legatoinvest.com/api/market-data/stocks/{symbol}/history`. Nginx strips `/api/market-data/` before forwarding to the container. Service routes must NOT include this prefix.

**Error handling:**
- `ValueError` from Alpha Vantage (rate limits, API errors) → HTTP 502 with AV message
- Missing symbol → HTTP 404
- Date range validation → HTTP 422

---

## Database Migration

**Migration ID:** `a218ef2b914c`
**File:** `src/market-data-service/migrations/versions/a218ef2b914c_create_price_history_table.py`

```bash
# Apply migration
alembic upgrade head

# Verify
alembic current
```

---

## Testing & Acceptance

### Unit Tests
- `PriceHistoryRepository` upsert — duplicate (symbol, date) updates, not inserts
- `PriceHistoryRepository` range query — returns records ordered by date ASC
- `AlphaVantageClient` rate limiter — class variable shared across instances
- `AlphaVantageClient` daily price parsing — correct field mapping
- Statistics calculation — min, max, avg, volatility, price change %

### Integration Tests
- `GET /stocks/AAPL/history?start_date=2025-11-01&end_date=2025-11-30` → 19 records
- `GET /stocks/AAPL/history/stats` → non-null min, max, avg, volatility
- `POST /stocks/AAPL/history/refresh` → records saved, no duplicates
- Request older than 140 days → returns DB data or empty array (no AV call)

### Acceptance Criteria (Validated in Production)
- [x] `/stocks/AAPL/history` returns 19 records for November 2025
- [x] Stats: min $266.25, max $278.85, avg $271.66, volatility 3.77, change +3.64%
- [x] Duplicate inserts do not create duplicate rows
- [x] Cache hit on second identical request
- [x] Service starts without hanging on VPC Valkey connection

### Known Edge Cases
- **Weekends/holidays:** Trading days only — count will be less than calendar days
- **140-day boundary:** Requests spanning the boundary return partial data from DB
- **Rate limit hit:** Returns HTTP 502 with Alpha Vantage error message
- **`adjusted_close`:** Populated with `close` value (free tier limitation)

---

## Production Validation (2026-02-23)

```bash
# Verified on droplet
curl "http://localhost:8001/stocks/AAPL/history?start_date=2025-11-01&end_date=2025-11-30"
# → count: 19, source: alpha_vantage

curl "http://localhost:8001/stocks/AAPL/history/stats?start_date=2025-11-01&end_date=2025-11-30"
# → min: 266.25, max: 278.85, avg: 271.6563, volatility: 3.7708, change: 3.6424%

curl "http://localhost:8001/stocks/AAPL/price"
# → price: 264.35, source: database

curl "http://localhost:8001/api/v1/cache/stats"
# → connected: true, hit_rate: 27.27%
```

---
