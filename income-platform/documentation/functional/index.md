# Agent 03 — Income Scorer: Design Index

**Platform:** Income Fortress Platform  
**Monorepo Path:** `/Agentic/income-platform/agents/agent-03-income-scorer/`  
**Design Date:** 2026-02-25  
**Status:** ✅ DESIGN COMPLETE — Ready for Development

---

## Quick Navigation

| Document | Purpose | Status |
|---|---|---|
| [Reference Architecture](architecture/reference-architecture.md) | System overview, data flow, component map, weight tables | ✅ Complete |
| [Functional Specification](functional/agent-03-functional-spec.md) | Responsibilities, interfaces, dependencies, success criteria | ✅ Complete |
| [Implementation Specification](implementation/agent-03-implementation-spec.md) | Technical design, phase plan, code patterns, testing | ✅ Complete |
| [System Architecture Diagram](diagrams/system-architecture.mmd) | Full platform integration flowchart (Mermaid) | ✅ Complete |
| [Scoring Flow Sequence](diagrams/scoring-flow-sequence.mmd) | Step-by-step scoring sequence diagram (Mermaid) | ✅ Complete |
| [Data Model](diagrams/data-model.mmd) | Entity relationship diagram (Mermaid) | ✅ Complete |

---

## Design Decision Summary

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Agent scope | Income Scorer core only | Clean separation from Agent 04 (evaluator) |
| 2 | Asset classes | All 7 from day one | MVP priority on stocks, ETFs, bonds |
| 3 | Quality gate | Class-specific router in Agent 03 | Gate must precede scoring; Agent 04 dependency inversion avoided |
| 4 | Weight framework | Full replacement sets per class | No delta ambiguity; weights always sum to 100% |
| 5 | Decision matrix | Universal thresholds (85/70) | Scores comparable across classes; class context in output field |
| 6 | Tax efficiency | 0% weight, parallel metadata field | Philosophically pure score; personalized in Agent 05 |
| 7 | Newsletter signals | Negative signals → risk penalty only | Avoids analyst optimism bias inflating scores |
| 8 | Monte Carlo | Covered ETFs, mREITs, CEFs | 30-day cache; vectorized NumPy |
| 9 | Data stack | yfinance primary → FMP → Polygon | Free primary; paid APIs for gaps only |
| 10 | Asset class detector | Shared utility, rule-based v1 | No training data needed; ML v2 post-MVP |
| 11 | Learning loop | Quarterly, shadow portfolio | LR=0.01, ±5% max per cycle |
| 12 | VETO placement | Post-composite | Preserves sub-score visibility for analytics |

---

## Phase Plan

| Phase | Focus | Key Deliverables |
|---|---|---|
| 1 | Foundation | DB models, migrations, DataProvider, skeleton |
| 2 | Quality Gate Router | 8 class gates + universal fallback + tests |
| 3 | Monte Carlo Engine | NAV erosion simulation + cache integration |
| 4 | Composite Scorer | 4 sub-scorers + weight loading + VETO engine |
| 5 | API & Output | FastAPI routes + score builder + tax metadata + LLM explanation (ADR-001) |
| 6 | Learning Loop | Shadow portfolio + quarterly weight adjustment |

---

## Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [ADR-001](decisions/ADR-001-post-scoring-llm-explanation.md) | Post-Scoring LLM Explanation Layer | ✅ Accepted |

---

## Related Agents

| Agent | Relationship |
|---|---|
| Agent 01 — Market Data Service | Upstream: provides price, technicals, options data |
| Agent 02 — Newsletter Ingestion | Upstream: provides sentiment signals for penalty layer |
| Shared: Asset Class Detector | `/shared/asset_class_detector/` — used by Agent 03, 04, 05+ |
| Agent 04 — Asset Class Evaluator | Downstream: consumes scored_event, adds benchmark context |
| Agent 05 — Tax Optimizer | Downstream: consumes tax_efficiency metadata + veto status |

---

## Key Invariants (Never Violate)

1. **VETO always forces composite_score to 0** — no exceptions, no overrides
2. **Tax efficiency field always populated** — including on VETO responses
3. **Positive newsletter signals never boost score** — only negative signals penalize
4. **Weight sets always sum to 100%** — enforced at load time with assertion
5. **No hardcoded weights in code** — Preference Table is the single source of truth
6. **DataProvider abstraction always used** — no direct yfinance calls in scoring logic
7. **Every score is versioned with weight snapshot** — enables learning loop auditing
