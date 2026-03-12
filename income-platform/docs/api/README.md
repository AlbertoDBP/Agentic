# Income Fortress Platform API Documentation

Welcome to the API documentation for the Income Fortress income-platform. This document provides an overview of all six microservices and their endpoints.

## Platform Overview

The Income Fortress platform is a distributed income investment intelligence system composed of six microservices, each responsible for a distinct phase of the investment analysis pipeline.

### Microservices Architecture

| Agent | Service | Port | Purpose |
|-------|---------|------|---------|
| Agent 01 | Market Data Service | 8001 | Real-time & historical market data, fundamentals, dividends |
| Agent 02 | Newsletter Ingestion | 8002 | Analyst recommendations, consensus, and signals |
| Agent 03 | Income Scoring | 8003 | Quality gates & weighted scoring for income assets |
| Agent 04 | Asset Classification | 8004 | Asset class inference and classification rules |
| Agent 05 | Tax Optimization | 8005 | Tax treatment, account placement, loss harvesting |
| Agent 06 | Scenario Simulation | 8006 | Stress testing, income projection, vulnerability analysis |

## Base URL Pattern

All services follow this URL pattern:

```
http://<host>:<port>/
```

Example for Agent 01 on localhost:

```
http://localhost:8001/
```

## Authentication

All endpoints (except `/health`) require a JWT Bearer token passed in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

**Token Type:** HS256 (HMAC with SHA-256)
**Secret:** Environment variable `JWT_SECRET`
**Format:** Standard JWT with 3 dot-separated segments (header.payload.signature)

For token generation and validation details, see [Authentication Guide](./authentication.md).

## Response Codes

All services use standardized HTTP status codes:

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Request succeeded, response body contains data |
| 201 | Created | Resource created (rare in this API) |
| 400 | Bad Request | Invalid query params, malformed request body, validation error |
| 401 | Unauthorized | Missing or invalid JWT token |
| 403 | Forbidden | Token valid but insufficient permissions |
| 404 | Not Found | Resource does not exist (ticker not found, no historical data, etc.) |
| 422 | Unprocessable Entity | Request is well-formed but semantically invalid (e.g., quality gate fails) |
| 500 | Internal Server Error | Unexpected server error, upstream service unavailable |
| 502 | Bad Gateway | Upstream provider (e.g., FMP API) unreachable |
| 503 | Service Unavailable | Service is degraded or temporarily unavailable |

## Standard Error Response

All error responses follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

For complex validation errors (especially 422), the `detail` field may contain a nested structure with additional context.

## Service Documentation

- **[Agent 01: Market Data Service](./agent-01-market-data.md)** - Stock prices, historical data, dividends, fundamentals, ETF holdings
- **[Agent 02: Newsletter Ingestion](./agent-02-newsletter.md)** - Analyst profiles, recommendations, consensus scores, signals
- **[Agent 03: Income Scoring](./agent-03-scoring.md)** - Quality gates, income scoring, NAV erosion analysis
- **[Agent 04: Asset Classification](./agent-04-classification.md)** - Asset class detection, rules, overrides
- **[Agent 05: Tax Optimization](./agent-05-tax.md)** - Tax profiles, calculations, portfolio optimization, loss harvesting
- **[Agent 06: Scenario Simulation](./agent-06-simulation.md)** - Stress testing, income projection, vulnerability ranking

## Common Patterns

### Pagination & Filtering

Most list endpoints support:

- **`limit`** (query param): Maximum number of results to return
- **`offset`** (query param): Number of results to skip (for pagination)
- **Filtering**: Service-specific filter parameters (e.g., `recommendation=BUY`, `active_only=true`)

### Caching

- Market data is cached for 5-60 minutes depending on the endpoint
- Analyst signals are cached for 1 hour
- Cache hits are transparent to the client
- Use `force_refresh=true` query parameter to bypass cache (where supported)

### Rate Limiting

The platform does not implement endpoint-level rate limiting. External provider APIs (Polygon, FMP, Finnhub, Alpha Vantage) have their own rate limits. The services implement fallback strategies and graceful degradation.

### Concurrency

Services handle concurrent requests safely. All database operations are ACID-compliant. Async I/O is used where beneficial (e.g., fetching from multiple providers in parallel).

## Development & Testing

### Quick Start

1. Ensure all services are running on their designated ports
2. Generate or obtain a valid JWT token (see [Authentication Guide](./authentication.md))
3. Test health endpoints first:

   ```bash
   curl http://localhost:8001/health
   curl http://localhost:8002/health
   # etc.
   ```

4. Make authenticated requests:

   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/stocks/AAPL/price
   ```

### Interactive API Documentation

Each service publishes OpenAPI (Swagger) documentation at:

```
http://<host>:<port>/docs
```

You can use the Swagger UI to explore endpoints, read schemas, and test requests interactively (requires a valid JWT token).

## Error Handling & Debugging

See [Error Codes & Troubleshooting](./errors.md) for:

- Complete list of error codes used across all services
- Common causes and solutions
- Debugging strategies
- Provider-specific failure modes

## Integration Flow

Typical client integration sequence:

1. **Score a ticker** (Agent 03):
   - POST `/quality-gate/evaluate` (if gate data unavailable)
   - POST `/scores/evaluate` with fundamental data from Agent 01

2. **Get analyst signals** (Agent 02):
   - GET `/signal/{ticker}` to fetch the strongest recommendation

3. **Optimize portfolio** (Agent 05):
   - POST `/tax/optimize` with holdings list

4. **Run stress test** (Agent 06):
   - POST `/scenarios/stress-test` with portfolio and scenario

## Support & Documentation

For detailed endpoint specifications, request/response schemas, and examples:

- Check the service-specific documentation pages linked above
- Review the OpenAPI schema at `/docs` on any service
- Check recent commits and PR descriptions in the repository

Last updated: 2026-03-12
