# Error Codes and Troubleshooting

All API errors follow a standard response format. This document describes common errors, their causes, and solutions.

## Standard Error Response

All error responses use this format:

```json
{
  "detail": "Human-readable error message describing what went wrong"
}
```

For validation errors (422), the `detail` field may contain nested structure:

```json
{
  "detail": {
    "message": "Quality gate failed for TICKER",
    "fail_reasons": ["Dividend history < 10 years", "Free cash flow volatile"]
  }
}
```

---

## HTTP Status Codes

### 200 OK
Request succeeded, response body contains the requested data.

### 201 Created
Resource was created successfully. Rare in this API.

### 400 Bad Request
The request was malformed or contained invalid parameters.

**Common causes:**
- Missing required query parameter
- Invalid date format (expected YYYY-MM-DD)
- Invalid enum value (e.g., asset_class="UNKNOWN")
- start_date is after end_date
- Invalid batch size (> max allowed)

**Example:**
```json
{
  "detail": "start_date must be before end_date"
}
```

**Solution:**
- Review the endpoint documentation
- Verify all required parameters are present
- Check data types and formats match the specification

---

### 401 Unauthorized
Missing or invalid JWT authentication token.

**Common causes:**
- No `Authorization` header in request
- Malformed token (missing dot separators)
- Token signature is invalid (wrong JWT_SECRET)
- Token has expired (check `exp` claim)

**Example:**
```json
{
  "detail": "Invalid or expired token"
}
```

**Solution:**
1. Verify the `Authorization: Bearer <token>` header is present
2. Generate a new token using the correct JWT_SECRET
3. Check token expiration: decode at https://jwt.io and verify `exp` timestamp is in the future
4. Ensure all services use the same JWT_SECRET

---

### 403 Forbidden
Token is valid but insufficient permissions. Currently not used; reserved for future RBAC.

---

### 404 Not Found
The requested resource does not exist.

**Common causes:**
- Stock symbol not found in market data provider (Agent 01)
- Analyst ID does not exist (Agent 02)
- No historical price data for the symbol and date range (Agent 01)
- No score has been calculated yet for this ticker (Agent 03)
- Override not found for this ticker (Agent 04)
- Portfolio not found (Agent 06)

**Example (Agent 01):**
```json
{
  "detail": "Symbol INVALID not found"
}
```

**Solution:**
1. Verify the symbol/ID is correct
2. For Agent 01: ensure the symbol has been ingested (check provider status at `/api/v1/providers/status`)
3. For Agent 03: run `POST /scores/evaluate` first to create a score
4. For Agent 04: run `POST /classify` first to classify the ticker

---

### 422 Unprocessable Entity
The request was syntactically valid but semantically invalid.

**Common causes (by service):**

**Agent 03 (Scoring):**
- No passing quality gate found + no gate_data provided
- Quality gate evaluation failed (invalid credit rating, insufficient dividend history)
- Batch size exceeds maximum

**Agent 04 (Classification):**
- Batch size exceeds maximum (100)
- Invalid rule_type
- confidence_weight outside 0-1 range

**Agent 05 (Tax):**
- Asset class is not provided and Agent 04 fails to classify
- Invalid filing status or account type

**Agent 06 (Simulation):**
- Portfolio has no open positions
- Invalid scenario parameters
- Batch size exceeds maximum

**Example (Agent 03):**
```json
{
  "detail": {
    "message": "Quality gate failed for TICKER",
    "fail_reasons": ["Credit rating below BBB-", "Dividend history < 10 years"]
  }
}
```

**Solution:**
1. For quality gates: provide valid gate_data with required fields
2. For batch requests: reduce batch size to ≤ limit
3. Check fail_reasons for specific validation failures
4. Ensure data completeness (credit ratings, dividend history, etc.)

---

### 500 Internal Server Error
An unexpected server error occurred.

**Common causes:**
- Database connection lost
- Unhandled exception in business logic
- Required service dependency is unavailable
- Memory/resource exhaustion

**Example:**
```json
{
  "detail": "Internal server error"
}
```

**Solution:**
1. Check service logs: `docker logs <service-container>`
2. Verify database connectivity: check the `/health` endpoint
3. Retry the request (transient failures are common)
4. Contact support if error persists

---

### 502 Bad Gateway
Upstream service or API provider is unreachable.

**Common causes:**
- Market data provider (Polygon, FMP, Alpha Vantage, Finnhub) API is down
- Agent 01 cannot reach external provider to fetch prices/fundamentals
- Network connectivity issue

**Example:**
```json
{
  "detail": "Alpha Vantage API unreachable"
}
```

**Solution:**
1. Check provider status: `GET /api/v1/providers/status` (Agent 01)
2. Verify internet connectivity and firewall rules
3. Check provider status page (Polygon, FMP, Finnhub, Alpha Vantage)
4. Retry after provider recovers

---

### 503 Service Unavailable
The service is temporarily unavailable or degraded.

**Common causes:**
- Service is starting up (lifespan initialization)
- Cache or database temporarily unavailable
- High load causing resource exhaustion

**Example:**
```json
{
  "detail": "Service temporarily unavailable"
}
```

**Solution:**
1. Check `/health` endpoint to see which components are unhealthy
2. Wait for service to recover (usually a few seconds)
3. Retry the request
4. If persistent, check service logs and infrastructure

---

## Service-Specific Error Scenarios

### Agent 01: Market Data Service

