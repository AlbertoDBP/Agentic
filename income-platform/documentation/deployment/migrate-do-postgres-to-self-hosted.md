# Migrate DB: DO Managed Postgres → Self-hosted Postgres + pgvector on legato

**Goal:** Leave DigitalOcean managed Postgres without changing a single line of application
code. We keep Postgres (so `pgvector`, `JSONB`, `ARRAY`, `DISTINCT ON`, upserts, etc. all keep
working) and just move *where it runs* — into a `pgvector/pgvector` container on `legato`
(138.197.78.238), alongside the services that already run there.

**Net effect:** the DO managed-Postgres line item → $0 extra compute (already paying for the droplet)
\+ a small nightly-backup discipline you now own.

> **This is a dump-and-restore, not a rewrite.** No SQL changes, no Alembic edits, no new vector DB.

---

## 0. Facts this runbook is built on (verified against the repo)

| Thing | Current value |
|---|---|
| Main compose | `/opt/Agentic/income-platform/docker-compose.yml` (23 services) |
| Pooler | `edoburu/pgbouncer:1.22.0-p0`, transaction mode, `SERVER_TLS_SSLMODE=require` |
| Pooler status | **Deployed but unused** — `PGBOUNCER_URL` unset, services use `DATABASE_URL` (direct to DO) |
| Service DB wiring | `DATABASE_URL=${PGBOUNCER_URL:-${DATABASE_URL}}` (every service) |
| DO upstream | `income-platform-db-do-user-32765812-0.j.db.ondigitalocean.com:25060` |
| DB / user / schema | db `income_platform`, user `dbpmanager`, primary schema `platform_shared` (~97 objects) |
| Extensions required | `vector` (pgvector), `uuid-ossp`, `pg_trgm` |
| Source PG version | 15.x (DO managed) → target **pg16** (restore 15→16 is supported; never the reverse) |
| `.env` | git-ignored ✅ |

> ⚠️ **Rotate the password.** The DO password is currently embedded in `.env`/`DATABASE_URL`.
> The new self-hosted instance gets a **new** superuser password (`<NEWPASS>` below). Do not reuse the DO one.
> Also note Redis/Valkey is still on DO (`rediss://…valkey…`) — out of scope here; track as a separate follow-up to fully leave DO.

---

## 1. Add the Postgres container to `docker-compose.yml`

Insert this service **above** the `pgbouncer:` service (so `depends_on` resolves cleanly), and add the
named volume at the bottom of the file.

```yaml
  # ───────────────────────────────────────────────────────────────────────────
  # Self-hosted PostgreSQL 16 + pgvector  (replaces DO managed Postgres)
  # Only PgBouncer talks to it over the docker network — no host port exposed.
  # ───────────────────────────────────────────────────────────────────────────
  postgres:
    image: pgvector/pgvector:pg16
    container_name: postgres
    environment:
      - POSTGRES_USER=${PG_USER}
      - POSTGRES_PASSWORD=${PG_PASSWORD}
      - POSTGRES_DB=${PG_DATABASE}
      # Raise from the default 100 — 23 services behind PgBouncer transaction pooling
      # still want headroom for admin/migrations/backups.
      - POSTGRES_INITDB_ARGS=--data-checksums
    command:
      - "postgres"
      - "-c"
      - "max_connections=200"
      - "-c"
      - "shared_buffers=512MB"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro
    restart: unless-stopped
    shm_size: 256mb
    mem_limit: 1536m
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER} -d ${PG_DATABASE}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

At the very bottom of the file (create the key if there's no `volumes:` block yet):

```yaml
volumes:
  pgdata:
