# CHANGELOG — Agent 03: Income Scoring Service

All notable changes to the Income Scoring Service are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] — 2026-02-26

### Added
- `app/api/scores.py`: Inline quality gate fallback via `GateData` model in `ScoreRequest`
  - `POST /scores/evaluate` now accepts optional `gate_data` for one-step evaluation
  - Returns 422 with clear message if no gate record found and no gate_data provided
- `docker-compose.yml`: Agent 03 service entry with health checks and inter-service URLs
- `docker-compose.yml`: Agent 02 service entry with dependency on Agent 01 health

### Fixed
- Agent 01 local connectivity: `.env` with public DigitalOcean hostnames for local dev
- numpy 1.26.3 installed in platform venv for Monte Carlo simulations

---

## [1.0.0] — 2026-02-26

### Added — Phase 2: Scoring Engine

- `app/scoring/data_client.py`: Async httpx client for Agent 01 API
  - Methods: `get_fundamentals`, `get_dividend_history`, `get_history_stats`, `get_etf_data`, `get_current_price`
  - Graceful degradation: returns `{}` / `[]` on any error
- `app/scoring/income_scorer.py`: Weighted scoring engine
  - 3 pillars: Valuation & Yield (0–40), Financial Durability (0–40), Technical Entry (0–20)
  - 8 sub-components with 50% partial credit for missing data
  - Grade thresholds: A+(95+) A(85+) B+(75+) B(70+) C(60+) D(50+) F(<50)
  - Recommendations: AGGRESSIVE_BUY(≥85) ACCUMULATE(≥70) WATCH(<70)
- `app/scoring/nav_erosion.py`: Monte Carlo NAV erosion analysis
  - Configurable simulations via `settings.nav_erosion_simulations`
  - Risk tiers: LOW/MODERATE/HIGH/SEVERE → penalty 0/10/20/30
- `app/api/scores.py`: Replaced 501 stubs with live endpoints
  - `POST /scores/evaluate`
  - `GET /scores/`
  - `GET /scores/{ticker}`
- `tests/test_income_scorer.py`: 66 tests (sub-component boundaries, grades, null handling)
- `tests/test_nav_erosion.py`: 26 tests (risk tiers, determinism, configurable simulations)

### Added — Phase 1: Quality Gate Foundation

- `app/scoring/quality_gate.py`: Binary pass/fail gate engine
  - Asset classes: DIVIDEND_STOCK, COVERED_CALL_ETF, BOND
  - Capital preservation VETO — FAIL blocks scoring regardless of yield
  - INSUFFICIENT_DATA status for missing required fields
  - 24hr result caching via `valid_until` timestamp
- `app/api/quality_gate.py`: API router
  - `POST /quality-gate/evaluate` (single ticker)
  - `POST /quality-gate/batch` (up to 50 tickers)
- `app/api/health.py`: `GET /health` with DB connectivity check
- `app/api/scores.py`: Stub endpoints (501) — replaced in Phase 2
- `app/main.py`: FastAPI app with lifespan, CORS, timing middleware
- `app/config.py`: Settings with all scoring thresholds configurable
- `app/database.py`: SQLAlchemy engine with QueuePool, Agent 01 table verification
- `app/models.py`: ORM models — `ScoringRun`, `QualityGateResult`, `IncomeScore`
- `scripts/migrate.py`: Plain Python migration (no Alembic)
  - Tables: `platform_shared.scoring_runs`, `quality_gate_results`, `income_scores`
  - `--drop-first` flag for destructive reset
- `tests/test_quality_gate.py`: 42 tests (credit rating, dividend stock, covered call ETF, bond gates)
- `requirements.txt`: Phase 1 + Phase 2 dependencies
- `Dockerfile`: Python 3.13-slim, migration + uvicorn on port 8003

### Infrastructure
- Service port: 8003
- DB schema: `platform_shared` (shared with Agent 01, Agent 02)
- Run command: `PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8003`
- Migration: `PYTHONPATH=. python scripts/migrate.py`

---

## Test Coverage Summary

| Test File | Tests | Status |
|---|---|---|
| test_quality_gate.py | 42 | ✅ All passing |
| test_income_scorer.py | 66 | ✅ All passing |
| test_nav_erosion.py | 26 | ✅ All passing |
| **Total** | **134** | **✅ 134/134** |
