# Architecture Decision Records — Agent 03: Income Scoring Service

---

## ADR-001: Two-Phase Pipeline (Gate → Score)

**Date:** 2026-02-26  
**Status:** Accepted

### Context
Income assets can have attractive yields while being fundamentally unsound (yield traps). Scoring all tickers and relying on score to differentiate creates risk of recommending deteriorating assets.

### Decision
Implement a mandatory binary quality gate as Phase 1. A FAIL is an absolute VETO — the ticker never reaches the scoring engine. This enforces capital preservation as the highest priority.

### Consequences
- No yield trap can score its way to a recommendation
- Callers must provide gate data before or alongside score requests
- Gate results are persisted and reused (24hr TTL) to avoid repeated evaluation

---

## ADR-002: Credit Rating via User Input (Not External API)

**Date:** 2026-02-26  
**Status:** Accepted

### Context
FMP `/rating` endpoint returns empty results on the current plan. Agent 01 does not store credit ratings. Building a credit rating scraper introduces new dependencies and maintenance burden.

### Decision
Credit rating is provided by the API caller in the quality gate request payload. The scoring engine reads it from the persisted `quality_gate_results` record.

### Alternatives Considered
- Call FMP directly from Agent 03 — rejected, endpoint unavailable
- Add credit rating endpoint to Agent 01 — implemented and tested, then reverted when FMP returned empty
- Fetch from Agent 02 newsletter signals — not reliable enough for a gate check

### Consequences
- Caller must provide `credit_rating` in gate request
- No automated credit rating refresh
- Acceptable for current platform maturity

---

## ADR-003: Agent 01 HTTP API (Not Direct DB)

**Date:** 2026-02-26  
**Status:** Accepted

### Context
Agent 01 and Agent 03 share the same PostgreSQL instance. Agent 03 could query `market_data_daily` and `price_history` directly for performance.

### Decision
Agent 03 always calls Agent 01 via HTTP API. Direct DB access is prohibited.

### Rationale
- Agent 01 owns its data and cache layer
- Direct DB queries bypass Agent 01's Redis caching (doubles DB load)
- Microservice boundary prevents tight coupling
- Agent 01's provider routing (Polygon → FMP → yfinance) is transparent to Agent 03

### Consequences
- Agent 03 latency includes Agent 01 HTTP roundtrip (~50–200ms per call)
- Agent 03 degrades gracefully if Agent 01 is down (returns partial scores)

---

## ADR-004: Plain Python Migration (No Alembic)

**Date:** 2026-02-26  
**Status:** Accepted

### Context
Agent 01 uses Alembic. The platform venv is shared across services. Running Alembic from a service subdirectory with `sys.path` complications caused `ModuleNotFoundError` for Agent 03 during setup.

### Decision
Use plain Python `scripts/migrate.py` matching Agent 02's established pattern. Run with `PYTHONPATH=. python scripts/migrate.py` from service root.

### Consequences
- No automatic migration versioning
- Manual `--drop-first` flag for destructive resets
- Consistent pattern across Agent 02 and Agent 03
- Simpler debugging — no Alembic env.py path resolution

---

## ADR-005: 50% Partial Credit for Missing Data

**Date:** 2026-02-26  
**Status:** Accepted

### Context
Agent 01 may return incomplete fundamental data for some tickers. Scoring all missing fields as 0 would artificially push incomplete tickers to grade F.

### Decision
Missing fields receive 50% of their sub-component maximum. `data_completeness_pct` tracks how many fields were present, giving callers visibility into data quality.

### Consequences
- Tickers with partial data can still receive ACCUMULATE recommendations
- `data_completeness_pct` must be considered alongside grade when making decisions
- 50% is a conservative assumption — may be tuned in Phase 3 with ML model

---

## ADR-006: Configurable Monte Carlo Simulations

**Date:** 2026-02-26  
**Status:** Accepted

### Context
NAV erosion analysis accuracy improves with more simulations but increases compute time. Different environments (dev, prod) have different performance requirements.

### Decision
`nav_erosion_simulations` is configurable via `settings.nav_erosion_simulations` (default: 10,000). Environment variable `NAV_EROSION_SIMULATIONS` overrides the default.

### Consequences
- Dev environments can use 1,000 for fast tests
- Production uses 10,000 for accuracy
- Future: increase to 50,000 or 100,000 for high-stakes decisions

---

## ADR-007: Inline Quality Gate Fallback in `/scores/evaluate`

**Date:** 2026-02-26  
**Status:** Accepted

### Context
The original `POST /scores/evaluate` required a prior call to `POST /quality-gate/evaluate`. This created a two-step workflow that could be simplified.

### Decision
Add optional `gate_data` field to `ScoreRequest`. If provided and no DB gate record exists, run the gate inline, persist the result, then proceed to scoring.

### Consequences
- Single-step evaluation possible for new tickers
- Gate data is always persisted regardless of path
- Callers can still use the two-step workflow for explicit gate control
