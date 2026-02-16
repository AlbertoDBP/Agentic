# Market Data Service (Agent 01) - Functional Specification

**Version:** 1.0  
**Status:** Ready for Implementation  
**Last Updated:** 2026-02-13

## Purpose & Scope

The Market Data Service provides real-time and historical market data to the Income Fortress platform by fetching, normalizing, and synchronizing data from multiple external providers into a unified database with intelligent caching.

### Responsibilities
- Fetch daily price data (OHLCV) from external APIs
- Collect dividend calendar information  
- Retrieve ETF holdings composition data
- Normalize data from multiple providers
- Cache frequently accessed data in Redis
- Prevent duplicate database entries
- Handle provider failures gracefully
- Expose REST API for data access

### In Scope
- US stock and ETF price data
- Dividend calendar and payment information
- ETF look-through holdings data
- Multi-provider fallback support
- Redis caching layer
- Scheduled background synchronization
- REST API endpoints

### Out of Scope (Future Phases)
- Real-time streaming prices (WebSocket)
- Options chain data
- International markets
- Fundamental data (P/E ratios, earnings)
- News sentiment integration

## Interfaces

### REST API Endpoints

#### Health Check
```
GET /health
Response: 200 OK
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "providers": {
    "alpha_vantage": "operational"
  },
  "last_sync": "2026-02-13T16:00:00Z"
}
```

#### Current Price
```
GET /api/v1/price/{ticker}
Response: 200 OK
{
  "ticker": "AAPL",
  "price": 182.45,
  "change": 1.23,
  "change_percent": 0.68,
  "volume": 45678900,
  "timestamp": "2026-02-13T20:00:00Z",
  "source": "alpha_vantage",
  "cached": true
}
```

#### Historical Prices
```
GET /api/v1/price/{ticker}/history?start_date=2026-01-01&end_date=2026-02-13
Response: 200 OK
{
  "ticker": "AAPL",
  "data": [
    {
      "date": "2026-02-13",
      "open": 181.20,
      "high": 183.50,
      "low": 180.90,
      "close": 182.45,
      "volume": 45678900
    }
  ],
  "count": 32
}
```

#### Dividend Calendar
```
GET /api/v1/dividends/{ticker}
Response: 200 OK
{
  "ticker": "AAPL",
  "dividends": [
    {
      "ex_dividend_date": "2026-02-07",
      "payment_date": "2026-02-14",
      "amount": 0.25,
      "frequency": "quarterly"
    }
  ]
}
```

#### Manual Sync Trigger
```
POST /api/v1/sync/trigger
Body: {"tickers": ["AAPL", "MSFT", "GOOGL"]}
Response: 202 Accepted
{
  "job_id": "uuid",
  "status": "queued",
  "tickers": 3
}
```

### Database Schema (Already Exists)

**market_data_daily**
- ticker_symbol (VARCHAR, indexed)
- trade_date (DATE, indexed)
- open_price, high_price, low_price, close_price (DECIMAL)
- volume (BIGINT)
- adjusted_close (DECIMAL)
- UNIQUE(ticker_symbol, trade_date)

**dividend_calendar**
- ticker_symbol (VARCHAR, indexed)
- ex_dividend_date (DATE, indexed)
- payment_date (DATE)
- amount (DECIMAL)
- frequency (VARCHAR)
- UNIQUE(ticker_symbol, ex_dividend_date)

**etf_look_through_data**
- etf_ticker (VARCHAR)
- underlying_ticker (VARCHAR)
- weight_percent (DECIMAL)
- as_of_date (DATE)
- UNIQUE(etf_ticker, underlying_ticker, as_of_date)

### External API Providers

**Alpha Vantage** (Primary)
- Endpoint: `https://www.alphavantage.co/query`
- Rate Limit: 500 calls/day (free tier)
- Functions: TIME_SERIES_DAILY, DIVIDEND
- API Key: From MARKET_DATA_API_KEY env var

**Polygon.io** (Backup)
- Endpoint: `https://api.polygon.io/v2/`
- Rate Limit: 5 calls/minute (free tier)
- Used for: Real-time prices, fallback

**Yahoo Finance** (Fallback)
- Library: yfinance
- Rate Limit: ~10/minute (unofficial)
- Used for: Dividend data, international stocks

