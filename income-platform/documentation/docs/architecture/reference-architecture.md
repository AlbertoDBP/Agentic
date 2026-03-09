# Reference Architecture — Income Fortress Platform

**Version:** 1.3.0
**Date:** 2026-03-09

---

## System Overview

The Income Fortress Platform is a 24-agent AI microservices system. Each agent runs
as an independent FastAPI service in Docker. Agents communicate via the shared
PostgreSQL database (`platform_shared` schema) and Valkey cache. No direct
agent-to-agent HTTP calls in v1 — all coordination through shared state.

**Core invariant:** Every output that drives action (score, proposal, alert) requires
`Asset × Position × Portfolio` as joint context. Agents never act on asset data alone.

---

## Infrastructure

```
legatoinvest.com (DigitalOcean, 2 vCPU / 4 GB RAM)
│
├── Nginx (reverse proxy, SSL termination)
│   └── routes /api/agent-XX/ → port 800X
│
├── Docker Compose
│   ├── agent-01  :8001  Market Data
│   ├── agent-02  :8002  Newsletter Ingestion
│   ├── agent-03  :8003  Income Scoring
│   ├── agent-04  :8004  Asset Classification
│   ├── agent-05  :8005  Tax Optimizer
│   └── [agents 06–24 pending]
│
├── Managed PostgreSQL (DigitalOcean)
│   └── schema: platform_shared
│       ├── Foundation:  securities, features_historical, user_preferences
│       ├── Asset:       nav_snapshots, income_scores, asset_classifications...
│       ├── Analyst:     analysts, analyst_articles, analyst_recommendations...
│       ├── Portfolio:   accounts, portfolios, portfolio_constraints
│       ├── Position:    positions, transactions, dividend_events
│       └── Metrics:     portfolio_income_metrics, portfolio_health_scores
│
└── Valkey Cache
    ├── Price data (TTL = health_score_ttl_hours, default 24h)
    ├── Income scores (same TTL)
    └── Health scores (same TTL, invalidated by Agent 01 refresh)
```

---

## Agent Interaction Model

Four trigger flows drive all agent activity:

### Flow 1: Portfolio Review (scheduled / user-initiated)
```
User / Scheduler
    → Agent 09 (Income Metrics rollup)
    → Agent 11 (Portfolio Health Score)
    → Agent 03 (rescore stale positions)
    → Agent 12 (proposals if thresholds breached)
    → User notification
```

### Flow 2: Analyst Signal
```
Agent 02 (newsletter ingestion)
    → extract ticker
    → Agent 03 (score ticker)
    → cross-reference portfolios holding ticker
    → Agent 12 (proposal if actionable)
    → User notification
```

### Flow 3: Circuit Breaker
```
Agent 01 (price/data event detected)
    → identify positions holding ticker
    → calculate portfolio weight severity
    → Agent 03 (rescore)
    → Agent 12 (alert / proposal)
    → User notification
```

### Flow 4: Portfolio Construction (Greenfield)
```
User (constraints only, no positions)
    → Agent 08 construction mode
    → PROPOSED positions on DRAFT portfolio
    → Agent 12 (ranked proposals)
    → User approval
    → positions.status PROPOSED → ACTIVE
    → portfolios.status DRAFT → ACTIVE
```

---

## Data Flow

```
External APIs
  Polygon.io ──────────────────────────────────────┐
  Financial Modeling Prep ─────────────────────────┤
  yfinance (fallback) ─────────────────────────────┤→ Agent 01 → platform_shared
  Finnhub (credit ratings) ────────────────────────┘
  APIDojo / Seeking Alpha ─────────────────────────→ Agent 02 → platform_shared
  SEC EDGAR (interest coverage proxy) ─────────────→ Agent 01

Scoring Pipeline
  platform_shared.securities ──────────────────────┐
  platform_shared.features_historical ─────────────┤→ Agent 03 → income_scores
  platform_shared.asset_classifications ───────────┘

Portfolio Pipeline
  platform_shared.positions ───────────────────────┐
  platform_shared.portfolios ──────────────────────┤→ Agent 09 → portfolio_income_metrics
  platform_shared.income_scores ───────────────────┘

Health Pipeline
  platform_shared.portfolio_income_metrics ────────┐
  platform_shared.positions ───────────────────────┤→ Agent 11 → portfolio_health_scores
  platform_shared.portfolio_constraints ───────────┘

Proposal Pipeline
  platform_shared.portfolio_health_scores ─────────┐
  platform_shared.analyst_recommendations ─────────┤→ Agent 12 → proposals (API response)
  platform_shared.positions ───────────────────────┘
```

---

## FK Conventions (v1)

Entity chain throughout the system:

```
platform_shared.securities (symbol TEXT PK)
         │
         │ FK: symbol TEXT
         ▼
platform_shared.positions (portfolio_id UUID FK, symbol TEXT FK)
         │
         │ FK: portfolio_id UUID
         ▼
platform_shared.portfolios (id UUID PK)
```

All agent payload contracts use `symbol: str` (not UUID). See ADR-P09 for v2
UUID migration path.

---

## Non-Functional Requirements

| Concern | Requirement |
|---------|-------------|
| Availability | Each agent independently deployable; failure of one does not cascade |
| Latency | Score endpoint ≤ 2s p95; portfolio health ≤ 5s p95 |
| Data freshness | Price + health TTL user-configurable (default 24h) |
| Safety | 70% safety threshold with veto over yield-chasing |
| Capital preservation | Hard gates on NAV erosion, credit quality, payout ratio |
| User control | All proposals require explicit user approval before execution |
| Auditability | All scoring runs logged; all proposals persisted with FK context |
