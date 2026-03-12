# API Quick Start Guide

Get up and running with the Income Fortress Platform API in 5 minutes.

## Prerequisites

- All 6 services running on their designated ports (8001-8006)
- JWT_SECRET environment variable set on each service
- Valid JWT token for authentication

## Step 1: Generate a JWT Token

```python
import base64
import hashlib
import hmac
import json
import time

secret = "your-jwt-secret"  # From JWT_SECRET env var
user_id = "user-123"
expires_in = 3600  # 1 hour

header = base64.urlsafe_b64encode(
    json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
).rstrip(b"=").decode()

payload = base64.urlsafe_b64encode(
    json.dumps({
        "sub": user_id,
        "exp": int(time.time()) + expires_in,
    }).encode()
).rstrip(b"=").decode()

signature = base64.urlsafe_b64encode(
    hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
).rstrip(b"=").decode()

token = f"{header}.{payload}.{signature}"
print(f"Token: {token}")
```

Or use PyJWT:

```python
import jwt
import time

token = jwt.encode(
    {"sub": "user-123", "exp": int(time.time()) + 3600},
    "your-jwt-secret",
    algorithm="HS256"
)
```

## Step 2: Check Service Health

```bash
# All services have health checks (no auth required)
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
curl http://localhost:8006/health
```

## Step 3: Fetch Market Data (Agent 01)

```bash
TOKEN="your-jwt-token"

# Get current stock price
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JNJ/price

# Get historical prices
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/stocks/JNJ/history?start_date=2026-01-01&end_date=2026-03-12"

# Get fundamentals
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JNJ/fundamentals

# Get dividend history
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JNJ/dividends
```

## Step 4: Classify Asset (Agent 04)

```bash
# Classify a single ticker
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "JNJ"}' \
  http://localhost:8004/classify
```

## Step 5: Score Income Asset (Agent 03)

```bash
# Run quality gate first
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "JNJ",
    "asset_class": "DIVIDEND_STOCK",
    "credit_rating": "AAA",
    "consecutive_positive_fcf_years": 15,
    "dividend_history_years": 60
  }' \
  http://localhost:8003/quality-gate/evaluate

# Then score the asset
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "JNJ",
    "asset_class": "DIVIDEND_STOCK",
    "gate_data": {
      "credit_rating": "AAA",
      "consecutive_positive_fcf_years": 15,
      "dividend_history_years": 60
    }
  }' \
  http://localhost:8003/scores/evaluate
```

## Step 6: Get Tax Profile (Agent 05)

```bash
# Get tax treatment for a symbol
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8005/tax/profile/JNJ?filing_status=MARRIED_FILING_JOINTLY&state_code=CA"

# Calculate after-tax distribution
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "JNJ",
    "distribution_amount": 3.25,
    "annual_income": 200000,
    "filing_status": "MARRIED_FILING_JOINTLY",
    "state_code": "CA",
    "account_type": "TAXABLE"
  }' \
  http://localhost:8005/tax/calculate
```

## Step 7: Run Stress Test (Agent 06)

```bash
# First, get available scenarios
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8006/scenarios/library

# Run a stress test
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
    "scenario_type": "RATE_HIKE_200BPS",
    "save": false
  }' \
  http://localhost:8006/scenarios/stress-test

# Project income
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
    "horizon_months": 12
  }' \
  http://localhost:8006/scenarios/income-projection
```

## Step 8: Get Analyst Signals (Agent 02)

```bash
# Get all active analysts
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/analysts

# Get recommendations for a ticker
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/recommendations/JNJ

# Get consensus score
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/consensus/JNJ

# Get complete analyst signal (consumed by proposal engine)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/signal/JNJ
```

## Common Workflows

### Workflow 1: Score a Dividend Stock

```bash
TOKEN="..."

# 1. Get fundamentals from market data
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JNJ/fundamentals

# 2. Evaluate quality gate
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}' \
  http://localhost:8003/quality-gate/evaluate

# 3. Run income score
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}' \
  http://localhost:8003/scores/evaluate

# 4. Get latest score
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/scores/JNJ
```

### Workflow 2: Evaluate Tax Impact

```bash
TOKEN="..."

# 1. Get tax profile
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8005/tax/profile/JNJ?filing_status=SINGLE&state_code=CA"

# 2. Calculate after-tax return
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}' \
  http://localhost:8005/tax/calculate

# 3. Optimize portfolio allocation
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}' \
  http://localhost:8005/tax/optimize
```

### Workflow 3: Analyze Portfolio Risk

```bash
TOKEN="..."

# 1. Run stress test
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": "...",
    "scenario_type": "RATE_HIKE_200BPS"
  }' \
  http://localhost:8006/scenarios/stress-test

# 2. Project income
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": "...",
    "horizon_months": 12
  }' \
  http://localhost:8006/scenarios/income-projection

# 3. Rank vulnerabilities
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": "..."
  }' \
  http://localhost:8006/scenarios/vulnerability
```

## Environment Variables

Set these before running:

```bash
# Each service needs JWT_SECRET
export JWT_SECRET="your-32-character-minimum-random-secret"

# Database connection (service-specific)
export DATABASE_URL="postgresql://user:pass@localhost/income_platform"

# Redis cache (shared)
export REDIS_URL="redis://localhost:6379"

# API keys for market data providers
export POLYGON_API_KEY="..."
export FMP_API_KEY="..."
export FINNHUB_API_KEY="..."
export ALPHA_VANTAGE_API_KEY="..."
```

## Troubleshooting

**"Invalid or expired token"**
- Regenerate token with correct JWT_SECRET
- Check token expiration: decode at https://jwt.io

**"Symbol not found"**
- Agent 01 hasn't ingested data for this symbol yet
- Run `POST /stocks/{symbol}/sync` to trigger fetch

**"Port already in use"**
- Change port in service config or kill existing process
- Ensure all 6 services are on their designated ports (8001-8006)

**"Database connection failed"**
- Verify DATABASE_URL is correct
- Ensure PostgreSQL is running and accessible
- Check credentials

**"Provider API unreachable"**
- Check provider status page (Polygon, FMP, Alpha Vantage, Finnhub)
- Verify API keys are set correctly
- Check internet connectivity

## Next Steps

1. Read the full [API Documentation](./README.md)
2. Review endpoint-specific docs for each agent:
   - [Agent 01: Market Data](./agent-01-market-data.md)
   - [Agent 02: Newsletter Ingestion](./agent-02-newsletter.md)
   - [Agent 03: Income Scoring](./agent-03-scoring.md)
   - [Agent 04: Asset Classification](./agent-04-classification.md)
   - [Agent 05: Tax Optimization](./agent-05-tax.md)
   - [Agent 06: Scenario Simulation](./agent-06-simulation.md)
3. Explore interactive API docs at `http://localhost:PORT/docs` (Swagger UI)
4. Check [Error Codes](./errors.md) for debugging help
5. Review [Authentication Guide](./authentication.md) for token management

## Support

- Check recent issues in the repository
- Review service logs: `docker logs <service-name>`
- Check health endpoints: `curl http://localhost:PORT/health`
- Open an issue with detailed error logs and reproduction steps

Happy coding!
