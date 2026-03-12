# Troubleshooting Guide - Income Fortress Platform

A comprehensive operational reference for diagnosing and fixing common issues in the income-platform microservices architecture.

**Last Updated:** March 2026
**Target Audience:** DevOps, SRE, Backend Engineers, QA
**Services Covered:** Agent 01–06, Market Data Service

---

## Quick Navigation

### By Symptom Category

**[Service Startup Failures](./service-startup.md)**
- Container exits immediately with errors
- ModuleNotFoundError (jwt, psycopg2, python-multipart)
- Database connection refused at startup
- asyncpg dialect configuration errors
- Port already in use
- JWT_SECRET not configured

**[Database Connection Errors](./database.md)**
- Connection string format errors
- asyncpg vs psycopg2 dialect issues
- Connection pool exhaustion
- `platform_shared` schema not found
- SSL/TLS connection failures
- Migration failures

**[Authentication Errors](./authentication.md)**
- 401 Invalid token
- 403 Missing authorization header
- 503 JWT_SECRET not configured
- Token expired
- Token generated with wrong algorithm
- Auth module initialization failures

**[Docker & Deployment Issues](./docker-deployment.md)**
- Old image running after code changes
- git pull blocked by untracked files
- Service health check failing
- Environment variables not reaching containers
- Image caching problems
- Dockerfile layer conflicts

**[Test Failures](./tests.md)**
- pytest: command not found
- JWT_SECRET not set before app import
- sys.modules mock leakage between test files
- asyncpg pool mocking issues
- Fixture import ordering problems
- Test database connectivity

---

## Service Architecture Reference

### Deployment Structure

```
docker-compose.yml
├── market-data-service (Agent 01, port 8001)
├── agent-02-newsletter-ingestion (port 8002)
├── agent-03-income-scoring (port 8003)
├── agent-04-asset-classification (port 8004)
├── tax-optimization-service (Agent 05, port 8005)
└── agent-06-scenario-simulation (port 8006)

Backend Services:
├── PostgreSQL (database)
├── Redis/Valkey (cache)
└── External APIs
    ├── Polygon.io
    ├── Financial Modeling Prep (FMP)
    ├── Finnhub
    └── Alpha Vantage
```

### Health Check Endpoints

All services expose `/health` endpoint:

```bash
curl -s http://localhost:8001/health | jq .
curl -s http://localhost:8002/health | jq .
curl -s http://localhost:8003/health | jq .
```

Expected healthy response:
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected"
}
```

### Startup Dependencies

```
market-data-service (8001)
    ↓
depends_on_health_check
    ↓
agent-02-newsletter-ingestion (8002)
agent-03-income-scoring (8003)
agent-04-asset-classification (8004)
tax-optimization-service (8005)
agent-06-scenario-simulation (8006)
```

---

## Common Solutions

### Check Service Status

```bash
# View all running containers
docker compose ps

# View logs for specific service
docker compose logs market-data-service -f

# View all logs (follow)
docker compose logs -f
```

### View Environment Configuration

```bash
# See what environment variables were passed to a service
docker compose config | grep -A 20 "market-data-service:"

# Inspect a running container's environment
docker inspect <container-id> | jq '.[0].Config.Env'
```

### Force Rebuild

```bash
# Full rebuild (removes images, rebuilds from scratch)
docker compose down --rmi local
docker compose up -d --build

# Rebuild specific service
docker compose down
docker compose up -d --build market-data-service
```

### Check Database Connectivity

```bash
# From inside a container
docker compose exec market-data-service python3 -c "
import asyncio
from app.database import DatabaseManager
async def test():
    db = DatabaseManager('$DATABASE_URL')
    await db.connect()
    print('✅ Connected')
asyncio.run(test())
"
```

### Test JWT Configuration

```bash
# Generate a valid test token
python3 -c "
import base64, hashlib, hmac, json, time

secret = 'your-jwt-secret'
header = base64.urlsafe_b64encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()).rstrip(b'=').decode()
payload = base64.urlsafe_b64encode(json.dumps({'sub': 'test', 'exp': int(time.time()) + 3600}).encode()).rstrip(b'=').decode()
sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), f'{header}.{payload}'.encode(), hashlib.sha256).digest()).rstrip(b'=').decode()
print(f'{header}.{payload}.{sig}')
"

