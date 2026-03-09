# Architecture Decision Records — Agent 05

---

## ADR-005-01: Rule-Based Tax Engine (No External Tax API)

**Date:** 2026-03-09
**Status:** Accepted

### Context
Tax calculation requires federal brackets, state rates, and special treatment rules. Options considered:
1. External tax API (e.g., TaxJar, Avalara)
2. Rule-based constants maintained in code

### Decision
Rule-based constants in `calculator.py`.

### Rationale
- Investment income tax rules change only once per year (IRS updates in November/December for next tax year)
- External APIs add latency, cost, and an availability dependency for deterministic calculations
- Tables are simple enough to maintain manually with annual review
- No internet dependency in production hot path

### Consequences
- Annual maintenance required each January (update bracket tables)
- State rates are top-marginal approximations — full bracket schedules deferred to future enhancement

---

## ADR-005-02: Agent 04 as Soft Dependency with 3-Second Timeout

**Date:** 2026-03-09
**Status:** Accepted

### Context
Asset class is needed for tax treatment profiling. Agent 04 classifies assets but may be unavailable.

### Decision
Call Agent 04 with a 3-second `httpx` timeout. On any failure (timeout, error, unavailable), default to `ORDINARY_INCOME` and set `asset_class_fallback: true` in the response.

### Rationale
- ORDINARY_INCOME is the most conservative (highest tax) assumption — never underestimates tax burden
- Surfacing the fallback flag allows downstream consumers to decide whether to retry
- Platform philosophy: never silently degrade — always flag degraded state
- 3 seconds chosen to not block user-facing requests while still allowing for network latency

### Consequences
- Users see `asset_class_fallback: true` when Agent 04 is down — clear signal to investigate
- Tax calculations may overestimate burden for qualified dividend assets during degraded mode

---

## ADR-005-03: MLP UBTI Rule — Never Place in IRA

**Date:** 2026-03-09
**Status:** Accepted

### Context
MLPs generate Unrelated Business Taxable Income (UBTI) inside IRA accounts, which creates unexpected tax liability for the account holder and can trigger IRS penalties.

### Decision
The optimizer always recommends TAXABLE for MLP holdings, overriding any input `account_type`. This is a hard rule with no override.

### Rationale
- UBTI > $1,000 in an IRA triggers Form 990-T filing requirement and federal income tax
- This is one of the most common expensive mistakes made by income investors
- Capital preservation principle extends to protecting users from regulatory/tax traps

### Consequences
- MLP holdings cannot be sheltered — tax drag is unavoidable for this asset class
- Optimizer notes always include UBTI warning for MLP positions

---

## ADR-005-04: Proposals-Only Architecture for Optimizer and Harvester

**Date:** 2026-03-09
**Status:** Accepted

### Context
The optimizer and harvester could theoretically trigger trades or account transfers automatically.

### Decision
Both modules return recommendations only. No execution capability exists in Agent 05.

### Rationale
- Core platform philosophy: all investment actions require explicit user acknowledgment
- Tax-loss harvesting has wash-sale implications that require human judgment on replacement securities
- Account transfers involve custodian-specific workflows outside the platform's scope

### Consequences
- Users must act on recommendations manually
- Future Agent 12 (Proposal Agent) will synthesize Agent 05 recommendations into actionable proposals

---

## ADR-005-05: Read-Only Database Access

**Date:** 2026-03-09
**Status:** Accepted

### Context
Agent 05 could benefit from user tax preferences stored in the platform DB.

### Decision
Agent 05 reads only from the existing `user_preferences` table via SELECT. No new tables are created. `scripts/migrate.py` is a documented no-op.

### Rationale
- Minimal footprint principle — tax logic is stateless by design
- User preferences are set via other platform flows; Agent 05 consumes but does not own them
- Reduces schema coupling and simplifies deployment

### Consequences
- All endpoints function without a DB connection (graceful degradation)
- User-specific tax preferences only applied when `user_id` is present and DB is available
