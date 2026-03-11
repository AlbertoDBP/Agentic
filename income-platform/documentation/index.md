# Income Fortress Platform — Master Index

**Version:** 1.4.0
**Last Updated:** 2026-03-11
**Repository:** `AlbertoDBP/Agentic` → `income-platform/`
**Production:** `legatoinvest.com` | `138.197.78.238`

---

## Platform Overview

The Income Fortress Platform is a production-grade, tax-efficient income investment
platform built on a multi-agent microservices architecture. Core principles:

- **Capital Safety First** — 70% quality threshold with VETO power
- **Income over Growth** — yield sustainability and consistency prioritized
- **Yield Trap Avoidance** — NAV erosion detection, Chowder signal, quality gates
- **Proposal-Based Workflow** — platform never auto-executes; always proposes
- **Tax Efficiency** — parallel output, never a blocking gate

---

## Deployed Agents (6 of 24)

| Agent | Service Name | Port | Status | Version |
|-------|-------------|------|--------|---------|
| 01 | Market Data Service | 8001 | ✅ Deployed | v1.1.0 |
| 02 | Newsletter Ingestion | 8002 | ✅ Deployed | v1.0.0 |
| 03 | Income Scoring | 8003 | ✅ Deployed | v1.1.0 |
| 04 | Asset Classification | 8004 | ✅ Deployed | v1.0.0 |
| 05 | Tax Optimization | 8005 | ✅ Deployed | v1.0.0 |
| 06 | Scenario Simulation | 8006 | ✅ Deployed | v1.0.0 |

---

## Agent Descriptions

### Agent 01 — Market Data Service (port 8001)
Multi-provider market data hub. Fetches price, dividends, fundamentals, ETF
holdings, and credit ratings. Writes to `platform_shared.securities` and
`platform_shared.features_historical` via `/sync` endpoint.

**Providers:** Polygon.io (price), FMP (fundamentals/dividends), yfinance (ETF
holdings fallback), Finnhub (credit ratings)
**Key endpoint:** `POST /stocks/{symbol}/sync`

---

### Agent 02 — Newsletter Ingestion Service (port 8002)
"The Dividend Detective" — ingests Seeking Alpha articles via APIDojo, extracts
income signals using Claude Haiku, implements S-curve staleness decay and
SHA-256 deduplication.

**Key capability:** Analyst signal extraction → `platform_shared.analyst_articles`

---

### Agent 03 — Income Scoring Service (port 8003)
Quality gate + weighted scoring engine. Capital safety first — a 70% threshold
with VETO power. Includes NAV erosion Monte Carlo for covered call ETFs.

**Score weights:** Valuation/Yield 40%, Financial Durability 35%, Technical 25%
**Chowder Number:** Computed from `features_historical`, 0% weight, informational
**Key endpoint:** `POST /scores/evaluate`

---

### Agent 04 — Asset Classification Service (port 8004)
Classifies securities into 7 asset classes using rule-based detection. Shared
utility available at `src/shared/asset_class_detector/` for direct import.

**Asset classes:** DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT,
MORTGAGE_REIT, BDC, PREFERRED_STOCK

---

### Agent 05 — Tax Optimization Service (port 8005)
Read-only tax analysis covering 2024 IRS brackets (4 filing statuses), 51 state
tax rates, NIIT, Section 1256 60/40 treatment, asset-class-specific logic.
Tax efficiency = parallel output only — 0% score weight.

**Key capability:** Tax harvesting proposals (never executes trades)

---

### Agent 06 — Scenario Simulation Service (port 8006)
Portfolio stress testing and income projection. Asset-class shock tables across
5 predefined scenarios. Monte Carlo P10/P50/P90 income projection. Custom
scenario support for NL/LLM-driven what-if analysis.

**Scenarios:** RATE_HIKE_200BPS, MARKET_CORRECTION_20, RECESSION_MILD,
INFLATION_SPIKE, CREDIT_STRESS, CUSTOM
**Key endpoint:** `POST /scenarios/stress-test`

---

## Agents Roadmap (7–24)

