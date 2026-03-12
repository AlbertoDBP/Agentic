# Database Connection Errors

Troubleshooting PostgreSQL and asyncpg issues.

---

## Error: Connection string must be a string or URL instance

**Symptom:**
```
TypeError: Connection string must be a string or URL instance
```

**Root Cause:** DATABASE_URL is None or empty string. Not set in environment or `.env`.

**Immediate Fix:**

1. Check if DATABASE_URL is set:
```bash
docker compose exec market-data-service python3 -c "import os; print(os.environ.get('DATABASE_URL'))"
```

2. If None, add to `.env`:
```bash
DATABASE_URL=postgresql+asyncpg://username:password@postgres:5432/income_platform
```

3. If using docker-compose.yml directly:
```yaml
environment:
  - DATABASE_URL=postgresql+asyncpg://username:password@postgres:5432/income_platform
```

4. Restart:
```bash
docker compose up -d market-data-service
```

**Prevention:**
- `.env` file must exist with all required vars
- Use docker-compose interpolation: `${DATABASE_URL}` references `.env`
- Fail fast: config.py should raise ValidationError if DATABASE_URL missing

---

## Error: could not translate host name to address / Name does not resolve

**Symptom:**
```
asyncpg.InvalidArgumentError: could not translate host name "postgres" to address
```

Or:
```
Name does not resolve
```

**Root Cause:** DATABASE_URL hostname is wrong or DNS can't resolve it. In docker-compose, hostname must be the service name.

**Immediate Fix:**

1. Check the DATABASE_URL:
```bash
docker compose config | grep DATABASE_URL
```

2. Ensure hostname matches service name in docker-compose.yml:
```yaml
services:
  postgres:
    container_name: postgres
    # ...

environment:
  # CORRECT: uses service name
  - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db

  # WRONG: uses localhost
  # - DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
```

3. Verify DNS resolution inside the container:
```bash
docker compose exec market-data-service nslookup postgres
```

Should resolve to postgres container IP (e.g., 172.18.0.2)

**Prevention:**
- Always use service name from docker-compose.yml, not localhost/IP
- Test connectivity before deployment: `nslookup <hostname>`
- Use explicit networks if needed:

```yaml
services:
  postgres:
    networks:
      - app-network
  market-data-service:
    networks:
      - app-network

networks:
  app-network:
```

---

## Error: ssl.SSLError: CERTIFICATE_VERIFY_FAILED

**Symptom:**
```
ssl.SSLError: CERTIFICATE_VERIFY_FAILED, certificate verify failed
```

**Root Cause:** Database requires SSL but certificate validation is failing. Usually when connecting to managed PostgreSQL (e.g., DigitalOcean, AWS RDS).

**Immediate Fix:**

Option 1: Disable SSL verification (dev only):
```bash
# In .env or docker-compose
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=false
```

Option 2: Provide CA certificate (production):
```bash
# Download the CA certificate
curl https://example.com/ca.crt -o ca.crt

# Add to DATABASE_URL
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=true&sslrootcert=/app/ca.crt
```

Then mount the certificate in docker-compose:
```yaml
services:
  market-data-service:
    volumes:
      - ./ca.crt:/app/ca.crt:ro
```

Option 3: Use sslmode parameter:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=require
```

**Prevention:**
- For production RDS/managed databases, always enable SSL
- Verify CA certificate is valid: `openssl x509 -in ca.crt -text -noout`
- Test connection locally before deploying to container

---

## Error: server closed the connection unexpectedly

**Symptom:**
```
asyncpg.PostgresError: server closed the connection unexpectedly
```

**Root Cause:** Database connection was reset. Usually due to:
- Database restarting
- Idle connection timeout
- Network interrupted
- Connection pooling misconfiguration

**Immediate Fix:**

Add connection pool recovery settings in database config:
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    database_url,
    pool_pre_ping=True,        # Verify connection before use
    pool_recycle=3600,         # Recycle connections every hour
    pool_size=5,               # Connection pool size
    max_overflow=10,           # Additional connections when needed
)
```

