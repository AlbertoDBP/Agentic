# Agent 03 — Income Scoring Service: Documentation Index

**Version:** 1.1.0 | **Date:** 2026-02-26 | **Status:** Production | **Port:** 8003

---

## Quick Reference

```bash
# Start service
cd income-platform/src/income-scoring-service
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload

# Run migration (first time only)
PYTHONPATH=. python scripts/migrate.py

# Run tests
PYTHONPATH=. python -m pytest tests/ -v

# Health check
curl http://localhost:8003/health
```

---

## Documentation Map

| Document | Description |
|---|---|
| [Reference Architecture](architecture/reference-architecture.md) | System overview, component diagrams, data model, deployment |
| [Quality Gate Spec](functional/quality-gate.md) | Phase 1 binary VETO gate — asset class rules, interfaces |
| [Scoring Engine Spec](functional/scoring-engine.md) | Phase 2 weighted scoring — pillars, sub-components, NAV erosion |
| [Test Matrix](testing/test-matrix.md) | 134 tests, coverage map, edge cases, run commands |
| [Decisions Log](decisions/decisions-log.md) | 7 ADRs — architecture decisions with rationale |
| [CHANGELOG](CHANGELOG.md) | Version history — Phase 1, Phase 2, review fixes |

---

## Service Overview

Agent 03 evaluates income-generating assets through a two-phase pipeline:

**Phase 1 — Quality Gate (Capital Preservation VETO)**
A ticker that fails the quality gate is permanently blocked from scoring, regardless of yield attractiveness. This enforces the platform's core principle: capital safety first.

**Phase 2 — Scoring Engine (0–100)**
Tickers that pass the gate are scored across three pillars using live market data from Agent 01. Covered call ETFs receive an additional Monte Carlo NAV erosion penalty.

---

## File Structure

```
src/income-scoring-service/
├── app/
│   ├── __init__.py
│   ├── config.py              ← all thresholds configurable
│   ├── database.py            ← SQLAlchemy QueuePool
│   ├── main.py                ← FastAPI app, lifespan, middleware
│   ├── models.py              ← ScoringRun, QualityGateResult, IncomeScore
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py          ← GET /health
│   │   ├── quality_gate.py    ← POST /quality-gate/evaluate, /batch
│   │   └── scores.py         ← POST /scores/evaluate, GET /scores/
│   └── scoring/
│       ├── __init__.py
│       ├── quality_gate.py    ← QualityGateEngine (business logic)
│       ├── data_client.py     ← Agent 01 HTTP client
│       ├── income_scorer.py   ← IncomeScorer (8 sub-components)
│       └── nav_erosion.py     ← NAVErosionAnalyzer (Monte Carlo)
├── scripts/
│   └── migrate.py             ← plain Python migration
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_quality_gate.py   ← 42 tests
│   ├── test_income_scorer.py  ← 66 tests
│   └── test_nav_erosion.py    ← 26 tests
├── .env
├── .env.example
├── Dockerfile
└── requirements.txt
```

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health + DB connectivity |
| POST | `/quality-gate/evaluate` | Single ticker gate evaluation |
| POST | `/quality-gate/batch` | Batch gate evaluation (max 50) |
| POST | `/scores/evaluate` | Full scoring pipeline |
| GET | `/scores/` | Last 20 scores (filterable) |
| GET | `/scores/{ticker}` | Latest score for ticker |

---

## Integration with Platform

```
Agent 01 (port 8001) ──► Agent 03 (port 8003) ──► PostgreSQL
Market Data              Income Scoring           platform_shared schema
  /fundamentals            /quality-gate/evaluate   scoring_runs
  /dividends               /scores/evaluate         quality_gate_results
  /history/stats                                    income_scores
  /etf
  /price
```

---

## Test Coverage

| File | Tests | Status |
|---|---|---|
| test_quality_gate.py | 42 | ✅ |
| test_income_scorer.py | 66 | ✅ |
| test_nav_erosion.py | 26 | ✅ |
| **Total** | **134** | **✅ All passing** |

---

## Known Limitations & Phase 3 Roadmap

| Item | Status | Phase |
|---|---|---|
| Credit rating via user input (not API) | Accepted limitation | — |
| Rule-based scoring (no ML) | Deferred | Phase 3 |
| XGBoost model | Deferred | Phase 3 |
| SHAP explainability | Deferred | Phase 3 |
| Learning loop / shadow portfolio | Deferred | Phase 3 |
| Redis required for full performance | Degraded locally | Infrastructure |

---

## Environment Variables

```bash
SERVICE_NAME=agent-03-income-scoring
SERVICE_PORT=8003
DATABASE_URL=postgresql+psycopg2://...?sslmode=require
REDIS_URL=rediss://...
FMP_API_KEY=...
MARKET_DATA_SERVICE_URL=http://localhost:8001
NEWSLETTER_SERVICE_URL=http://localhost:8002
NAV_EROSION_SIMULATIONS=10000
SCORE_HISTORY_DAYS=90
LOG_LEVEL=INFO
ENVIRONMENT=development
```
