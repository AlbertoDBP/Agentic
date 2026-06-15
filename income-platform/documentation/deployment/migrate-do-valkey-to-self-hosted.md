# Migrate Cache: DO Managed Valkey → Self-hosted Valkey on legato

**Goal:** Drop the DO managed Valkey line item by running a Valkey container on `legato`
(138.197.78.238), alongside the services that already run there.

**Why this is trivial (verified against the repo):**

- Valkey is used as an **ephemeral cache only** — `consensus:{ticker}` (TTL 30m), `signal:{ticker}`
  (TTL 1h), market-price keys (TTL 5m). Every value is **recomputable from Postgres**.
- Services **degrade gracefully** without it (`src/agent-02-newsletter-ingestion/app/api/health.py`
  reports `degraded`, not failed) and **nothing `depends_on` it**.
- Code uses only generic commands (`GET`/`SETEX`/`DEL`/`PING`) via `redis==5.2.0`, plain `redis://`
  — **no TLS assumed in code**, no pub/sub, no queues/streams, no locks, no Prefect broker.

> **There is NO data to migrate.** Cache loss on cutover = a few minutes of cold cache that
> repopulates on the next queries. No dump, no restore, no maintenance window required.

---

## 0. Facts this runbook is built on

| Thing | Current value |
|---|---|
| Client | `redis==5.2.0` (sync in agent-02, `redis.asyncio` in market-data-service) |
| Wiring | `REDIS_URL=${REDIS_URL}` injected into each service from `.env` |
| DO upstream | `rediss://default:…@private-db-valkey-nyc3-79344-do-user-32765812-0.j.db.ondigitalocean.com:25061` (TLS) |
| Consumers | market-data-service (8001), agent-02 (8002); config-only in income-scoring / asset-classification |
| Persistence needed | **None** — pure cache, all keys TTL'd and recomputable |
| Valkey-specific features | none — any Redis 5+/Valkey 7+ is a drop-in |
| Existing local ref | `valkey/valkey:7.2-alpine` in `src/agent-02-newsletter-ingestion/docker-compose.yml` |

---

## 1. Add the Valkey container to `docker-compose.yml`

Add this service (anywhere in `services:`; no ordering constraint since nothing depends on it):

```yaml
  # ───────────────────────────────────────────────────────────────────────────
  # Self-hosted Valkey (replaces DO managed Valkey). Pure cache — no persistence.
  # No host port exposed; only platform services reach it on the docker network.
  # ───────────────────────────────────────────────────────────────────────────
  valkey:
    image: valkey/valkey:8-alpine
    container_name: valkey
    command:
      - "valkey-server"
      - "--maxmemory"
      - "256mb"
      - "--maxmemory-policy"
      - "allkeys-lru"
      - "--save"
      - ""                       # disable RDB snapshots — it's a cache, not a datastore
      - "--appendonly"
      - "no"                     # disable AOF — nothing here needs to survive a restart
    restart: unless-stopped
    mem_limit: 320m              # 256m maxmemory + overhead
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 5s
```

> `--maxmemory 256mb` + `allkeys-lru` matches current usage (consensus/signal for ~1000 tickers at
> 1–5KB each). Eviction is safe — evicted keys just get recomputed on next request.

**Optional** — make services wait for it (not required; they degrade gracefully). If you want it,
add to market-data-service and agent-02:

```yaml
    depends_on:
      valkey:
        condition: service_healthy
```

---

## 2. `.env` change

```bash
# OLD (DO managed Valkey, TLS):
# REDIS_URL=rediss://default:<DO_VALKEY_PASS>@private-db-valkey-nyc3-79344-do-user-32765812-0.j.db.ondigitalocean.com:25061

# NEW (self-hosted container, internal docker network, no TLS):
REDIS_URL=redis://valkey:6379/0
```

> Single DB `/0` is fine — cache keys are namespaced by prefix (`consensus:`, `signal:`, price keys),
> so no collisions. (If you prefer isolation you *can* give services `/0`, `/1`, `/2`, but it's
> unnecessary here.) No password: the container isn't exposed outside the docker network. If you ever
> publish the port, add `--requirepass` and put the password back in the URL.

---

## 3. Cutover (no maintenance window needed)

On legato:

```bash
cd /opt/Agentic/income-platform
git pull origin main              # if you commit the compose change; else edit in place
# ...apply the .env change above...
docker compose up -d valkey       # start the cache
docker compose up -d --force-recreate market-data-service agent-02-newsletter-ingestion
```

(`--force-recreate` so the services pick up the new `REDIS_URL`. You can recreate all services if
you prefer, but only these two use the cache.)

---

## 4. Verify

```bash
# Container healthy + responding
docker compose exec valkey valkey-cli ping            # -> PONG

# Services report cache healthy again
curl -fsS http://localhost:8002/health | grep -i cache    # agent-02 cache: healthy
curl -fsS http://localhost:8001/health                     # market-data-service

# Watch keys populate as traffic flows
docker compose exec valkey valkey-cli --scan --pattern 'consensus:*'
docker compose exec valkey valkey-cli --scan --pattern 'signal:*'
docker compose exec valkey valkey-cli info keyspace
```

---

## 5. Rollback (instant)

Nothing was migrated, so rollback is just repointing:

```bash
# Restore REDIS_URL to the DO rediss:// value in .env, then:
docker compose up -d --force-recreate market-data-service agent-02-newsletter-ingestion
```

The DO Valkey is untouched throughout. Keep it for a day or two after cutover, then destroy it.

---

## 6. After this

With Postgres (see `migrate-do-postgres-to-self-hosted.md`) **and** Valkey both self-hosted, the only
remaining DO dependency is the **droplet itself** (your compute) — which you keep until the broader
"leave DO" move. At that point both data services come along as plain containers in the same compose
file, portable to any host.