This is already done in `src/market-data-service/database.py`.

If still failing:
```bash
# Restart database service
docker compose restart postgres

# Wait for it to be healthy
sleep 5

# Restart app service
docker compose restart market-data-service
```

**Prevention:**
- Set `pool_pre_ping=True` (already configured)
- Set `pool_recycle=3600` to refresh old connections
- Monitor database availability with health checks
- Use connection retry logic in application

---

## Error: column "schema_name" does not exist

**Symptom:**
```
ProgrammingError: (psycopg2.ProgrammingError) column "schema_name" does not exist
```

**Root Cause:** Querying PostgreSQL system tables with wrong syntax or permissions issue.

**Immediate Fix:**

1. Check the query in database.py:
```bash
grep -n "schema_name" src/market-data-service/database.py
```

2. Verify PostgreSQL version supports the query:
```bash
docker compose exec postgres psql -U user -d db -c "SELECT schema_name FROM information_schema.schemata LIMIT 1;"
```

3. Check user permissions:
```bash
docker compose exec postgres psql -U postgres -d db -c "GRANT USAGE ON SCHEMA public TO username;"
```

4. Restart connection:
```bash
docker compose restart market-data-service
```

**Prevention:**
- Ensure PostgreSQL user has SELECT on `information_schema`
- Test queries locally before deployment
- Use `information_schema.tables` instead of direct system table queries

---

## Error: FATAL: password authentication failed for user

**Symptom:**
```
FATAL: password authentication failed for user "username"
```

**Root Cause:** Wrong database credentials in DATABASE_URL.

**Immediate Fix:**

1. Verify credentials in DATABASE_URL:
```bash
# Extract from docker-compose
docker compose config | grep DATABASE_URL | head -1
```

2. Test with psql:
```bash
# Format: postgresql://username:password@host:port/database
docker compose exec postgres psql -U username -d database -c "SELECT 1;"
```

3. If wrong, update `.env`:
```bash
DATABASE_URL=postgresql+asyncpg://correct_user:correct_pass@postgres:5432/income_platform
```

4. Restart:
```bash
docker compose down
docker compose up -d
```