## Dependencies

### External Services
- PostgreSQL database (DATABASE_URL)
- Valkey/Redis cache (REDIS_URL)  
- Alpha Vantage API (MARKET_DATA_API_KEY)

### Internal Services
- None (foundational service)

### Consumed By
- NAV Erosion Service (historical prices for simulations)
- Income Scoring Service (dividend data for feature engineering)
- Alert System (price drops, dividend cuts)

## Success Criteria

### Functional
- [x] Fetch price data from Alpha Vantage
- [x] Store data in PostgreSQL without duplicates
- [x] Cache current prices in Redis (TTL: 5min)
- [x] Return cached data when available
- [x] Handle API failures gracefully
- [x] Sync minimum 50 tickers successfully

### Performance
- [x] API response: <100ms (cached), <500ms (database)
- [x] Cache hit rate: >90% for current prices
- [x] Sync throughput: >50 tickers/minute
- [x] Database query: <200ms for 30 days of data

### Reliability
- [x] Auto-fallback when primary provider fails
- [x] Retry failed requests (3 attempts, exponential backoff)
- [x] Circuit breaker prevents cascading failures
- [x] Service uptime: 99.5%+

## Non-Functional Requirements

### Performance
- Handle 1000 concurrent API requests
- Batch database inserts (100 records/transaction)
- Connection pooling (min: 5, max: 20)

### Scalability
- Stateless design (can run multiple instances)
- Horizontal scaling via load balancer
- Database sharding by ticker symbol (future)

### Security
- API keys in environment variables (never hardcoded)
- Input validation on all endpoints
- Rate limiting: 60 requests/minute per IP
- No authentication required (internal service)

### Monitoring
- Log all external API calls
- Track cache hit/miss rates
- Monitor database connection pool
- Alert on sync failures (>5 consecutive)

### Data Quality
- Validate price data (no negative prices, volume > 0)
- Cross-check between providers when available
- Log discrepancies >1% between sources
- Backfill missing data automatically

## Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Cache  
REDIS_URL=rediss://default:pass@host:port

# API Keys
MARKET_DATA_API_KEY=your_alpha_vantage_key

# Service Config
SERVICE_PORT=8001
LOG_LEVEL=INFO
MARKET_DATA_SYNC_INTERVAL=300  # seconds

# Feature Flags
ENABLE_POLYGON=false
ENABLE_YAHOO_FINANCE=false
```

### Sync Schedule
- **Market Hours (9:30 AM - 4:00 PM ET):** Every 5 minutes
- **After Hours:** Every 1 hour
- **Weekends:** Every 6 hours (cache warmup only)

## Error Handling

### Provider Failures
```python
if alpha_vantage_fails:
    try polygon_io
    if polygon_fails:
        try yahoo_finance
        if all_fail:
            return cached_data or error_response
```

### Rate Limits
```python
if rate_limit_hit:
    wait = exponential_backoff(attempt_number)
    sleep(wait)
    retry()
    if max_retries_exceeded:
        switch_to_backup_provider()
```

### Database Errors
```python
if db_connection_lost:
    trigger_circuit_breaker()
    alert_operations_team()
    serve_from_cache_only()
```

## Testing Strategy

### Unit Tests
- Test each API client independently
- Mock external API responses
- Validate data normalization
- Test cache operations
- Test error handling paths

### Integration Tests
- Test with real Alpha Vantage API (sandbox)
- Verify database persistence
- Test cache invalidation
- Test provider fallback logic

### Load Tests
- 1000 concurrent requests
- Sustained 100 req/sec for 5 minutes
- Database connection pool exhaustion
- Cache eviction under load

## Deployment Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Redis cache accessible
- [ ] Alpha Vantage API key valid
- [ ] Health check passing
- [ ] Sync scheduler started
- [ ] Logs streaming to monitoring
- [ ] Alerts configured

## Future Enhancements

### Phase 2
- Polygon.io integration
- Yahoo Finance fallback
- International markets

### Phase 3
- WebSocket streaming prices
- Options chain data
- Fundamental data integration

### Phase 4
- Machine learning for data quality
- Predictive caching
- Multi-region deployment
