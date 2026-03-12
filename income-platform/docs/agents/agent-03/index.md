# Agent 03 — Income Scoring Service: Documentation Index

**Version:** 2.0.0 | **Date:** 2026-03-12 | **Status:** Production | **Port:** 8003

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
| [Test Matrix](testing/test-matrix.md) | 438 tests, coverage map, edge cases, run commands |
| [Decisions Log](decisions/decisions-log.md) | 7 ADRs — architecture decisions with rationale |
| [CHANGELOG](CHANGELOG.md) | Version history — Phase 0–4, v2.0 Adaptive Intelligence |

---

## Service Overview

Agent 03 evaluates income-generating assets through a six-phase pipeline:

**Phase 1 — Quality Gate (Capital Preservation VETO)**
A ticker that fails the quality gate is permanently blocked from scoring, regardless of yield attractiveness. This enforces the platform's core principle: capital safety first.

**Phase 2 — Scoring Engine (0–100)**
Tickers that pass the gate are scored across three pillars using live market data from Agent 01. Covered call ETFs receive an additional Monte Carlo NAV erosion penalty.

**Phase 3 — Dynamic Weight Profiles (v2.0)**
Each of 7 asset classes has its own weight profile (e.g., MORTGAGE_REIT: yield 30%, durability 45%, technical 25%). Profiles are stored in the database and can be updated quarterly without redeployment. POST /scores/evaluate applies the active profile for the ticker's asset class.

**Phase 4 — Signal Penalty Layer (v2.0)**
Agent 02 newsletter signals feed into a penalty engine. BEARISH signals (strong/moderate/weak) reduce score by 8/5/2 points respectively. This is a deliberate capital preservation constraint: bullish signals NEVER inflate scores. Architecture note: signals can only reduce, never inflate.

**Phase 5 — Learning Loop (v2.0)**
AGGRESSIVE_BUY and ACCUMULATE recommendations are tracked in shadow portfolio. After 90-day holding period, outcomes are populated (CORRECT: +5% return, INCORRECT: -5% return, NEUTRAL: in between). Quarterly weight reviews analyze which sub-components predicted actual income sustainability, proposing bounded adjustments (±5 percentage points max).

**Phase 6 — Detector Confidence Learning (v2.0)**
Every scoring call logs classification feedback (asset_class used, whether from auto-classification or manual override, and any mismatch detected). Monthly rollups compute accuracy metrics, informing confidence in Asset Classification service (Agent 04).

---

## File Structure

```
src/income-scoring-service/
├── app/
│   ├── __init__.py
│   ├── config.py              ← all thresholds configurable
│   ├── database.py            ← SQLAlchemy QueuePool
│   ├── main.py                ← FastAPI app, lifespan, middleware
│   ├── models.py              ← ScoringRun, QualityGateResult, IncomeScore, etc.
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py          ← GET /health
│   │   ├── quality_gate.py    ← POST /quality-gate/evaluate, /batch
│   │   ├── scores.py          ← POST /scores/evaluate, GET /scores/
│   │   ├── weights.py         ← GET/POST /weights/* (v2.0)
│   │   ├── signal_config.py   ← GET /signal-config/ (v2.0)
│   │   ├── learning_loop.py   ← /learning-loop/* endpoints (v2.0)
│   │   └── classification_accuracy.py ← /classification-accuracy/* endpoints (v2.0)
│   └── scoring/
│       ├── __init__.py
│       ├── quality_gate.py    ← QualityGateEngine (business logic)
│       ├── data_client.py     ← Agent 01 HTTP client
│       ├── income_scorer.py   ← IncomeScorer (8 sub-components, dynamic weights)
│       ├── nav_erosion.py     ← NAVErosionAnalyzer (Monte Carlo)
│       ├── weight_profile_loader.py ← Per-class weight profile cache (v2.0)
│       ├── newsletter_client.py ← Agent 02 signal fetcher (v2.0)
│       ├── signal_penalty.py  ← SignalPenaltyEngine (v2.0)
│       ├── shadow_portfolio.py ← ShadowPortfolioManager (v2.0)
│       ├── weight_tuner.py    ← QuarterlyWeightTuner (v2.0)
│       └── classification_feedback.py ← ClassificationFeedbackTracker (v2.0)
├── scripts/
│   └── migrate.py             ← plain Python migration
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_quality_gate.py   ← 42 tests
│   ├── test_income_scorer.py  ← 66 tests
│   ├── test_nav_erosion.py    ← 26 tests
│   ├── test_chowder.py        ← 14 tests (v2.0)
│   ├── test_weight_profiles.py ← 27 tests (v2.0)
│   ├── test_dynamic_weights.py ← 47 tests (v2.0)
│   ├── test_signal_penalty.py ← 60 tests (v2.0)
│   ├── test_learning_loop.py  ← 74 tests (v2.0)
│   └── test_classification_accuracy.py ← 47 tests (v2.0)
├── .env
├── .env.example
├── Dockerfile
└── requirements.txt
```