```

### Repoint PgBouncer upstream → the local container

Change **two** lines in the existing `pgbouncer:` service and add a `depends_on`:

```yaml
  pgbouncer:
    image: edoburu/pgbouncer:1.22.0-p0
    container_name: pgbouncer
    environment:
      - DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT:-5432}/${PG_DATABASE}
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=200
      - DEFAULT_POOL_SIZE=25
      - MIN_POOL_SIZE=2
      - RESERVE_POOL_SIZE=5
      - SERVER_TLS_SSLMODE=disable        # ← was: require  (internal docker net, no TLS needed)
      - LOG_CONNECTIONS=0
      - LOG_DISCONNECTIONS=0
    restart: unless-stopped
    mem_limit: 128m
    depends_on:                            # ← add this block
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -p 5432 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

> The `PG_PORT:-5432` default replaces `:-25060`. With `PG_HOST=postgres` (set in step 2) PgBouncer
> now pools to the local container instead of DO.

---

## 2. Create the extensions init file

`infra/postgres/init/00-extensions.sql` — runs automatically on the container's **first** start (empty
data dir). The dump also recreates these, but pre-creating verifies the image supports pgvector before
you restore:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 3. `.env` changes

**Before the cutover window** — set the variables that drive the *new* container. `DATABASE_URL`
still points at DO at this stage (the app keeps running on DO until step 6):

```bash
# --- New self-hosted Postgres (drives the `postgres` container + pgbouncer upstream) ---
PG_USER=dbpmanager
PG_PASSWORD=<NEWPASS>            # NEW rotated password — becomes the container superuser password
PG_HOST=postgres                # was: income-platform-db-...ondigitalocean.com
PG_PORT=5432                    # was: 25060
PG_DATABASE=income_platform

# DATABASE_URL — leave pointing at DO for now (used only as fallback; flipped in step 6)
```

> `POSTGRES_PASSWORD` is read **only on first init**. Decide `<NEWPASS>` now, before step 4.

**At the cutover (step 6)** you'll add/replace these two:

```bash
# Services finally route through the pooler:
PGBOUNCER_URL=postgresql://dbpmanager:<NEWPASS>@pgbouncer:5432/income_platform?sslmode=disable
# Direct admin URL (used by migrate.py / Alembic / psql):
DATABASE_URL=postgresql://dbpmanager:<NEWPASS>@postgres:5432/income_platform?sslmode=disable
```

---

## 4. Stand up the empty Postgres container (no app downtime)

On legato:

```bash
cd /opt/Agentic/income-platform
git pull origin main            # if you commit the compose/init changes; otherwise edit in place
docker compose up -d postgres   # ONLY postgres — do NOT recreate pgbouncer/services yet
docker compose logs -f postgres # wait for "database system is ready to accept connections"
```

Verify extensions are installable (proves the image has pgvector):

```bash
docker compose exec postgres psql -U dbpmanager -d income_platform -c '\dx'
# Expect: vector, uuid-ossp, pg_trgm
```

The app is still happily running against DO at this point.

---

## 5. Dump from DO → restore into the container (maintenance window)

Pick a low-activity window. Stop writers so the dump is consistent:

```bash
cd /opt/Agentic/income-platform
# Stop everything EXCEPT postgres (which has no data yet) — pgbouncer too:
docker compose stop $(docker compose config --services | grep -vx postgres)
```