**Prevention:**
- Store credentials in `.env` (not in code)
- Use secrets manager in production (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate credentials regularly
- Verify credentials in CI/CD before deploying

---

## Error: psycopg2.OperationalError: could not translate host name

**Symptom:**
```
psycopg2.OperationalError: could not translate host name "localhost" to address
```

**Root Cause:** DATABASE_URL uses `localhost` inside Docker. Inside containers, localhost refers to the container itself, not the host machine.

**Immediate Fix:**

Change DATABASE_URL to use service name:
```bash
# WRONG
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db

# CORRECT
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db
#                                              ^^^^^^^^ service name
```

Update in `.env` or docker-compose.yml:
```bash
sed -i 's|@localhost:|@postgres:|g' .env
docker compose up -d
```

**Prevention:**
- Always use Docker service names, never localhost
- Use docker-compose networks properly
- Test with `docker compose exec <service> nslookup postgres`

---

## Error: [pool_0] size overflow, discarding object

**Symptom:**
```
WARNING [pool_0] size overflow, discarding object
```

Appears in logs when under heavy load.

**Root Cause:** Connection pool exhausted. More connections requested than `pool_size + max_overflow`.

**Immediate Fix:**

Increase pool settings in database.py:
```python
pool_size=10,        # Was 5
max_overflow=20,     # Was 10
```

Then rebuild:
```bash
docker compose up -d market-data-service
```

**Prevention:**
- Monitor pool usage: `docker compose logs market-data-service | grep "pool"`
- Calculate needed connections:
  - Concurrent requests × 2 (some queries hold locks)
  - Typical: 10-20 for small services, 50+ for high-traffic
- Use connection pooling proxy (pgbouncer) for large deployments
- Profile slow queries to reduce hold time

---

## Error: schema "platform_shared" does not exist

**Symptom:**
```
ProgrammingError: (psycopg2.ProgrammingError) schema "platform_shared" does not exist
```

**Root Cause:** Custom schema not created in database. Platform uses `platform_shared` schema for shared tables.

**Immediate Fix:**

1. Create the schema manually:
```bash
docker compose exec postgres psql -U user -d income_platform -c "CREATE SCHEMA platform_shared;"
```

2. Grant permissions:
```bash
docker compose exec postgres psql -U user -d income_platform -c "GRANT ALL ON SCHEMA platform_shared TO user;"
```

3. Restart services:
```bash
docker compose restart
```

**Prevention:**
- Run schema creation in Alembic migration or init script
- Add to docker-compose postgres service initialization:

```yaml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-c search_path=public,platform_shared"
  volumes:
    - ./init-schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
```

Where `init-schema.sql` contains:
```sql
CREATE SCHEMA IF NOT EXISTS platform_shared;
GRANT ALL ON SCHEMA platform_shared TO app_user;
```

---

## Error: relation "market_data_daily" does not exist

**Symptom:**
```
ProgrammingError: (psycopg2.ProgrammingError) relation "market_data_daily" does not exist
```

**Root Cause:** ORM tables not created. SQLAlchemy models exist but tables haven't been created in the database.

**Immediate Fix:**

1. Create tables from ORM models:
```bash
docker compose exec market-data-service python3 -c "
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
print('✅ Tables created')
"
```

Or for async:
```bash
docker compose exec market-data-service python3 << 'EOF'
import asyncio
from sqlalchemy import text
from app.database import engine

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(lambda conn: print('Tables created'))

asyncio.run(create_tables())
EOF
```

2. Verify tables exist:
```bash
docker compose exec postgres psql -U user -d income_platform -c "\dt public.*"
```

**Prevention:**
- Run table creation on startup (already done in lifespan)
- Use Alembic migrations for schema management
- Version control all schema changes

---

## Error: Timeout expired

**Symptom:**
```
asyncio.TimeoutError: Timeout expired
```

Or:
```
socket.timeout: timed out
```

**Root Cause:** Database query or connection took longer than timeout. Usually slow queries or connection issues.

**Immediate Fix:**

1. Increase connection timeout:
```python
connect_args = {"timeout": 30}  # Was 10
```

2. Check slow queries:
```bash
docker compose exec postgres psql -U postgres -d income_platform << 'EOF'
SELECT query, calls, mean_time FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
EOF
```

3. If specific query is slow, add index:
```bash
docker compose exec postgres psql -U user -d income_platform -c "CREATE INDEX idx_symbol_date ON market_data_daily(symbol, date);"
```

**Prevention:**
- Set statement_timeout in PostgreSQL config:
```yaml
postgres:
  environment:
    - POSTGRES_INIT_ARGS=-c statement_timeout=30000  # 30s
```

- Monitor query performance in dev
- Add indexes before production queries get slow

---

## Debugging Checklist

- [ ] DATABASE_URL set and formatted correctly? (`postgresql+asyncpg://user:pass@host:5432/db`)
- [ ] Postgres container running? `docker compose ps postgres`
- [ ] Postgres accepting connections? `docker compose exec postgres psql -U user -c "SELECT 1;"`
- [ ] Network connectivity? `docker compose exec market-data-service nc -zv postgres 5432`
- [ ] Schema exists? `docker compose exec postgres psql -c "\dn"`
- [ ] Tables exist? `docker compose exec postgres psql -c "\dt public.*"`
- [ ] Credentials correct? Try manual psql connection
- [ ] Connection pool not exhausted? Check logs for "size overflow"
- [ ] Queries completing in time? `EXPLAIN ANALYZE` on slow queries

---

## See Also

- [Service Startup Failures](./service-startup.md) — Database connection refused during startup
- [Authentication Errors](./authentication.md) — JWT and auth module issues
- [Docker Deployment](./docker-deployment.md) — Image/container issues