| Agent | Name | Description | Priority |
|-------|------|-------------|----------|
| 07 | Opportunity Scanner | Screens universe for new income candidates | P1 |
| 08 | Rebalancing | Portfolio optimization proposals | P1 |
| 09 | Income Projection | Forward 12-month income forecast (position-level) | P1 |
| 10 | NAV Monitor | ETF NAV erosion tracking over time | P1 |
| 11 | Alert Classification | Smart alert generation and prioritization | P2 |
| 12 | Proposal Agent | Synthesizes all agent outputs into actionable proposals | P0 |
| 13–24 | TBD | Additional agents per platform roadmap | P2–P3 |

**Agent 12 is a priority gate** — all agents 07–11 feed into Agent 12.
ADR-P11 (Chowder thresholds) and ADR-P12 (GLM model) both require review
before Agent 12 DESIGN.

---

## Data Flow Overview

```
External Data                Platform Agents              Storage
─────────────                ───────────────              ───────
Polygon.io ──┐               
FMP ─────────┤──→ Agent 01 ──→ securities
Finnhub ─────┘    (Market     features_historical
yfinance ─────    Data)
                              
Seeking Alpha ──→ Agent 02 ──→ analyst_articles
(APIDojo)         (Newsletter)  analyst_recommendations

                  Agent 04 ──→ asset_classifications
                  (Classifier)

Agent 01 ───────→ Agent 03 ──→ income_scores
Agent 04 ───────→ (Scorer)     quality_gate_results

Agent 03 ───────→ Agent 05     [read-only, no writes]
Agent 04 ───────→ (Tax)

platform_shared → Agent 06 ──→ scenario_results (on save)
                  (Simulation)

[All agents] ───→ Agent 12 ──→ proposals  [PLANNED]
                  (Proposal)
```

---

## Infrastructure

| Component | Detail |
|-----------|--------|
| Server | DigitalOcean Ubuntu droplet, 2 vCPU / 4GB RAM |
| IP | 138.197.78.238 |
| Domain | legatoinvest.com |
| Database | DigitalOcean managed PostgreSQL (`platform_shared` schema) |
| Cache | Valkey (Redis-compatible) |
| Reverse Proxy | Nginx + SSL |
| Container Runtime | Docker + docker-compose |
| CI | GitHub Actions |

### DB Users
- `doadmin` — container runtime user (private network URL)
- `dbpmanager` — migration user (public URL, used from Mac)

---

## Nginx Route Map

| Agent | Nginx Prefix |
|-------|-------------|
| Agent 01 | `/api/market-data/` |
| Agent 02 | `/api/newsletter/` |
| Agent 03 | `/api/nav-erosion/` |
| Agent 04 | `/api/asset-classification/` |
| Agent 05 | `/api/tax-optimization/` |
| Agent 06 | `/api/scenario-simulation/` |

---

## Documentation Index

### Functional Specifications
- [Agent 01 — Market Data](functional/agent-01-market-data.md)
- [Agent 03 — Income Scoring](functional/agent-03-income-scoring.md)
- [Agent 06 — Scenario Simulation](functional/agent-06-scenario-simulation.md)

### Implementation Specifications
- [Agent 01 — Implementation](implementation/agent-01-impl.md)
- [Agent 03 — Implementation](implementation/agent-03-impl.md)
- [Agent 06 — Implementation](implementation/agent-06-impl.md)

### Architecture Diagrams
- [System Diagram](diagrams/system-diagram.mmd)
- [Agent 01 Provider Flow](diagrams/agent-01-provider-flow.mmd)
- [Agent 06 Architecture](diagrams/agent-06-architecture.mmd)
- [Portfolio ERD](diagrams/portfolio-erd.mmd)

### Decision Records
- [Decisions Log — ADRs P01–P10](decisions/decisions-log.md)
- [ADR-P11 — Chowder Threshold Management](decisions/adr-p11-chowder-thresholds.md)
- [ADR-P12 — Scenario Simulation Model](decisions/adr-p12-scenario-model.md)

### Changelogs
- [Agent 01 Changelog](CHANGELOG-agent-01.md)
- [Agent 03 Changelog](CHANGELOG-agent-03.md)
- [Agent 06 Changelog](CHANGELOG-agent-06.md)
- [Platform Changelog](CHANGELOG.md)

### Roadmap
- [Platform Roadmap v2](roadmap-v2.md)
