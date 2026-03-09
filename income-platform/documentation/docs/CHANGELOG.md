# CHANGELOG — Income Fortress Platform

All notable changes to this platform are documented here.
Format: [version] date — summary

---

## [1.3.0] — 2026-03-09

### Added
- **Portfolio & Positions Schema** (12 tables, 4 phases)
  - Phase 0 — Foundation: `securities` (TEXT PK), `features_historical`, `user_preferences`
  - Phase 1 — Asset: `nav_snapshots`
  - Phase 2 — Portfolio: `accounts`, `portfolios`, `portfolio_constraints`
  - Phase 3 — Position: `positions`, `transactions`, `dividend_events`
  - Phase 4 — Metrics: `portfolio_income_metrics`, `portfolio_health_scores`
- **Migration script** `portfolio-positions-v2` — phased asyncpg execution with full rollback
- **ADR-P09** — Symbol TEXT PK v1, UUID migration path for v2
- **ADR-P10** — Average cost basis v1, tax lot migration path for v2
- **Asset-Gem Amendments A1–A4**:
  - A1: `yield_5yr_avg` + `chowder_number` added to `features_historical`
  - A2: Chowder signal added to Agent 03 output (0% score weight, informational)
  - A3: Named boolean entry signal flags added to Agent 04 output
  - A4: `dca_schedule` block added to Agent 12 BUY proposals
- **Finnhub** added as 4th credit rating provider (ADR-P07) — resolves `credit_rating` NULL
- **4 trigger flow definitions**: Portfolio Review, Analyst Signal, Circuit Breaker,
  Portfolio Construction (Greenfield)
- **`user_preferences` table** — per-tenant TTL and threshold configuration
- **`features_historical` table** — created fresh (was not in production schema)

### Changed
- FK strategy: symbol TEXT throughout (ADR-P09) replaces UUID FK design
- Migration phasing: Phase 0 foundation added before portfolio layer

### Fixed
- Discovered `securities`, `features_historical`, `user_preferences` absent from
  production `platform_shared` schema — migration now creates all from scratch
- No naming conflicts with existing 12 production tables confirmed

### Agents Impacted (no breaking changes to deployed 01–05)
| Agent | Change |
|-------|--------|
| 01 | Add Finnhub credit rating provider; write nav_snapshots + features_historical |
| 03 | Add chowder_number + chowder_signal to output |
| 04 | Add named entry signal flags to output |
| 07 | income_gap_annual < 0 as autonomous trigger |
| 08 | Add construction mode (greenfield portfolio) |
| 09 | Primary owner of portfolio_income_metrics |
| 11 | Primary owner of portfolio_health_scores |
| 12 | Add dca_schedule to BUY proposals; three-FK proposal context |

---

## [1.2.0] — 2026-02-XX

### Added
- Agent 05: Tax Optimizer Service (port 8005)
- Asset classification shared detector (`src/shared/asset_class_detector/`)
- Agent 03 auto-calls Agent 04 when asset_class missing
- Tax efficiency parallel output (0% score weight)

---

## [1.1.0] — 2026-01-XX

### Added
- Agent 03: Income Scoring Service (port 8003)
  - NAV erosion analysis
  - Monte Carlo simulation
  - Dividend safety scoring
- Agent 04: Asset Classification Service (port 8004)

---

## [1.0.0] — 2025-12-XX

### Added
- Agent 01: Market Data Service (port 8001)
  - Multi-provider: Polygon.io, Financial Modeling Prep, yfinance fallback
- Agent 02: Newsletter Ingestion "The Dividend Detective" (port 8002)
  - Seeking Alpha analyst signal extraction via APIDojo + Claude
- Production infrastructure on DigitalOcean
  - Managed PostgreSQL, Valkey cache, Nginx + SSL
  - Docker Compose microservices
