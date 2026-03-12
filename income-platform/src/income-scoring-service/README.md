# Income Scoring Service — Agent 03

Scores income-generating assets (dividend stocks, covered call ETFs, bonds) using a two-phase quality gate + weighted scoring engine. Capital preservation first via 70% VETO threshold on fundamentals.

## Overview

Agent 03 is the platform's decision engine. It evaluates income assets through a binary quality gate (Phase 1: capital safety VETO—fails here = never scores) and a weighted scoring pipeline (Phase 2: 0–100 total score). Covered call ETFs receive Monte Carlo NAV erosion analysis. The Chowder Number signal (specific to covered call ETFs) combines yield, FCF growth, and price appreciation. All scores are persisted with 30 factors and data quality metrics for explainability.

Called by Agent 05 (tax), Agent 06 (scenarios), and the Proposal Agent (Agent 12).

## Port & Health Check

- **Port:** 8003
- **Health:** `GET /health` — checks database connectivity + asyncpg pool
- **Docs:** `GET /docs` (OpenAPI/Swagger UI)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + database + asyncpg pool status |
| POST | `/quality-gate/evaluate` | Single ticker gate evaluation (capital safety VETO) |
| POST | `/quality-gate/batch` | Batch gate evaluation (max 50 tickers) |
| POST | `/scores/evaluate` | Full scoring pipeline: gate → scoring → persist |
| GET | `/scores/` | Last 20 scores (optional ?recommendation= filter) |
| GET | `/scores/{ticker}` | Latest score for a ticker |

## Dependencies

**Upstream services:**
- Agent 01 (port 8001) — fundamentals, price history, dividends, ETF holdings, credit ratings
- Agent 02 (port 8002, optional) — analyst signals for consensus weighting

**External dependencies:**
- PostgreSQL (schema: `platform_shared`) — scoring_runs, quality_gate_results, income_scores tables
- Redis/Valkey — caching scores (1h) & quality gate results (24h)
- Financial Modeling Prep — supplementary fundamental metrics

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection (schema: platform_shared) |
| REDIS_URL | Yes | Redis/Valkey URL for scoring cache |
| MARKET_DATA_SERVICE_URL | No | Default: http://localhost:8001 |
| NEWSLETTER_SERVICE_URL | No | Default: http://localhost:8002 |
| FMP_API_KEY | Yes | Financial Modeling Prep API key |
| JWT_SECRET | Yes | Shared JWT signing secret |
| SERVICE_PORT | No | Default: 8003 |
| LOG_LEVEL | No | Default: INFO |
| NAV_EROSION_SIMULATIONS | No | Default: 10000 (Monte Carlo paths) |
| SCORE_HISTORY_DAYS | No | Default: 90 (lookback for technical scoring) |
| MIN_CREDIT_RATING | No | Default: BBB- (investment grade floor) |

## Running Locally

```bash
cd src/income-scoring-service

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://user:pass@localhost/income_platform"
export REDIS_URL="redis://localhost:6379"
export MARKET_DATA_SERVICE_URL="http://localhost:8001"
export FMP_API_KEY="your_key"
export JWT_SECRET="dev-secret"

# Run service
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

## Running Tests

```bash
cd src/income-scoring-service
PYTHONPATH=. pytest tests/ -v
# Test coverage: 134 total tests
#   - test_quality_gate.py: 42 tests
#   - test_income_scorer.py: 66 tests
#   - test_nav_erosion.py: 26 tests
```

## Project Structure

```
income-scoring-service/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Settings: gate thresholds, weights, scoring params
│   ├── auth.py                 # JWT verification
│   ├── database.py             # SQLAlchemy engine + session factory
│   ├── models.py               # ORM: ScoringRun, QualityGateResult, IncomeScore
│   ├── api/
│   │   ├── health.py           # GET /health
│   │   ├── quality_gate.py     # POST /quality-gate/{evaluate,batch}
│   │   └── scores.py           # POST /scores/evaluate, GET /scores/
│   └── scoring/
│       ├── quality_gate.py     # QualityGateEngine: VETO rules by asset class
│       ├── income_scorer.py    # IncomeScorer: 8 sub-components + weighting
│       ├── nav_erosion.py      # NAVErosionAnalyzer: Monte Carlo for covered calls
│       └── data_client.py      # MarketDataClient: Agent 01 HTTP client
├── scripts/
│   └── migrate.py              # Plain Python DB migration
├── requirements.txt
├── Dockerfile
└── tests/
    ├── conftest.py
    ├── test_quality_gate.py    # 42 tests: gate logic by asset class
    ├── test_income_scorer.py   # 66 tests: scoring components
    └── test_nav_erosion.py     # 26 tests: Monte Carlo analysis
```

## Key Design Decisions

- **Two-Phase Pipeline:** Quality gate (binary VETO) separates capital safety from opportunity scoring. A 70% threshold on fundamentals means 30% of fundamentals must be questionable to fail—strict but not impossible. Once past the gate, a separate engine applies 3-pillar scoring (valuation/yield 40%, financial durability 40%, technical entry 20%).
- **Monte Carlo NAV Erosion (Covered Calls Only):** Simulates 10,000 paths of underlying price movement with call options. Estimates probability of NAV erosion under stress. Penalty is scaled: 0–30 points deducted based on probability tier. This captures a unique risk in covered-call ETFs.
- **Chowder Number for Covered Calls:** (Yield + Dividend Growth % + Price Appreciation %) replaces raw yield in covered call scoring. Balances dividend with capital appreciation—the whole income thesis.
- **Data Quality Transparency:** Returns `data_completeness_pct` (0–100%) and `data_quality_score` (0–100) alongside each score. This enables downstream agents to weight scores by data maturity and flag when API failures degrade analysis.