---

## API Endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/health` | Service health + DB connectivity | Not required |
| POST | `/quality-gate/evaluate` | Single ticker gate evaluation | Required |
| POST | `/quality-gate/batch` | Batch gate evaluation (max 50) | Required |
| POST | `/scores/evaluate` | Full scoring pipeline | Required |
| GET | `/scores/` | Last 20 scores (filterable) | Required |
| GET | `/scores/{ticker}` | Latest score for ticker | Required |
| GET | `/weights/` | List weight profiles (v2.0) | Required |
| GET | `/weights/{asset_class}` | Active profile for asset class (v2.0) | Required |
| POST | `/weights/{asset_class}` | Create new weight profile (v2.0) | Required |
| GET | `/signal-config/` | Active signal penalty configuration (v2.0) | Required |
| GET | `/learning-loop/shadow-portfolio/` | List shadow portfolio entries (v2.0) | Required |
| POST | `/learning-loop/populate-outcomes` | Batch populate entry outcomes (v2.0) | Required |
| POST | `/learning-loop/review/{asset_class}` | Trigger quarterly weight review (v2.0) | Required |
| GET | `/learning-loop/reviews` | List review run history (v2.0) | Required |
| GET | `/classification-accuracy/feedback` | List classification feedback (v2.0) | Required |
| GET | `/classification-accuracy/runs` | List monthly accuracy rollups (v2.0) | Required |
| POST | `/classification-accuracy/rollup` | Trigger monthly rollup (v2.0) | Required |

---

## Integration with Platform

```
Agent 02 (port 8002) ──► Agent 03 Signal Penalty Layer
Newsletter Signals        GET /signal/{ticker}
                         BEARISH → -2/-5/-8 pts
                         BULLISH → never inflates (cap=0.0)

Agent 04 (port 8004) ──► Agent 03 Classification Feedback
Asset Classification      auto-classify or manual override tracked

Agent 01 (port 8001) ──► Agent 03 (port 8003) ──► PostgreSQL
Market Data              Income Scoring           platform_shared schema
  /fundamentals            /quality-gate/evaluate   11 tables:
  /dividends               /scores/evaluate           • scoring_runs
  /history/stats           /weights/*                 • quality_gate_results
  /etf                     /signal-config/            • income_scores
  /price                   /learning-loop/*           • scoring_weight_profiles
                           /classification-accuracy/*  • weight_change_audit
                                                      • signal_penalty_config
                                                      • signal_penalty_log
                                                      • shadow_portfolio_entries
                                                      • weight_review_runs
                                                      • classification_feedback
                                                      • classifier_accuracy_runs
```

---

## Test Coverage

| File | Tests | Status |
|---|---|---|
| test_quality_gate.py | 42 | ✅ |
| test_income_scorer.py | 66 | ✅ |
| test_nav_erosion.py | 26 | ✅ |
| test_chowder.py | 14 | ✅ |
| test_weight_profiles.py | 27 | ✅ |
| test_dynamic_weights.py | 47 | ✅ |
| test_signal_penalty.py | 60 | ✅ |
| test_learning_loop.py | 74 | ✅ |
| test_classification_accuracy.py | 47 | ✅ |
| **Total** | **438** | **✅ All passing** |

---

## Known Limitations & Future Roadmap

| Item | Status | Phase |
|---|---|---|
| Credit rating via user input (not API) | Accepted limitation | — |
| Rule-based scoring (no ML) | Deferred | v3.0 |
| XGBoost model | Deferred | v3.0 |
| SHAP explainability | Deferred | v3.0 |
| ML asset classification | Deferred | v3.0 |
| Redis required for full performance | Degraded locally | Infrastructure |
| Multi-tenant execution isolation | Deferred | v3.1 |

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
CLASSIFICATION_VERIFY_OVERRIDES=False
NAV_EROSION_SIMULATIONS=10000
SCORE_HISTORY_DAYS=90
LOG_LEVEL=INFO
ENVIRONMENT=development
```

**New in v2.0:**
- `NEWSLETTER_SERVICE_URL`: Agent 02 service URL; set to null to disable signal penalties
- `CLASSIFICATION_VERIFY_OVERRIDES`: When True, calls Agent 04 even for manual overrides to detect mismatches