**Error: "Symbol AAPL not found"**
- Status: 404
- Cause: Provider hasn't ingested data for this symbol yet
- Solution: Run `POST /stocks/{symbol}/sync` to trigger data fetch

**Error: "All providers failed"**
- Status: 500
- Cause: All configured market data providers are unreachable
- Solution: Check provider status, verify internet connectivity

**Error: "start_date must be before end_date"**
- Status: 400
- Cause: Query parameter order is incorrect
- Solution: Ensure start_date < end_date in YYYY-MM-DD format

---

### Agent 02: Newsletter Ingestion

**Error: "Analyst 123 not found"**
- Status: 404
- Cause: Analyst ID does not exist in database
- Solution: List active analysts with `GET /analysts`

**Error: "Analyst with SA ID john-smith already exists"**
- Status: 409
- Cause: Attempting to add a duplicate analyst
- Solution: Update existing analyst instead or use different SA ID

**Error: "No active recommendations found for ticker XYZ"**
- Status: 404
- Cause: No analyst recommendations exist yet
- Solution: Trigger `POST /flows/harvester/trigger` to ingest articles

---

### Agent 03: Income Scoring

**Error: "No passing quality gate record found for JNJ"**
- Status: 422
- Cause: No DB record + no gate_data provided
- Solution: Run `POST /quality-gate/evaluate` first, then score

**Error: "Quality gate failed" with fail_reasons**
- Status: 422
- Cause: Stock doesn't meet minimum criteria (credit rating, dividend history)
- Solution: Provide stronger fundamentals or try different ticker

**Error: "Failed to fetch market data"**
- Status: 500
- Cause: Agent 01 is unavailable or market data incomplete
- Solution: Check Agent 01 health, retry

---

### Agent 04: Asset Classification

**Error: "Batch size exceeds maximum 100"**
- Status: 422
- Cause: Too many tickers in single request
- Solution: Split into multiple batch requests

**Error: "rule_type must be one of..."**
- Status: 422
- Cause: Invalid rule type specified
- Solution: Use one of: ticker_pattern, sector, feature, metadata

---

### Agent 05: Tax Optimization

**Error: "Cannot determine asset class"**
- Status: 500
- Cause: Agent 04 classification service is unavailable
- Solution: Check Agent 04 health, retry

**Error: "Invalid filing status"**
- Status: 400
- Cause: Unsupported filing_status value
- Solution: Use one of: SINGLE, MARRIED_FILING_JOINTLY, MARRIED_FILING_SEPARATELY, HEAD_OF_HOUSEHOLD

---

### Agent 06: Scenario Simulation

**Error: "No open positions found for portfolio_id=..."**
- Status: 422
- Cause: Portfolio has no holdings or doesn't exist
- Solution: Verify portfolio_id is correct and contains positions

**Error: "Invalid scenario type UNKNOWN_SCENARIO"**
- Status: 422
- Cause: Scenario doesn't exist in library
- Solution: Use `GET /scenarios/library` to list valid scenarios or use "CUSTOM"

---

## Debugging Strategies

### 1. Check Service Health
Each service has a `/health` endpoint that reveals component status:

```bash
curl http://localhost:8001/health  # Agent 01
curl http://localhost:8002/health  # Agent 02
# etc.
```

Response shows database, cache, and provider connectivity.

### 2. Review Recent Commits
Check git log and pull requests for recent changes that may have introduced bugs.

### 3. Check Provider Status
For Agent 01 errors, verify provider availability:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/v1/providers/status
```

### 4. Examine Service Logs
View logs for detailed error traces:

```bash
docker logs <service-container>
# or
tail -f /var/log/income-platform/<service>.log
```

### 5. Validate Request Format
Use an HTTP client (Postman, Insomnia) to inspect:
- Headers (especially Authorization)
- Query parameters
- Request body (JSON structure)
- Content-Type header

### 6. Test with Mock Data
For development, bypass external dependencies:
- Use local market data cache
- Mock analyst recommendations
- Provide explicit gate_data to skip quality gate lookups

---

## Common Integration Mistakes

### Missing Authorization Header
```bash
# Wrong: no auth
curl http://localhost:8001/stocks/AAPL/price

# Right: with auth
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/AAPL/price
```

### Wrong Symbol Case
```bash
# Service normalizes to uppercase, but case-sensitive lookups may fail in some systems
curl http://localhost:8001/stocks/aapl/price  # May work
curl http://localhost:8001/stocks/AAPL/price  # Guaranteed to work
```

### Expired Token
```bash
# Generate new token before exp timestamp
python generate_token.py  # See authentication.md

# Or decode existing token to check expiry
python -c "import jwt; print(jwt.decode(token, options={'verify_signature': False})['exp'])"
```

### Invalid Date Range
```bash
# Wrong: start > end
curl "...?start_date=2026-03-12&end_date=2026-01-01"

# Right: start < end
curl "...?start_date=2026-01-01&end_date=2026-03-12"
```

### Batch Size Exceeded
```bash
# Wrong: too many items
{"tickers": [1, 2, 3, ..., 101]}  # > 100

# Right: within limit
{"tickers": [1, 2, ..., 50]}
```

---

## Support & Escalation

If you encounter an error not covered here:

1. **Check the documentation** for the specific endpoint
2. **Search recent issues** in the repository
3. **Review service logs** for detailed error traces
4. **Open an issue** with:
   - Full request (sanitized of secrets)
   - Full response including headers
   - Service logs
   - Reproduction steps
5. **Contact the team** with findings

Last updated: 2026-03-12
