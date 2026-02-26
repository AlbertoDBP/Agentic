# Income Fortress Platform — CHANGELOG

All notable changes to the Income Fortress Platform are documented here.  
Format: [Semantic Versioning](https://semver.org/) — `[version] YYYY-MM-DD`

---

## [Unreleased]

### Planned
- Agent 03 Phase 1–6 implementation
- Agent 04 — Asset Class Evaluator design
- Multi-provider data migration (Polygon + FMP)
- Shared Asset Class Detector v1 implementation

---

## [0.3.0] — 2026-02-25 — Agent 03 Design Complete

### Added
- **Agent 03 — Income Scorer**: Complete architecture design
  - 7-class scoring framework (REITs, mREITs, BDCs, CEFs, Covered Call ETFs, Bonds, Preferred Stocks)
  - Quality Gate Router with 8 class-specific gates + universal fallback
  - Composite scorer with full replacement weight sets per asset class
  - VETO engine (post-composite — preserves sub-scores for audit)
  - Monte Carlo NAV erosion analysis (Covered Call ETFs, mREITs, leveraged CEFs)
  - Risk penalty layer with Agent 02 negative-signal integration
  - Tax efficiency as parallel metadata field (0% composite weight)
  - Quarterly adaptive learning loop with shadow portfolio
  - 10 Alembic database migrations specified
  - FastAPI endpoints defined (8 routes)
  - Full test suite spec (unit, integration, acceptance, performance SLAs)

- **ADR-001**: Post-Scoring LLM Explanation Layer
  - LLM translates deterministic score output to plain English
  - Invoked on user-facing requests only (not batch scoring)
  - Temperature 0.3–0.5, max_tokens 300, facts-only prompt
  - Full audit trail: prompt + output stored in scores table
  - 4 new columns added to scores table migration

- **Shared Utility**: Asset Class Detector
  - Location: `/Agentic/income-platform/shared/asset_class_detector/`
  - v1: Rule-based (yfinance metadata)
  - v2: ML-based (sentence-transformers + linear head) — post-MVP
  - Consumed by Agent 03, Agent 04, Agent 05 and future agents

- **Agent 04 — Asset Class Evaluator**: Scoped (design pending)
  - Benchmark comparison, class sub-scores, cross-class recommendations
  - Consumes Agent 03 scored_event from message bus

- **Agent 05 — Tax Optimizer**: Role clarified and expanded
  - Consumes tax_efficiency metadata from Agent 03 output
  - User-specific after-tax yield scenarios
  - Account placement advice (taxable / Roth / IRA)
  - FL residency context integration

### Changed
- **Data Stack**: yfinance promoted to primary provider
  - FMP for gaps: AFFO, NII, CEF discount/premium, non-accrual data
  - Polygon for options chain depth and price precision
  - DataProvider abstraction layer enforced — no direct provider calls in scoring logic

- **Scoring Architecture**: Split from monolithic to modular
  - Agent 03 = Income Fortress Score (capital safety + income quality)
  - Agent 04 = Asset Class Evaluation (benchmark context — design pending)
  - Previously undifferentiated; now cleanly bounded

### Design Decisions Locked
| # | Decision | Choice |
|---|---|---|
| 1 | Agent 03 scope | Income Scorer core only |
| 2 | Asset class coverage | All 7 from day one, MVP priority on stocks/ETFs/bonds |
| 3 | Quality gate placement | Agent 03 internal pre-scoring module |
| 4 | Weight framework | Full replacement sets per class |
| 5 | Decision matrix | Universal thresholds 85/70 + class context in output |
| 6 | Tax efficiency | 0% weight, parallel metadata field |
| 7 | Newsletter signals | Negative-only penalty layer |
| 8 | Monte Carlo scope | Covered ETFs, mREITs, CEFs — 30-day cache |
| 9 | Data stack | yfinance → FMP → Polygon resolution order |
| 10 | Asset class detector | Shared utility, rule-based v1 |
| 11 | Learning loop | Quarterly, LR=0.01, ±5% max per cycle |
| 12 | VETO placement | Post-composite |

---

## [0.2.0] — 2026-02-05 — Agent 02 Phase 1 Complete

### Added
- Agent 02 — Newsletter Ingestion Service Phase 1 (foundation)
  - SQLAlchemy models and database migrations with pgvector support
  - Comprehensive unit tests
  - Seeking Alpha API integration (validated against actual response shapes)
- Agent 02 Phase 2 — Harvester flow implemented

### In Progress
- Agent 02 Phases 3–5 (signal extraction, database integration, API endpoints)

---

## [0.1.0] — 2026-01-26 — Agent 01 Production Deployed

### Added
- Agent 01 — Market Data Service: production deployment
  - FastAPI microservice with Redis caching
  - Alpha Vantage integration with rate limiting and fallback chains
  - Database persistence (PostgreSQL managed, DigitalOcean)
  - Real-time stock data with proper fallback handling
- Platform infrastructure: DigitalOcean App Platform, managed PostgreSQL (68+ tables), Valkey cache, Nginx reverse proxy with SSL
- Reference architecture: 24-agent platform design
- Monorepo structure: `/Agentic/income-platform/`

---

## Legend
- **Added** — New features or components
- **Changed** — Changes to existing functionality
- **Deprecated** — Features to be removed in future
- **Removed** — Features removed
- **Fixed** — Bug fixes
- **Security** — Security-related changes
