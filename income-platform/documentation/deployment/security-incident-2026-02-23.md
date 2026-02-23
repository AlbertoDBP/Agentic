# Security Incident Report — Redis Public Exposure
**Date:** 2026-02-23
**Severity:** High
**Status:** Resolved ✅

---

## Incident Summary

DigitalOcean issued a security alert indicating that port 6379 (Redis) was publicly accessible on the production droplet (138.197.78.238). An orphaned `redis:7-alpine` Docker container was running with port mapping `0.0.0.0:6379:6379`, bypassing UFW firewall rules via Docker's direct iptables modification.

---

## Root Cause

During early development, a local Redis container was added to `docker-compose.yml` for development purposes. The container definition was subsequently removed from the compose file when the platform migrated to DigitalOcean managed Valkey, but the **running container was never stopped**. It continued running as an orphaned container with no compose definition, publicly accessible.

---

## Timeline

| Time | Event |
|------|-------|
| ~4 days prior | Orphaned Redis container first started |
| 2026-02-23 | DigitalOcean security alert received |
| 2026-02-23 | Investigation: confirmed orphaned container, not used by any service |
| 2026-02-23 | `docker stop income-fortress-redis && docker rm income-fortress-redis` |
| 2026-02-23 | Service health confirmed: all endpoints still healthy |
| 2026-02-23 | Port 6379 confirmed no longer listening (`ss -tlnp | grep 6379` returns empty) |
| 2026-02-23 | DigitalOcean Cloud Firewall confirmed: all ports blocked except 22, 80, 443 |

---

## Resolution

1. Stopped and removed orphaned `income-fortress-redis` container
2. Confirmed `income-fortress-postgres` (also orphaned, crash-looping) removed simultaneously
3. Verified all services use managed DigitalOcean infrastructure via environment variables
4. DigitalOcean Cloud Firewall provides defense-in-depth — port 6379 blocked at network level

---

## Impact Assessment

- **Data exposure:** Cached stock price data was potentially readable. No credentials, PII, or financial account data stored in Redis.
- **Service impact:** None — services were already using managed Valkey via `${REDIS_URL}`
- **Confirmed no breach:** DigitalOcean noted no known abuse

---

## Prevention

- Never leave development containers running in production
- After removing services from `docker-compose.yml`, always run `docker compose down` to stop orphaned containers
- DigitalOcean Cloud Firewall as defense-in-depth for all non-web ports
- Add to deployment checklist: `docker ps` review before declaring deployment complete

---
