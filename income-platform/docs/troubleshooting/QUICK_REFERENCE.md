# Quick Reference - Common Commands

Fast lookup for the most common troubleshooting commands.

---

## Service Status & Logs

```bash
# See all services
docker compose ps

# Check specific service status
docker compose ps market-data-service

# Follow logs (real-time)
docker compose logs -f

# Last 50 lines of specific service
docker compose logs market-data-service --tail 50

# Search logs for error
docker compose logs market-data-service | grep -i error

# Logs from last 5 minutes
docker compose logs --since 5m market-data-service
```

---

## Environment & Configuration

```bash
# View interpolated docker-compose (with .env values)
docker compose config

# Check specific env var in container
docker compose exec market-data-service env | grep DATABASE_URL

# Check all env vars in container
docker compose exec market-data-service env

# Print env var to console
docker compose exec market-data-service python3 -c "import os; print(os.environ.get('JWT_SECRET'))"
```

---

## Rebuilding & Restarting

```bash
# Rebuild specific service (no cache)
docker compose build --no-cache market-data-service

# Full rebuild, remove images, restart all
docker compose down --rmi local && docker compose up -d --build

# Restart single service
docker compose restart market-data-service

# Stop and start (cleaner than restart)
docker compose down && docker compose up -d

# Rebuild and restart in one command
docker compose up -d --build market-data-service
```

---

## Health Checks

```bash
# Check /health endpoint
curl -s http://localhost:8001/health | jq .

# For protected endpoints, need token:
TOKEN='...'
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/stocks/AAPL/price

# Check with Python
docker compose exec market-data-service python3 -c "
import urllib.request
try:
    response = urllib.request.urlopen('http://localhost:8001/health')
    print('✅ Healthy')
except Exception as e:
    print(f'❌ {e}')
"
```

---

## Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U user -d income_platform

# Run query
docker compose exec postgres psql -U user -d income_platform -c "SELECT 1;"

# Check tables
docker compose exec postgres psql -U user -d income_platform -c "\dt"

# Check schema
docker compose exec postgres psql -U user -d income_platform -c "\dn"

# Test connection from service
docker compose exec market-data-service python3 -c "
import asyncio
from app.database import DatabaseManager

async def test():
    db = DatabaseManager('${DATABASE_URL}')
    await db.connect()
    print('✅ Connected')

asyncio.run(test())
"
```

---

## Network & Connectivity

```bash
# Test port is open
docker compose exec market-data-service nc -zv postgres 5432
docker compose exec market-data-service nc -zv redis 6379

# Test DNS resolution
docker compose exec market-data-service nslookup postgres

# Ping service
docker compose exec market-data-service ping postgres

# Check if port is in use (on host)
lsof -i :8001

# Check all listening ports
netstat -tulpn | grep LISTEN
```

---

## Container Introspection

```bash
# Get container ID
docker compose ps --format "table {{.Names}}\t{{.ID}}"

# Inspect container details
docker inspect <container-id>

# Check resource usage
docker stats

# Execute command in container
docker compose exec market-data-service bash

# Copy file from container
docker compose cp market-data-service:/app/file.txt ./file.txt

# View container filesystem
docker compose exec market-data-service ls -la /app
```

---

## Cleanup

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune -f

# Remove all build cache
docker builder prune -a

# Full cleanup (everything)
docker system prune -a --volumes

# Free up disk space (see usage)
docker system df
```

---

## Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/unit/test_auth.py

# Run specific test function
python -m pytest tests/unit/test_auth.py::test_verify_token

# Run with verbose output
python -m pytest -vv

# Run and show print statements
python -m pytest -s

# Run failed tests only
python -m pytest --lf

# Run with timeout (requires pytest-timeout)
python -m pytest --timeout=10

# Drop to debugger on failure
python -m pytest --pdb

# Show available fixtures
python -m pytest --fixtures
```

---

## Git Operations (On Server)

```bash
# Check git status
git status

# See what would be pulled
git diff origin/main

