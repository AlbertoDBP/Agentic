# Income Fortress Platform — Decisions Log

Consolidated record of all architecture decision records (ADRs) and key design decisions made during platform development.

---

## Architecture Decision Records

| ADR | Title | Agent Scope | Date | Status |
|---|---|---|---|---|
| [ADR-001](#adr-001) | Post-Scoring LLM Explanation Layer | Agent 03 + Chat Layer | 2026-02-25 | ✅ Accepted |

---

## ADR-001: Post-Scoring LLM Explanation Layer {#adr-001}

**Full Document:** [decisions/ADR-001-post-scoring-llm-explanation.md](decisions/ADR-001-post-scoring-llm-explanation.md)

**Date:** 2026-02-25  
**Status:** Accepted  
**Scope:** Agent 03 (Income Scorer) + Chat Layer  

**Summary:**  
After the deterministic scoring pipeline completes, pass the structured score output JSON to an LLM that generates a plain-English explanation for the retail investor. The LLM is a pure translator — it never modifies, re-derives, or overrides any score, sub-score, VETO decision, or recommendation.

**Key Constraints:**
- Invoked on user-facing requests only (chat, dashboard, notifications) — not during background batch scoring
- Temperature: 0.3–0.5 (low creativity)
- max_tokens: 300 (focused, concise)
- Facts-only system prompt — no speculation, no new information
- Full audit trail: prompt + output + model stored in scores table

**Implementation Impact:**
- `scores` table: 4 new columns (`explanation_text`, `explanation_prompt`, `explanation_model`, `explanation_generated_at`)
- Migration: `010_add_explanation_columns_to_scores`
- Phase 5 (API & Output): `generate_explanation()` added to score output builder
- Output JSON: `explanation` field (null by default, populated on request)

**Alternatives Rejected:**
- Static template strings — readable but not explanatory; can't surface contradictions
- LLM integrated into scoring pipeline — violates deterministic scoring principle
- No explanation layer — unacceptable for retail investor UX

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
| Primary data provider | Alpha Vantage (current) | 2026-01-26 | Established integration, rate-limited |
| Migration target | Polygon + FMP | Planned | Better coverage for income-specific metrics |
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
| Polygon + FMP migration timing | After Agent 02 completion or before Agent 03 dev? | Platform | High |
| ML classifier training data | When to start collecting labeled ticker dataset for v2 detector | Shared | Medium |
| Agent 05 Tax Optimizer design | Scope confirmed; design not started | Agent 05 | Medium |
| Monte Carlo simulation count | 1K (batch) vs 10K (deep analysis) — configurable? | Agent 03 | Low |
