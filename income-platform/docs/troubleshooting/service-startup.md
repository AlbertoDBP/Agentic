# Service Startup Failures

Troubleshooting guide for services that fail to start or exit immediately.

---

## Error: ModuleNotFoundError: No module named 'jwt'

**Symptom:** Container exits with:
```
ModuleNotFoundError: No module named 'jwt'
```

**Root Cause:** PyJWT not installed in container. Market Data Service Dockerfile has an explicit `RUN pip install PyJWT==2.8.0` step, but other services may rely on requirements.txt which may be incomplete or cached.

**Immediate Fix:**

```bash
# Full rebuild forces Docker to fetch latest PyPI packages
docker compose down --rmi local
docker compose up -d --build market-data-service
```

If only one service affected:
```bash
docker compose build --no-cache market-data-service
docker compose up -d market-data-service
```

**Prevention:**
- Ensure `PyJWT==2.8.0` is in `requirements.txt` for any service using `auth.py`
- After updating requirements.txt, rebuild: `docker compose build --no-cache <service>`
- Don't rely on pip cache across builds; use `--no-cache-dir` in Dockerfile

**Verification:**
```bash
docker compose exec market-data-service python3 -c "import jwt; print('✅ jwt available')"
```

---

## Error: ModuleNotFoundError: No module named 'psycopg2'

**Symptom:** Container exits with:
```
ModuleNotFoundError: No module named 'psycopg2'
```

**Root Cause:** psycopg2-binary not installed. Required by SQLAlchemy for PostgreSQL.

**Immediate Fix:**

```bash
# Rebuild with fresh dependencies
docker compose build --no-cache <service>
docker compose up -d <service>
```

Verify `psycopg2-binary==2.9.10` is in `requirements.txt`:
```bash
grep psycopg2 src/market-data-service/requirements.txt
```

**Prevention:**
- Add `psycopg2-binary==2.9.10` to all service requirements.txt files
- Never use plain `psycopg2`; binary build is required in containers

---

## Error: ModuleNotFoundError: No module named 'python_multipart'

**Symptom:** Container starts but `/auth/token` endpoint fails with:
```
FormData could not be parsed as JSON or form data
```

Or startup logs show import error.

**Root Cause:** `python-multipart` package missing. FastAPI's OAuth2PasswordBearer and form endpoints require this for parsing `application/x-www-form-urlencoded` requests.

**Immediate Fix:**

```bash
# Add to requirements.txt
echo "python-multipart==0.0.7" >> src/market-data-service/requirements.txt

# Rebuild
docker compose build --no-cache market-data-service
docker compose up -d market-data-service
```

**Prevention:**
- Include `python-multipart==0.0.7` in all FastAPI service requirements.txt
- Test form endpoints in dev before deployment

---

## Error: InvalidRequestError: loaded 'psycopg2' is not async

**Symptom:** Container exits with:
```
sqlalchemy.exc.InvalidRequestError: loaded 'psycopg2' is not async
```

**Root Cause:** AsyncIO code using `create_async_engine()` but DATABASE_URL has `postgresql://` prefix instead of `postgresql+asyncpg://`. SQLAlchemy defaults to psycopg2 (sync driver) when dialect not specified.

**Immediate Fix:**

1. Check DATABASE_URL in `.env` or docker-compose.yml:
```bash
grep DATABASE_URL docker-compose.yml
```

2. Ensure prefix is `postgresql+asyncpg://`:
```bash
# WRONG
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb

# CORRECT
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
```

3. Update `.env`:
```bash
# Edit .env
sed -i 's|postgresql://|postgresql+asyncpg://|g' .env
```

4. Restart service:
```bash
docker compose up -d market-data-service
```

**Prevention:**
- Code verification: search for `create_async_engine` → must have `postgresql+asyncpg://` prefix
- Add validation in config.py:

```python
def _validate_async_db_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
```

---

## Error: HTTPException 503 on startup / JWT_SECRET not configured

**Symptom:** Service container starts but:
- Health check fails
- Any protected endpoint returns 503: "JWT_SECRET not configured"
- Logs show no explicit error, but auth module returns 503

**Root Cause:** `JWT_SECRET` environment variable not set. Auth verification code checks this and raises 503 immediately.

**Immediate Fix:**

```bash
# Check if JWT_SECRET is set in docker-compose.yml
grep -A 5 "environment:" docker-compose.yml | grep JWT_SECRET

# If missing, add to docker-compose.yml or .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
```

Then restart:
```bash
docker compose down
docker compose up -d
```

**Prevention:**
- `.env` file must include: `JWT_SECRET=<some-secret>`
- In production, set via secrets manager: `docker compose.yml` using `${JWT_SECRET}` interpolation
- CI/CD must inject JWT_SECRET before deployment
- Fail-fast at startup (not at first request): validate in lifespan or config

---

## Error: psycopg2.OperationalError: could not connect to server: Connection refused

**Symptom:** Container starts but immediately fails with:
```
psycopg2.OperationalError: could not connect to server: Connection refused
Is the server running on host "postgres" (172.18.0.2) and accepting TCP connections on port 5432?
```

**Root Cause:** PostgreSQL container not running, not ready, or DATABASE_URL hostname is wrong.

**Immediate Fix:**

1. Check PostgreSQL is running:
```bash
docker compose ps | grep postgres
```

If not running:
```bash
docker compose up -d postgres
# Wait for it to be healthy (check logs)
sleep 10
docker compose up -d
```