# Test with an endpoint
TOKEN=$(python3 test-token-gen.py)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/health
```

---

## Investigation Workflow

### Step 1: Check Container Status

```bash
docker compose ps
```

Look for:
- Container running? (`Up` status)
- Exit code? (non-zero = crash)
- Health check? (`healthy` vs `unhealthy`)

### Step 2: Examine Recent Logs

```bash
docker compose logs market-data-service --tail 50
```

Common error patterns:
- `ModuleNotFoundError` → missing dependency
- `InvalidRequestError` → asyncpg dialect missing
- `OperationalError` → database connection issue
- `HTTPException 503` → JWT_SECRET not set
- `Connection refused` → service not listening

### Step 3: Check Environment

```bash
docker compose exec market-data-service env | grep -E "DATABASE_URL|JWT_SECRET|REDIS_URL"
```

Verify all required vars are set and non-empty.

### Step 4: Verify Dependencies

```bash
docker compose exec market-data-service python3 -c "import psycopg2, asyncpg, redis; print('✅ All deps OK')"
```

### Step 5: Check Network

```bash
# From container, test database
docker compose exec market-data-service nc -zv postgres 5432

# Test Redis
docker compose exec market-data-service nc -zv redis 6379
```

---

## Document Structure

Each troubleshooting section follows this format:

```
## Error: [Exact error message or symptom]

**Symptom:** What you see in logs or when running commands.

**Root Cause:** Why this happens (technical explanation).

**Immediate Fix:** Steps to resolve the issue right now.

**Prevention:** How to avoid this in the future.

**Debugging:** Extra steps to investigate if fix doesn't work.
```

---

## When to Escalate

Contact the platform engineering team if:
- Issue persists after all troubleshooting steps
- Multiple services affected (cascade failure)
- Database appears corrupted
- Unusual memory/CPU usage
- Network latency > 500ms to services

Provide:
1. `docker compose ps` output
2. Full logs from affected service (last 100 lines)
3. Steps to reproduce
4. Environment variables (sanitized)

---

## Related Documentation

- [Deployment Guide](../deployment/deployment-guide.md) — Initial setup
- [Architecture Reference](../agents/agent-03/architecture/reference-architecture.md) — System design
- [Agent Documentation](../agents/) — Service-specific guides
- [API Documentation](../api/README.md) — Endpoint reference

---

## Version Compatibility

| Service | Python | FastAPI | Uvicorn | Database |
|---------|--------|---------|---------|----------|
| Agent 01 (Market Data) | 3.11 | 0.115.0 | 0.32.0 | PostgreSQL 13+ |
| Agent 02 (Newsletter) | 3.12 | 0.115.0 | 0.32.0 | PostgreSQL 13+ |
| Agent 03 (Scoring) | 3.13 | 0.115.0 | 0.32.0 | PostgreSQL 13+ |
| Agent 04 (Classification) | 3.13 | 0.115.0 | 0.32.0 | PostgreSQL 13+ |
| Agent 05 (Tax Optimization) | 3.13 | 0.115.0 | 0.32.0 | PostgreSQL 13+ |
| Agent 06 (Scenario) | 3.13 | 0.115.0 | 0.32.0 | PostgreSQL 13+ |

---

## Troubleshooting Flow Chart

```
Service container not running?
├─ Yes → [Service Startup Failures](./service-startup.md)
└─ No → Container running but unhealthy?
    ├─ Yes → Health check failing?
    │   ├─ Database check failing? → [Database](./database.md)
    │   ├─ Cache check failing? → Check Redis connectivity
    │   └─ Other → [Docker Deployment](./docker-deployment.md)
    └─ No → Endpoint returning errors?
        ├─ 401/403 → [Authentication](./authentication.md)
        ├─ 5xx → Check application logs
        └─ 2xx but wrong data → Check application logic
```

---

**Quick Help:** `docker compose logs -f` is your friend. Start there.