**Dump** (run pg_dump from the pg16 image so the dumper version ≥ DO's 15; reach DO over the internet):

```bash
docker run --rm -v "$PWD/backups:/backups" pgvector/pgvector:pg16 \
  pg_dump --no-owner --no-privileges -Fc \
  "postgresql://dbpmanager:<DO_PASSWORD>@income-platform-db-do-user-32765812-0.j.db.ondigitalocean.com:25060/income_platform?sslmode=require" \
  -f /backups/income_platform_predump.dump

ls -lh backups/income_platform_predump.dump   # sanity: non-trivial size
```

**Restore** into the local container:

```bash
docker compose exec -T postgres \
  pg_restore --no-owner --no-privileges --clean --if-exists \
  -U dbpmanager -d income_platform < backups/income_platform_predump.dump
```

> `--clean --if-exists` makes the restore idempotent (safe to re-run). A few "extension already
> exists" / "does not exist, skipping" notices are normal.

---

## 6. Verify the restore (gate before cutover)

```bash
docker compose exec postgres psql -U dbpmanager -d income_platform <<'SQL'
\dx
\dt platform_shared.*
SELECT 'portfolios'   t, count(*) FROM platform_shared.portfolios
UNION ALL SELECT 'analysts',          count(*) FROM platform_shared.analysts
UNION ALL SELECT 'analyst_articles',  count(*) FROM platform_shared.analyst_articles
UNION ALL SELECT 'analyst_recommendations', count(*) FROM platform_shared.analyst_recommendations;
-- pgvector smoke test: dimensions present and queryable
SELECT count(*) FILTER (WHERE content_embedding IS NOT NULL) AS embedded_articles
FROM platform_shared.analyst_articles;
SQL
```

Compare counts against DO (run the same counts against the DO URL). **Only proceed if they match.**

---

## 7. Cutover

Apply the **cutover `.env`** values from step 3 (`PGBOUNCER_URL` + `DATABASE_URL` → local), then
recreate the pooler and bring the app back up:

```bash
cd /opt/Agentic/income-platform
docker compose up -d postgres pgbouncer          # recreate pgbouncer with new upstream
docker compose up -d                              # start all services (now via PGBOUNCER_URL)
docker compose ps                                 # all healthy?
```

Smoke-test the platform: hit a few service `/health` endpoints and one real read (e.g. admin-panel
portfolio view, an Agent-02 semantic search that exercises pgvector).

```bash
for p in 8001 8002 8003 8013 8100; do
  echo -n "port $p: "; curl -fsS "http://localhost:$p/health" && echo " OK" || echo " FAIL"
done
```

---

## 8. Rollback (if anything looks wrong in step 7)

The DO database is untouched (we only **read** from it). To revert:

```bash
# Restore the pre-cutover .env (DATABASE_URL → DO host:25060 ?sslmode=require, unset PGBOUNCER_URL)
git checkout -- .env   # if you snapshotted it, else restore from your backup of .env
docker compose up -d --force-recreate pgbouncer
docker compose up -d
```

Keep the DO database alive for **at least 7 days** after a clean cutover before destroying it.

---

## 9. Nightly backups (you now own this)

DO managed Postgres gave you automated backups for the fee. Replace that with a nightly `pg_dump`
to off-box storage. The script is committed at `infra/postgres/backup.sh`.

Install the cron on legato:

```bash
mkdir -p /opt/backups
chmod +x /opt/Agentic/income-platform/infra/postgres/backup.sh
crontab -e
```

Add:

```cron
# Nightly Postgres backup at 03:15
15 3 * * * /opt/Agentic/income-platform/infra/postgres/backup.sh >> /var/log/pg_backup.log 2>&1
```

The script keeps 14 days locally and (optionally) pushes off-box to DO Spaces / S3 / Backblaze.
**Configure an off-box target** — a backup on the same droplet does not survive a droplet loss.
For point-in-time recovery later, add WAL archiving; nightly dumps are the minimum bar.

Test a restore at least once into a throwaway DB:

```bash
docker run --rm -d --name pgrestore-test -e POSTGRES_PASSWORD=test pgvector/pgvector:pg16
# ...createdb, pg_restore the latest dump, count rows, then: docker rm -f pgrestore-test
```

---

## 10. Cost / tradeoff summary

| | DO managed Postgres | Self-hosted on legato |
|---|---|---|
| Compute cost | recurring managed-DB fee | $0 extra (existing droplet) |
| Backups / PITR | automated, included | **you own it** (§9) — ~$1–5/mo off-box storage |
| HA / failover | managed | none (single container) — acceptable for this workload, revisit if needed |
| pgvector / all SQL | works | **works, unchanged** |
| App code changes | — | **none** |

If you'd rather not own backups/HA at all, the alternative that still keeps pgvector and still
leaves DO is a cheaper managed Postgres (Neon / Supabase) — same dump/restore, just a different
target host in step 5. The self-hosted path above is the lowest-cost way to leave DO.
