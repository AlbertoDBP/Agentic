# Income Fortress Platform — Decisions Log

Consolidated record of all Architecture Decision Records (ADRs) and key design decisions made during platform development.

---

## ADR Index

| ADR | Title | Date | Status | Impact |
|---|---|---|---|---|
| [ADR-001](#adr-001) | Post-Scoring LLM Explanation Layer | 2026-02-25 | ✅ Accepted | Medium — UX/explainability |
| [ADR-002](#adr-002) | NAV Erosion Calculation for Covered Call ETFs | 2026-01-18 | ✅ Accepted | High — ETF scoring accuracy |
| [ADR-003](#adr-003) | ROC Tax Efficiency Tracking | 2026-01-20 | ✅ Accepted | Medium — Tax optimization |
| [ADR-004](#adr-004) | Granular SAIS Curves (5-Zone Scoring) | 2026-01-22 | ✅ Accepted | High — Scoring precision |
| [ADR-005](#adr-005) | Profile-Driven Circuit Breaker Auto-Enable | 2026-01-25 | ✅ Accepted | Medium — User protection |
| [ADR-006](#adr-006) | Preference-Based Configuration System | 2026-01-28 | ✅ Accepted | High — Multi-tenancy |
| [ADR-008](#adr-008) | Celery Queue Specialization (6 Queues) | 2026-01-31 | ✅ Accepted | Medium — Task prioritization |
| [ADR-009](#adr-009) | Structured JSON Logging | 2026-02-01 | ✅ Accepted | Medium — Observability |
| [ADR-010](#adr-010) | Manual Tax Breakdown Mapping (Short-Term) | 2026-02-02 | ✅ Accepted (Interim) | Low — Temporary solution |

*Note: ADR-007 (Docker Compose vs Kubernetes) referenced in original summary but document not recovered. ADR-011+ planned.*

---

## Architecture Decision Records

---

### ADR-001: Post-Scoring LLM Explanation Layer {#adr-001}

**Date:** 2026-02-25
**Status:** ✅ Accepted
**Scope:** Agent 03 (Income Scorer) + Chat Layer
**Deciders:** Alberto

#### Context
The Income Scorer produces a deterministic composite score (0–100) with up to 12 sub-components, VETO status, risk flags, Monte Carlo results, and tax metadata. While precise and auditable, this structured JSON output is difficult for retail investors to interpret directly. The platform needs plain-English explanations in chat, email/SMS notifications, and dashboard tooltips — without compromising scoring integrity.

#### Decision
After the deterministic scoring pipeline completes, pass the full output JSON to an LLM with a constrained prompt that generates a plain-English explanation. The LLM operates strictly as a translator — it reads already-computed numbers and converts them to natural language. It never modifies, overrides, or re-derives any score, sub-score, VETO decision, or recommendation.

**Key constraints:**
- Invoked on user-facing requests only — not during background batch scoring
- Temperature: 0.3–0.5 (low creativity)
- max_tokens: 300 (focused, concise)
- Facts-only system prompt — no speculation, no new information
- Full audit trail: prompt + output + model stored in scores table

#### Rationale
1. **Explainability:** Raw sub-scores become intuitive narratives
2. **VETO clarity:** Capital safety leads the explanation when veto fires
3. **Zero score integrity risk:** LLM receives output only after computation completes
4. **Low cost:** One inference per user-facing query, not per background run

#### Consequences
**Positive:** Retail investors understand why a decision was made. VETO emphasis reinforces capital safety first. Audit trail stored with every explanation.

**Negative:** Hallucination risk (mitigated by low temperature + facts-only prompt). Additional latency on user-facing queries (~200–500ms). Model provider dependency.

#### Implementation Impact
- `scores` table: 4 new columns (`explanation_text`, `explanation_prompt`, `explanation_model`, `explanation_generated_at`)
- Migration: `010_add_explanation_columns_to_scores`
- Phase 5 (API & Output): `generate_explanation()` added to score output builder
- Output JSON: `explanation` field (null by default, populated on user-facing requests)

#### Full Document
`agents/agent-03-income-scorer/docs/decisions/ADR-001-post-scoring-llm-explanation.md`

---

### ADR-002: NAV Erosion Calculation for Covered Call ETFs {#adr-002}

**Date:** 2026-01-18
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Covered call ETFs can have attractive yields (10–12%+) but suffer from NAV erosion over time as they sacrifice upside. Need an objective measure to detect value destruction masked by high distributions.

#### Decision
Implement benchmark-relative NAV erosion calculation:
```python
Adjusted Erosion = (NAV_t + Cumulative_Dist) / NAV_0 ^ (365/days) - 1
                 - (Benchmark_t / Benchmark_0) ^ (365/days) - 1
```
- Use 3-year history (1-year fallback for newer ETFs)
- Weight at 20% in covered call ETF scoring
- Threshold: -10% max acceptable erosion
- Benchmark mapping: SPY, QQQ, IWM per ETF

#### Rationale
Distributions can mask declining NAV. Benchmark-relative comparison shows what investor could have earned in the index. Total return focus includes distributions. Annualized for consistent comparison across time periods.

#### Consequences
**Positive:** Identifies ETFs destroying value despite high yield. Protects users from yield traps. Comparable across time periods.

**Negative:** Requires 3 years of data (limits coverage of new ETFs). Uses Adj Close as NAV proxy (~0.5% error margin). Benchmark selection affects score.

**Note:** This ADR directly informs the Agent 03 Monte Carlo NAV Erosion Engine design. The -10% threshold is encoded as a quality gate criterion for the `CoveredCallETFGate`.

---

### ADR-003: ROC Tax Efficiency Tracking {#adr-003}

**Date:** 2026-01-20
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Tax efficiency is critical for income investors. Return of Capital (ROC) distributions are tax-deferred vs qualified dividends (0–20% tax) vs ordinary income (up to 37% tax). Few platforms track this systematically.

#### Decision
Implement comprehensive tax efficiency tracking:
- Track ROC %, qualified %, ordinary % for each asset
- Weight: ROC=100 pts, Qualified=75 pts, Ordinary=0 pts
- Section 1256 bonus: +10% for index option ETFs
- Manual mapping for known ETFs, updated quarterly (see ADR-010)

#### Rationale
After-tax returns matter. 37% tax on ordinary income significantly impacts real yield. ROC is undervalued by most investors. Section 1256 (60/40 treatment) provides meaningful advantage for SPYI-type ETFs.

#### Consequences
**Positive:** Highlights tax-advantaged ETFs like SPYI (92% ROC). Educates users on tax treatment. Competitive differentiation.

**Negative:** Manual mapping required (no reliable API). Quarterly maintenance burden. Tax breakdown can change year-to-year.

**Note (Agent 03 integration):** Per ADR-001 context and Agent 03 design, tax efficiency tracking is implemented as a **parallel metadata field** in the score output with **0% composite weight**. The ROC/qualified/ordinary percentages flow to Agent 05 (Tax Optimizer) for user-specific after-tax analysis. The weighting system (ROC=100, Qualified=75) described here applies within Agent 05, not in the composite score.

---

### ADR-004: Granular SAIS Curves (5-Zone Scoring) {#adr-004}

**Date:** 2026-01-22
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Original SAIS scoring used 3 zones (danger/acceptable/excellent). Hybrid prototype showed 5-zone curves provide better precision in the danger/warning areas where most scoring decisions occur.

#### Decision
Implement 5-zone granular curves for SAIS components:

**Coverage Zones:**
- Danger (<0.8×): 0–20 pts
- Critical (0.8–1.0×): 20–50 pts
- Acceptable (1.0–sector_min): 50–75 pts
- Good (sector_min–1.3×): 75–95 pts
- Excellent (>1.3×): 95–100 pts

**Leverage Zones:**
- Danger (>1.25× max): 0–40 pts
- Elevated (1.0–1.25×): 40–60 pts
- Acceptable (0.8–1.0×): 60–80 pts
- Good (0.5–0.8×): 80–95 pts
- Excellent (<0.5×): 95–100 pts

#### Rationale
Proven in hybrid prototype with higher prediction accuracy. Better separation of marginal assets. Sector calibration via `sector_min` allows per-class tuning.

#### Consequences
**Positive:** More nuanced scoring. Better danger detection (0–20 vs 20–50 separates severe from critical). Easier to tune thresholds.

**Negative:** Slightly more complex to explain. More parameters to maintain.

**Note (Agent 03 integration):** Zone thresholds are stored in the Preference Table per asset class, enabling chat-based overrides without code deployments.

---

### ADR-005: Profile-Driven Circuit Breaker Auto-Enable {#adr-005}

**Date:** 2026-01-25
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Circuit breaker monitoring is critical for high-yield assets (REITs, BDCs, mREITs) that can deteriorate quickly, but not all users know when to enable it.

#### Decision
Auto-enable circuit breaker based on asset profile:
```python
if asset_type in [REIT, BDC, MREIT] or sector in high_yield_sectors:
    check_circuit_breaker = True
else:
    check_circuit_breaker = preference.get('circuit_breaker_in_scoring', False)
```

#### Rationale
Smart defaults protect users who don't know to enable monitoring. Risk-based approach targets assets that need it most. Users can override via preferences.

#### Consequences
**Positive:** Better protection for risky assets. Reduced configuration burden. Catches deteriorating positions early.

**Negative:** Slight performance overhead. May trigger false positives.

---

### ADR-006: Preference-Based Configuration System {#adr-006}

**Date:** 2026-01-28
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Multi-tenant platform needs per-tenant configuration without code changes. Different users have different risk tolerances and preferences.

#### Decision
Implement preference system with:
- Tenant-specific preference table
- Per-agent, per-parameter configuration
- JSONB value storage for flexibility
- 5-minute TTL cache
- Defaults with override capability

#### Rationale
Essential for SaaS model. No-code configuration. JSONB allows any preference type. 5-min cache prevents excessive DB queries.

#### Consequences
**Positive:** Highly customizable per tenant. No deployments for config changes. Easy to add new preferences.

**Negative:** Cache invalidation complexity. Potential for configuration drift.

**Note (Agent 03 integration):** The Preference Table is the single source of truth for all Agent 03 scoring weights, gate thresholds, and learning loop bounds. This is a direct application of ADR-006 — no scoring configuration lives in code.

---

### ADR-008: Celery Queue Specialization (6 Queues) {#adr-008}

**Date:** 2026-01-31
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Different tasks have different priority and resource requirements. Need efficient task routing and prioritization.

#### Decision
6 specialized queues with priority-based routing:
- **alerts** (priority 10): Urgent notifications
- **monitoring** (priority 9): Circuit breaker checks
- **scoring** (priority 8): Asset scoring requests
- **proposals** (priority 7): Proposal generation
- **analysis** (priority 6): Market data, features
- **portfolio** (priority 5): Portfolio operations
- **background** (priority 1): Cleanup, maintenance

3 workers: scoring+analysis / portfolio+proposals / monitoring+alerts

#### Consequences
**Positive:** Better task prioritization. Predictable alert delivery. Independent scaling.

**Negative:** More complex configuration. Potential for queue imbalance.

---

### ADR-009: Structured JSON Logging {#adr-009}

**Date:** 2026-02-01
**Status:** ✅ Accepted
**Deciders:** Alberto

#### Context
Need production-grade logging for debugging, auditing, and compliance. Logs should be machine-parseable.

#### Decision
Structured JSON logging with: ISO timestamp, log level, logger name, request ID (tracing), message, context (arbitrary key-value pairs). Log rotation: 10MB, 10 backups.

#### Consequences
**Positive:** Machine parseable. Supports log aggregation. Compliance-ready audit trail.

**Negative:** Larger log files. Less human-readable (use `cat log.json | jq` locally).

---

### ADR-010: Manual Tax Breakdown Mapping (Short-Term) {#adr-010}

**Date:** 2026-02-02
**Status:** ✅ Accepted (Interim)
**Deciders:** Alberto

#### Context
Need tax breakdown (ROC %) for covered call ETFs but no reliable API exists. ETF providers publish 19a-1 notices but format varies.

#### Decision
**Phase 1:** Manual mapping in code, updated quarterly.
**Phase 2–3:** Automate 19a-1 notice scraping.

```python
KNOWN_TAX_BREAKDOWNS = {
    'SPYI': {'roc_percentage': 0.92, 'qualified': 0.05, 'ordinary': 0.03},
    'JEPI': {'roc_percentage': 0.15, 'qualified': 0.10, 'ordinary': 0.75},
    # ... top 20 ETFs by volume
}
```

#### Consequences
**Positive:** Simple implementation. No scraping complexity. Easy to verify accuracy.

**Negative:** Manual maintenance (~30 min/quarter). Limited coverage (20 ETFs initially). Updates lag up to 3 months.

**Upgrade Path:** Phase 3 — web scraping of 19a-1 notices. Phase 4 — data provider partnership if volume justifies.

---

## Key Design Decisions by Agent

### Platform-Level

| Decision | Choice | Date | Rationale |
|---|---|---|---|
| Agent count | 24 specialized agents | 2026-01-26 | Microservices independence, clear responsibilities |
| Infrastructure | DigitalOcean managed services | 2026-01-26 | Managed PostgreSQL, Valkey, App Platform |
| Proposal-based workflow | No auto-execution | 2026-01-26 | User maintains control over all investment actions |
| Capital safety threshold | 70% minimum with VETO power | 2026-01-26 | Core Income Fortress principle |

### Agent 01 — Market Data Service

| Decision | Choice | Date | Rationale |
|---|---|---|---|
| Primary data provider | Polygon + FMP (migrated) | 2026-02-23 | Better coverage for income-specific metrics |
| Fallback provider | yfinance | 2026-02-23 | Free, broad coverage |
| Caching strategy | Redis/Valkey with TTL | 2026-01-26 | Reduces API calls, improves latency |

### Agent 02 — Newsletter Ingestion

| Decision | Choice | Date | Rationale |
|---|---|---|---|
| Signal extraction model | Claude Haiku | 2026-02-05 | Cost/speed balance for high-volume ingestion |
| Vector storage | pgvector on PostgreSQL | 2026-02-05 | Avoids separate vector DB; unified storage |
| Primary source | Seeking Alpha API | 2026-02-05 | Validated against actual response shapes |

### Agent 03 — Income Scorer

| Decision | Choice | Date | Rationale |
|---|---|---|---|
| Agent scope | Income Scorer core only | 2026-02-25 | Clean separation from Agent 04 evaluator |
| Asset class coverage | All 7 from day one | 2026-02-25 | MVP priority on stocks/ETFs/bonds |
| Quality gate placement | Agent 03 internal module | 2026-02-25 | Gate must precede scoring; avoids Agent 04 dependency inversion |
| Weight framework | Full replacement sets per class | 2026-02-25 | No delta ambiguity; weights always sum to 100% |
| Decision matrix | Universal thresholds 85/70 | 2026-02-25 | Cross-class score comparability |
| Tax efficiency | 0% weight, parallel metadata | 2026-02-25 | Philosophically pure score; personalized in Agent 05 |
| Newsletter signals | Negative-only penalty | 2026-02-25 | Eliminates analyst optimism bias |
| Monte Carlo scope | Covered ETFs, mREITs, CEFs | 2026-02-25 | NAV erosion relevant to distribution-dependent classes |
| Data stack | yfinance → FMP → Polygon | 2026-02-25 | Free primary; paid APIs for gaps only |
| Asset class detector | Shared utility, rule-based v1 | 2026-02-25 | No training data needed; ML v2 post-MVP |
| Learning loop | Quarterly, shadow portfolio | 2026-02-25 | Adaptive improvement without over-fitting |
| VETO placement | Post-composite | 2026-02-25 | Preserves sub-score visibility for analytics and learning loop |

---

## Open Questions (Pending Decision)

| Question | Context | Target Agent | Priority |
|---|---|---|---|
| Agent 04 design scope | Benchmark comparison + class sub-scores | Agent 04 | High — design next |
| ML classifier training data | When to start collecting labeled ticker dataset for v2 detector | Shared | Medium |
| Agent 05 Tax Optimizer design | Scope confirmed; design not started | Agent 05 | Medium |
| Monte Carlo simulation count | 1K (batch) vs 10K (deep analysis) — configurable? | Agent 03 | Low |
| ADR-007 recovery | Docker Compose vs Kubernetes decision — document missing | Platform | Low |

---

## Future ADRs

| ADR | Topic | Trigger |
|---|---|---|
| ADR-011 | Agent 04 Asset Class Evaluator architecture | Agent 04 design phase |
| ADR-012 | Bond Scoring Methodology | Agent 03 Phase 2 |
| ADR-013 | Adaptive Learning Integration | Agent 03 Phase 6 |
| ADR-014 | Kubernetes Migration Strategy | Scale threshold reached |
| ADR-015 | Multi-Region Deployment | Production growth |
| ADR-016 | ML Model Management (Asset Class Detector v2) | Post-MVP |