2. Verify DATABASE_URL in docker-compose.yml:
```bash
# Should match postgres service name
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/database
#                                          ^^^^^^^^ must be service name
```

3. Check network connectivity:
```bash
docker compose exec market-data-service nc -zv postgres 5432
```

Expected output: `postgres port 5432 open`

**Prevention:**
- In docker-compose.yml, use service name (not localhost or IP)
- Add `depends_on` with `condition: service_healthy`:

```yaml
services:
  market-data-service:
    depends_on:
      postgres:
        condition: service_healthy
```

- Increase `start_period` in healthcheck if postgres is slow to start:

```yaml
healthcheck:
  start_period: 30s  # Wait 30s before first health check
```

---

## Error: Address already in use

**Symptom:** Container exits or fails to bind port:
```
Address already in use
OSError: [Errno 48] Address already in use
```

**Root Cause:** Another process or container already listening on the port (8001, 8002, 8003, etc.).

**Immediate Fix:**

```bash
# Find what's using the port
lsof -i :8001

# Kill the process
kill -9 <PID>

# Or use docker to kill the container
docker kill <container-id>

# Restart
docker compose up -d market-data-service
```

**Prevention:**
- Use `docker compose down` before restarting (not just `Ctrl+C`)
- Check ports aren't in use before deployment:

```bash
netstat -tulpn | grep -E ":(8001|8002|8003|8004|8005|8006)"
```

- In docker-compose.yml, use unique ports per service (already done)

---

## Error: pymupdf.fitz.FileError: cannot open document

**Symptom:** Newsletter ingestion service fails with:
```
pymupdf.fitz.FileError: cannot open document
```

**Root Cause:** PyMuPDF library not installed or version mismatch.

**Immediate Fix:**

```bash
# Check if pymupdf is in requirements.txt
grep -i pymupdf src/agent-02-newsletter-ingestion/requirements.txt

# If missing, add it
echo "PyMuPDF==1.24.1" >> src/agent-02-newsletter-ingestion/requirements.txt

# Rebuild
docker compose build --no-cache agent-02-newsletter-ingestion
docker compose up -d agent-02-newsletter-ingestion
```

---

## Error: libc.so.6: version `GLIBC_X.XX' not found

**Symptom:** Container exits during startup:
```
/lib64/libc.so.6: version `GLIBC_X.XX' not found
```

**Root Cause:** Base image Python version mismatch with compiled wheel packages.

**Immediate Fix:**

```bash
# Check current base image
grep "FROM python" Dockerfile

# Use matched version (e.g., python:3.11-slim for Python 3.11)
# Then rebuild
docker compose build --no-cache market-data-service
docker compose up -d market-data-service
```

**Prevention:**
- Pin Python version in Dockerfile: `FROM python:3.11-slim`
- Don't mix Python 3.11 with 3.13 wheels
- Use `slim` images to avoid bloat, but ensure required system libs are installed:

```dockerfile
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
```

---

## Error: Timeout waiting for service to become healthy

**Symptom:** `docker compose up` hangs after printing:
```
Waiting for market-data-service to be healthy...
```

Service container logs show it's running but health check fails.

**Root Cause:** Health check command failing or taking too long. Check `/health` endpoint.

**Immediate Fix:**

1. Manually check the health endpoint:
```bash
docker compose exec market-data-service curl -s http://localhost:8001/health
```

If connection refused: service not listening yet, increase `start_period`

2. Increase timeout in docker-compose.yml:
```yaml
healthcheck:
  test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 30s  # Increase this
```

3. Check service logs during startup:
```bash
docker compose logs market-data-service -f
```

Look for errors in database connection, cache initialization, etc.

**Prevention:**
- Test health endpoint locally before deployment
- Ensure all dependencies (DB, Redis) are running before main service
- Use `depends_on` with `service_healthy` condition

---

## Error: ImportError: cannot import name 'verify_token' from 'auth'

**Symptom:** During app startup:
```
ImportError: cannot import name 'verify_token' from 'auth'
```

**Root Cause:** In test scenarios, `auth.py` import fails because JWT_SECRET is not set at module import time.

**Immediate Fix:**

In test code, set JWT_SECRET before any app imports:
```python
import os
os.environ['JWT_SECRET'] = 'test-secret'  # SET THIS FIRST

# Now safe to import app
from app import app
```

This is already done correctly in `conftest.py` at the top of the file.

**Prevention:**
- Always set `JWT_SECRET` before importing app modules in tests
- Use fixtures in conftest.py that run at module scope:

```python
# conftest.py
import os
os.environ.setdefault('JWT_SECRET', 'test-secret')

# ... rest of conftest
```

---

## Debugging Checklist

If the service still won't start, work through this:

- [ ] Container exists? `docker compose ps`
- [ ] Container exiting with error code? Check `docker compose logs <service>`
- [ ] All required env vars set? `docker compose exec <service> env`
- [ ] All dependencies importable? `docker compose exec <service> python3 -c "import <module>"`
- [ ] Database reachable? `docker compose exec <service> nc -zv postgres 5432`
- [ ] Redis reachable? `docker compose exec <service> nc -zv redis 6379`
- [ ] Health endpoint works? `docker compose exec <service> curl http://localhost:<port>/health`
- [ ] Logs are captured? `docker compose logs <service> --tail 100`

---

## See Also

- [Docker & Deployment Issues](./docker-deployment.md) — Image caching, rebuild strategies
- [Database Connection Errors](./database.md) — PostgreSQL-specific issues
- [Authentication Errors](./authentication.md) — JWT token problems
