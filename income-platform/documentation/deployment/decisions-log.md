# Architecture Decision Records — Income Fortress Platform

This log captures significant architectural and technical decisions made during development.

---

## ADR-004 — Route Structure Consolidation to /stocks/ Pattern
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 2

### Context
Nginx reverse proxy strips the `/api/market-data/` prefix before forwarding requests to the service container. Legacy routes were defined with the full prefix included, causing 404s in production despite the service running correctly.

### Decision
Consolidate all Market Data Service routes to the `/stocks/{symbol}/` pattern. Nginx handles the public-facing prefix. The service operates on clean internal paths.

### Consequences
- All internal service routes use `/stocks/` prefix
- Cache stats remain at `/api/v1/cache/stats` (no equivalent replacement)
- Nginx config is the single source of truth for public URL structure
- Future agents must follow the same pattern: define internal routes without the public prefix

---

## ADR-005 — Alpha Vantage Free Tier Constraints
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 2

### Context
`TIME_SERIES_DAILY_ADJUSTED` (fetch_daily_adjusted) is a premium Alpha Vantage endpoint. The platform currently uses a free API key. Premium endpoints return 402 errors.

### Decision
Use `TIME_SERIES_DAILY` (get_daily_prices) with `outputsize=compact` (last ~100 days). Implement a 140-day cutoff: date ranges older than 140 days skip the Alpha Vantage call and return whatever is in the database.

### Consequences
- Historical data limited to ~100 days from today on free tier
- `adjusted_close` values are populated with `close` value as approximation
- Full history unavailable until migration to Polygon.io + FMP (planned after Agent 02)
- Income Scorer (Agent 03) must account for limited history window

---

## ADR-006 — Rate Limiter Class Variable Scope
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 2

### Context
`AlphaVantageClient.last_request_time` was an instance variable. Since each service call instantiated a new client, the rate limiter reset on every request and never enforced the 5 requests/minute limit, risking Alpha Vantage API bans.

### Decision
Change `last_request_time` to a class variable `_last_request_time` shared across all instances. Set hard floor of `max(60/calls_per_minute, 1.1)` seconds per request.

### Consequences
- Rate limiting is now enforced correctly across all service calls
- Minimum 1.1 second gap between requests regardless of configured rate
- All future API clients in the platform must use class variables for rate limiting state

---

## ADR-007 — Managed Valkey over Local Redis
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 2 (Security Incident)

### Context
An orphaned `redis:7-alpine` Docker container was running with port 6379 exposed publicly (`0.0.0.0:6379`). Docker bypasses UFW, making it accessible from the internet. DigitalOcean issued a security alert.

### Decision
Remove the orphaned local Redis container entirely. All services use the DigitalOcean managed Valkey instance via `${REDIS_URL}` environment variable. Add `socket_connect_timeout=5, socket_timeout=5` to handle VPC-only connectivity.

### Consequences
- No local Redis/Valkey containers in docker-compose.yml
- Managed Valkey provides HA, backups, and security by default
- VPC-only connectivity requires explicit timeouts to prevent startup hangs
- DigitalOcean Cloud Firewall blocks port 6379 at network level as defense in depth

---

## ADR-001 — Alpha Vantage as Initial Data Provider
**Date:** 2026-02-19
**Status:** Superseded (migration planned after Agent 02)

Alpha Vantage selected for initial development due to free tier availability. Migration to Polygon.io + Financial Modeling Prep planned to unlock dividend data, fundamentals, and ETF holdings required by Agent 03 Income Scorer.

---

## ADR-002 — Microservices Architecture with FastAPI
**Date:** 2026-02-19
**Status:** Accepted

Each agent implemented as an independent FastAPI microservice. Services communicate via REST APIs. Shared infrastructure: managed PostgreSQL, managed Valkey, Nginx reverse proxy.

---

## ADR-003 — Proposal-Based Workflow (No Auto-Execution)
**Date:** 2026-02-19
**Status:** Accepted

All platform agents operate in proposal mode. Capital safety threshold of 70% with VETO power. No agent auto-executes trades or portfolio changes. User approval required for all actions.

---