# Remove untracked files blocking pull
git clean -f path/to/file
git clean -f -d  # Remove directories too

# Stash local changes
git stash

# Pull latest code
git pull origin main

# Check recent commits
git log --oneline -10

# Revert to specific commit
git checkout <commit-hash>
```

---

## Generate Test JWT Token

```bash
python3 << 'EOF'
import base64, hashlib, hmac, json, time

secret = 'your-jwt-secret'
header = base64.urlsafe_b64encode(
    json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()
).rstrip(b'=').decode()

payload = base64.urlsafe_b64encode(
    json.dumps({'sub': 'test', 'exp': int(time.time()) + 3600}).encode()
).rstrip(b'=').decode()

sig = base64.urlsafe_b64encode(
    hmac.new(secret.encode(), f'{header}.{payload}'.encode(), hashlib.sha256).digest()
).rstrip(b'=').decode()

print(f'{header}.{payload}.{sig}')
EOF
```

---

## One-Liners for Common Issues

```bash
# Restart everything
docker compose down && docker compose up -d

# Full rebuild and restart
docker compose down --rmi local && docker compose up -d --build

# Check if service is healthy
docker compose ps | grep "unhealthy" && echo "UNHEALTHY" || echo "OK"

# Tail all logs (follow)
docker compose logs -f

# Find what's using a port
lsof -i :8001 || netstat -tulpn | grep 8001

# Create PostgreSQL schema
docker compose exec postgres psql -U user -d income_platform -c "CREATE SCHEMA IF NOT EXISTS platform_shared;"

# Reset database (dangerous - recreates all tables)
docker compose down && docker compose up -d postgres && sleep 5 && docker compose up -d

# Check all services are healthy
docker compose ps | grep -c "Up" && echo "All running"

# View JWT_SECRET is set
docker compose exec market-data-service python3 -c "import os; print('SET' if os.environ.get('JWT_SECRET') else 'NOT SET')"
```

---

## Port Reference

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| Market Data (Agent 01) | 8001 | http://localhost:8001/health |
| Newsletter (Agent 02) | 8002 | http://localhost:8002/health |
| Income Scoring (Agent 03) | 8003 | http://localhost:8003/health |
| Asset Classification (Agent 04) | 8004 | http://localhost:8004/health |
| Tax Optimization (Agent 05) | 8005 | http://localhost:8005/health |
| Scenario Simulation (Agent 06) | 8006 | http://localhost:8006/health |
| PostgreSQL | 5432 | N/A |
| Redis | 6379 | N/A |

---

## Environment Variables Checklist

Required in `.env`:
- [ ] `DATABASE_URL` - PostgreSQL connection string (must have `+asyncpg`)
- [ ] `REDIS_URL` - Redis/Valkey connection string
- [ ] `JWT_SECRET` - 32+ character secret for token signing
- [ ] `MARKET_DATA_API_KEY` - Alpha Vantage API key
- [ ] `POLYGON_API_KEY` - Polygon.io API key
- [ ] `FMP_API_KEY` - Financial Modeling Prep API key
- [ ] `FINNHUB_API_KEY` - Finnhub API key (for credit ratings)

Optional:
- `LOG_LEVEL` - DEBUG, INFO (default), WARNING, ERROR
- `ANTHROPIC_API_KEY` - For agents using Claude
- `OPENAI_API_KEY` - For agents using GPT models
- `ADMIN_USERNAME` - For admin endpoints
- `ADMIN_PASSWORD` - For admin endpoints

---

## Need More Help?

- **Service won't start?** → [Service Startup Failures](./service-startup.md)
- **Database issues?** → [Database Errors](./database.md)
- **Auth problems?** → [Authentication Errors](./authentication.md)
- **Docker problems?** → [Docker & Deployment](./docker-deployment.md)
- **Test failures?** → [Test Failures](./tests.md)
- **Complete index?** → [README](./README.md)

---

**Last Updated:** March 2026
**Questions?** Check the full troubleshooting guides linked above
