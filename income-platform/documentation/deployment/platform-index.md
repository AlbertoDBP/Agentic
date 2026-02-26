# Income Fortress Platform — Master Documentation Index

**Repository:** `/Agentic/income-platform/`  
**Last Updated:** 2026-02-25  
**Platform Version:** 0.3.0

---

## Platform Overview

The Income Fortress Platform is a 24-agent AI-powered investment system focused on **capital preservation and income generation**. Core principles:

- **Capital safety first** — 70% threshold with VETO power across all scoring decisions
- **No auto-execution** — proposal-based workflows; user approves all actions
- **Yield trap detection** — Monte Carlo simulation, NAV erosion analysis, coverage ratio monitoring
- **Multi-class income** — 7 asset classes: REITs, mREITs, BDCs, CEFs, Covered Call ETFs, Bonds, Preferred Stocks

**Infrastructure:** DigitalOcean (managed PostgreSQL, Valkey, App Platform, Nginx + SSL)  
**Domain:** legatoinvest.com

---

## Agent Status

| Agent | Name | Status | Docs |
|---|---|---|---|
| **Agent 01** | Market Data Service | ✅ Production | [docs](agents/agent-01-market-data/) |
| **Agent 02** | Newsletter Ingestion | 🔄 In Development (Phase 2) | [docs](agents/agent-02-newsletter-ingestion/) |
| **Agent 03** | Income Scorer | 📐 Design Complete | [docs](agents/agent-03-income-scorer/docs/index.md) |
| **Agent 04** | Asset Class Evaluator | 🔲 Scoped — Design Pending | — |
| **Agent 05** | Tax Optimizer | 🔲 Role Defined — Design Pending | — |
| Agents 06–24 | Various | 🔲 Planned | — |

**Legend:** ✅ Production · 🔄 In Development · 📐 Design Complete · 🔲 Planned

---

## Agent 03 — Income Scorer Documentation

> **Status: DESIGN COMPLETE — Ready for Phase 1 Development**

| Document | Description |
|---|---|
| [Index](agents/agent-03-income-scorer/docs/index.md) | Navigation hub, decision register, invariants, phase plan |
| [Reference Architecture](agents/agent-03-income-scorer/docs/architecture/reference-architecture.md) | System overview, data flow, weight tables, gate criteria, VETO conditions |
| [Functional Spec](agents/agent-03-income-scorer/docs/functional/agent-03-functional-spec.md) | Responsibilities, interfaces, dependencies, success criteria |
| [Implementation Spec](agents/agent-03-income-scorer/docs/implementation/agent-03-implementation-spec.md) | Phase plan, code patterns, API endpoints, migrations, test suite |
| [ADR-001](agents/agent-03-income-scorer/docs/decisions/ADR-001-post-scoring-llm-explanation.md) | Post-Scoring LLM Explanation Layer |
| [System Architecture Diagram](agents/agent-03-income-scorer/docs/diagrams/system-architecture.mmd) | Platform integration flowchart |
| [Scoring Flow Sequence](agents/agent-03-income-scorer/docs/diagrams/scoring-flow-sequence.mmd) | 10-step scoring sequence diagram |
| [Data Model](agents/agent-03-income-scorer/docs/diagrams/data-model.mmd) | 7-table ER diagram |

### Agent 03 Phase Plan

| Phase | Focus | Status |
|---|---|---|
| 1 | Foundation — DB models, migrations, DataProvider, skeleton | 🔲 Ready to start |
| 2 | Quality Gate Router — 8 class gates + universal fallback | 🔲 Pending Phase 1 |
| 3 | Monte Carlo Engine — NAV erosion + cache | 🔲 Pending Phase 2 |
| 4 | Composite Scorer — sub-scorers, weight loading, VETO | 🔲 Pending Phase 3 |
| 5 | API & Output — routes, score builder, tax metadata, LLM explanation | 🔲 Pending Phase 4 |
| 6 | Learning Loop — shadow portfolio, quarterly weight adjustment | 🔲 Pending Phase 5 |

---

## Shared Utilities

| Utility | Location | Status | Consumers |
|---|---|---|---|
| Asset Class Detector | `/shared/asset_class_detector/` | 🔲 Design complete — implementation pending | Agent 03, 04, 05+ |

---

## Architecture Decision Records

| ADR | Title | Date | Status |
|---|---|---|---|
| [ADR-001](agents/agent-03-income-scorer/docs/decisions/ADR-001-post-scoring-llm-explanation.md) | Post-Scoring LLM Explanation Layer | 2026-02-25 | ✅ Accepted |

Full decisions log: [decisions-log.md](docs/decisions-log.md)

---

## Platform Documentation

| Document | Description |
|---|---|
| [CHANGELOG](docs/CHANGELOG.md) | Version history and release notes |
| [Decisions Log](docs/decisions-log.md) | All ADRs and key design decisions |

---

## Repository Structure

```
/Agentic/income-platform/
├── agents/
│   ├── agent-01-market-data/
│   ├── agent-02-newsletter-ingestion/
│   └── agent-03-income-scorer/
│       ├── docs/
│       │   ├── index.md
│       │   ├── CHANGELOG.md
│       │   ├── decisions-log.md
│       │   ├── architecture/
│       │   │   └── reference-architecture.md
│       │   ├── functional/
│       │   │   └── agent-03-functional-spec.md
│       │   ├── implementation/
│       │   │   └── agent-03-implementation-spec.md
│       │   ├── decisions/
│       │   │   └── ADR-001-post-scoring-llm-explanation.md
│       │   └── diagrams/
│       │       ├── system-architecture.mmd
│       │       ├── scoring-flow-sequence.mmd
│       │       └── data-model.mmd
│       └── src/                    ← Phase 1 implementation starts here
├── shared/
│   └── asset_class_detector/       ← Shared utility (implementation pending)
├── docs/
│   ├── CHANGELOG.md
│   └── decisions-log.md
└── README.md
```

---

## Development Workflow

This platform uses a **dual-Claude workflow**:
- **Claude Code (VS Code)** — Implementation: writing code, running tests, deployments
- **Claude Chat (this interface)** — Architecture: design decisions, documentation generation, strategic planning

**Git discipline:** Always work from monorepo root (`/Agentic/`). Pull latest before development. Commit design artifacts before Document phase runs.

---

## Open Questions

| Question | Priority | Target |
|---|---|---|
| Agent 04 design — when to start? | High | After Agent 03 Phase 1–2 stable |
| Polygon + FMP migration timing | High | Before Agent 03 Phase 3 (needs FMP for gate criteria) |
| ML classifier training data collection | Medium | Start during Agent 03 Phase 1 |
| Agent 05 Tax Optimizer design | Medium | After Agent 03 design |
