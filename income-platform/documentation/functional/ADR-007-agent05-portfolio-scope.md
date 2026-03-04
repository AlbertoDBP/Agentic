# ADR-007: Agent 05 Portfolio Data Scope Deferral

**Status:** Accepted
**Date:** 2026-03-04
**Component:** Agent 05 — Tax Optimization Service
**Monorepo Path:** `/Agentic/income-platform/src/tax-optimization-service/`
**Decided In:** Claude Chat — Agent 05 Brainstorm + Design Session
**Next ADR:** ADR-008 (Celery Queue Specialization — already exists)

---

## Context

Agent 05 requires portfolio-level data (holdings, account types, cost basis, current
prices) to perform account placement optimization and tax harvesting analysis. No
portfolio persistence layer exists in the platform yet.

Designing a portfolio DB schema as a side effect of Agent 05 would prematurely
constrain all future agents that touch portfolios: Agent 08 (Rebalancing), Agent 09
(Income Projection), Agent 12 (Proposal). That schema belongs in a dedicated design
session before Agent 08.

Additionally, `current_price` was considered as a live fetch from Agent 01. This was
rejected — price will be caller-supplied in v1.1, sourced from daily batch-updated
portfolio positions when portfolio DB is live.

---

## Decision

Agent 05 accepts portfolio data as a **request payload** in v1.1.

- No portfolio DB reads or writes
- `current_price` supplied by caller — no Agent 01 dependency
- Tax profile resolved from: payload → `user_preferences` table → platform defaults
- Only DB access: read-only query to `user_preferences` by `user_id`

---

## Rationale

- Unblocks Agent 05 without waiting for portfolio persistence layer
- Tax optimization logic is stateless — it calculates, does not store
- Consistent with Agent 03 payload-based scoring pattern
- Portfolio DB schema belongs in a dedicated design session pre-Agent 08
- `current_price` from daily batch positions is more reliable than real-time Agent 01 fetch

---

## Consequences

| Impact | Description |
|---|---|
| ✅ Positive | Agent 05 ships in v1.1 as planned |
| ✅ Positive | No new DB tables required |
| ✅ Positive | Fully testable with mock payloads |
| ✅ Positive | No Agent 01 dependency — simpler docker-compose |
| ⚠️ Limitation | Callers must supply full portfolio context on every request |
| ⚠️ Limitation | No cross-session portfolio memory in v1.1 |

---

## Amendment — Portfolio DB + Valkey Caching (Future)

When portfolio DB schema is designed (pre-Agent 08 design session):

1. Add optional `portfolio_id` parameter to `POST /analyze`
2. If provided: fetch holdings from portfolio DB (holdings + daily-updated prices)
3. Cache result in Valkey keyed by `portfolio_id:user_id` (TTL: 1 hour)
4. Payload-based input remains supported as fallback for stateless callers + testing
5. `current_price` sourced from daily batch-updated portfolio positions

---

## Revisit Trigger

Portfolio DB schema design session — planned before Agent 08 (Rebalancing) DESIGN phase.
