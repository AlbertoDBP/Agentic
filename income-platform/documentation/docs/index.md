# Income Fortress Platform — Documentation Index

**Version:** 1.3.0
**Last Updated:** 2026-03-09
**Status:** Active Development — Agents 01–05 Deployed

---

## Platform Overview

The Income Fortress Platform is a 24-agent AI-powered financial technology system
focused on income-generating investments. Core principles:

- **Capital preservation first** — 70% safety threshold with veto power
- **Yield trap avoidance** — NAV erosion detection, Monte Carlo simulation
- **User control** — proposal-based workflows, never auto-execution
- **Unit of analysis** — `Asset × Position × Portfolio` (joint context required)

Infrastructure: DigitalOcean droplet (2 vCPU/4 GB RAM), managed PostgreSQL,
Valkey cache, Nginx + SSL, Docker Compose microservices at legatoinvest.com.

---

## Documentation Structure

```
documentation/
├── index.md                          ← this file
├── CHANGELOG.md
├── architecture/
│   ├── reference-architecture.md
│   ├── system-diagram.mmd
│   ├── data-model.mmd
│   └── agent-rw-matrix.md
├── functional/
│   ├── agent-01-market-data.md
│   ├── agent-02-newsletter-ingestion.md
│   ├── agent-03-income-scoring.md
│   ├── agent-04-asset-classification.md
│   ├── agent-05-tax-optimizer.md
│   ├── portfolio-schema.md           ← NEW v1.3
│   └── asset-gem-amendments.md       ← NEW v1.3
├── implementation/
│   ├── agent-01-impl.md
│   ├── agent-02-impl.md
│   ├── agent-03-impl.md
│   ├── agent-04-impl.md
│   ├── agent-05-impl.md
│   └── portfolio-schema-impl.md      ← NEW v1.3
├── diagrams/
│   ├── portfolio-erd.mmd             ← NEW v1.3
│   └── trigger-flows.mmd             ← NEW v1.3
└── decisions/
    ├── decisions-log.md              ← ADRs P01–P10
    └── adrs-p09-p10.md              ← NEW v1.3
```

---

## Agent Status

| Agent | Name | Port | Status | Notes |
|-------|------|------|--------|-------|
| 01 | Market Data Service | 8001 | ✅ Deployed | Finnhub credit ratings pending |
| 02 | Newsletter Ingestion | 8002 | ✅ Deployed | Seeking Alpha signals |
| 03 | Income Scoring | 8003 | ✅ Deployed | Chowder signal output pending |
| 04 | Asset Classification | 8004 | ✅ Deployed | Entry signal flags pending |
| 05 | Tax Optimizer | 8005 | ✅ Deployed | Position-level v1 |
| 06 | Scenario Simulation | 8006 | 🔲 Not started | ElasticNet GLM, stress tests |
| 07 | Income Gap Detector | 8007 | 🔲 Not started | Triggered by income_gap_annual < 0 |
| 08 | Portfolio Constructor | 8008 | 🔲 Not started | Greenfield + ACTIVE construction modes |
| 09 | Income Metrics | 8009 | 🔲 Not started | Portfolio income rollup |
| 10 | NAV Monitor | 8010 | 🔲 Not started | nav_snapshots owner |
| 11 | Portfolio Health | 8011 | 🔲 Not started | health_score owner |
| 12 | Proposal Agent | 8012 | 🔲 Not started | Dual-lens synthesis |
| 13–24 | Future agents | — | 🔲 Not started | Roadmap |

---

## Schema Status

| Layer | Tables | Status |
|-------|--------|--------|
| Phase 0 — Foundation | securities, features_historical, user_preferences | 🔲 Migration ready |
| Phase 1 — Asset | nav_snapshots | 🔲 Migration ready |
| Phase 2 — Portfolio | accounts, portfolios, portfolio_constraints | 🔲 Migration ready |
| Phase 3 — Position | positions, transactions, dividend_events | 🔲 Migration ready |
| Phase 4 — Metrics | portfolio_income_metrics, portfolio_health_scores | 🔲 Migration ready |

Migration script: `src/portfolio-positions-schema/scripts/migrate.py`

---

## Key Design Decisions (ADR Summary)

| ADR | Title | Status |
|-----|-------|--------|
| P01 | Monte Carlo NAV Erosion in Agent 03 | Accepted |
| P02 | Asset Classification Shared Detector | Accepted |
| P03 | Tax Efficiency as Parallel Output (0% weight) | Accepted |
| P04 | Proposal-Only Architecture (no auto-execution) | Accepted |
| P05 | Analyst Signal Storage Schema | Accepted |
| P06 | Portfolio Health Score TTL Strategy | Accepted |
| P07 | Finnhub as 4th Credit Rating Provider | Accepted |
| P08 | Income Gap as Autonomous Agent 07 Trigger | Accepted |
| P09 | Symbol TEXT PK v1, UUID Migration Path v2 | Accepted |
| P10 | Average Cost Basis v1, Tax Lot v2 | Accepted |

Full ADR details: [decisions/decisions-log.md](decisions/decisions-log.md)

---

## Quick Reference

**Infrastructure:**
- Production: `root@legatoinvest.com` via `~/.ssh/id_ed25519`
- App path: `/opt/Agentic/income-platform`
- Monorepo: `/Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform`

**Docker patterns:**
- No `db` depends_on — use `python3 urllib` healthcheck
- No `networks` block
- `--only-binary :all:` for pydantic-core and asyncpg
- DB SSL: strip `?sslmode=require`, pass `connect_args={"ssl": "require"}`

**File layout per agent:**
```
src/[service-name]/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   └── api/
└── scripts/
    └── migrate.py
```

---

## What Changed in v1.3 (2026-03-09)

- **Portfolio & Positions Schema** — 12-table foundation + portfolio layer designed
  and migration-ready (ADRs P01–P10)
- **Asset-Gem Amendments** — Chowder Number, 5yr avg yield, named entry signal
  flags, DCA schedule on proposals (Amendments A1–A4)
- **Foundation discovery** — `securities`, `features_historical`, `user_preferences`
  found missing from prod; created fresh in migration
- **FK strategy** — symbol TEXT PK throughout v1 (ADR-P09); UUID migration path
  documented for v2
- **Trigger flows** — 4 formal trigger patterns defined (Portfolio Review, Analyst
  Signal, Circuit Breaker, Portfolio Construction)
