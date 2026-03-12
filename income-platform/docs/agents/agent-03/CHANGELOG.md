# CHANGELOG — Agent 03: Income Scoring Service

All notable changes to the Income Scoring Service are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] — 2026-03-12

### Phase 0 — DB Foundation & Dynamic Weights

**Added**
- `app/scoring/weight_profile_loader.py`: Per-asset-class weight profile loading with in-process cache
  - Loads active weight profile for each of 7 asset classes
  - Default seed profiles for MORTGAGE_REIT (30/45/25), BDC (35/40/25), COVERED_CALL_ETF (40/30/30), EQUITY_REIT (30/40/30), DIVIDEND_STOCK (25/45/30), BOND (35/50/15), PREFERRED_STOCK (40/45/15)
- New ORM tables in `platform_shared` schema:
  - `scoring_weight_profiles`: id, asset_class, version, is_active, weight_yield, weight_durability, weight_technical, yield_sub_weights, durability_sub_weights, technical_sub_weights, source, created_at
  - `weight_change_audit`: id, profile_id, change_reason, created_by, created_at
- New API endpoints:
  - `GET /weights/`: List all weight profiles (filterable by asset_class, active_only)
  - `GET /weights/{asset_class}`: Return active profile for asset class
  - `POST /weights/{asset_class}`: Create new profile (supersedes current active)
- `app/api/weights.py`: API router for weight profile endpoints

**Changed**
- `app/scoring/income_scorer.py`: IncomeScorer now accepts optional `weight_profile` dict parameter
  - Ceilings computed from profile weights instead of hardcoded universals
  - If no profile provided, uses active profile from loader cache
- `app/api/scores.py`: POST /scores/evaluate accepts and passes weight_profile; response includes weight_profile_version and weight_profile_id
- `tests/test_weight_profiles.py`: 27 new tests covering profile CRUD, auth, 404 for unknown classes, response shape

---

### Phase 2 — Signal Penalty Layer

**Added**
- `app/scoring/newsletter_client.py`: Async Agent 02 signal fetcher
  - `get_signal(ticker)` — calls `GET /signal/{ticker}` on Agent 02 service
  - Handles 404, timeout, and error responses gracefully
  - Disabled via `NEWSLETTER_SERVICE_URL=null` env var
- `app/scoring/signal_penalty.py`: SignalPenaltyEngine
  - Penalty thresholds: BEARISH_STRONG = 8.0, BEARISH_MODERATE = 5.0, BEARISH_WEAK = 2.0
  - Architecture constraint: bullish signals NEVER inflate score (cap = 0.0)
  - Eligibility gates: checks min_n_analysts, min_decay_weight, consensus thresholds
  - Score floor: penalty cannot reduce score below 0.0
- New ORM tables in `platform_shared` schema:
  - `signal_penalty_config`: id, version, is_active, bearish_strong_penalty, bearish_moderate_penalty, bearish_weak_penalty, bullish_strong_bonus_cap (always 0.0), min_n_analysts, min_decay_weight, consensus_bearish_threshold, consensus_bullish_threshold, created_at
  - `signal_penalty_log`: id, income_score_id, signal_type, signal_strength, consensus_score, penalty_applied, created_at
- New API endpoints:
  - `GET /signal-config/`: Return active signal penalty configuration
- `app/api/signal_config.py`: API router for signal config endpoint
- `scores.py` step 5b: Apply signal penalty; step 6b: Write audit log
- `tests/test_signal_penalty.py`: 60 tests covering engine boundaries, newsletter client scenarios (disabled/200/404/timeout/error), signal config API, evaluate endpoint with penalty

**Changed**
- `app/models.py`: IncomeScore table now has signal_penalty (float) and signal_penalty_details (JSON) columns
- `app/api/scores.py`: POST /scores/evaluate response includes signal_penalty and signal_penalty_details

---

### Phase 3 — Learning Loop

**Added**
- `app/scoring/shadow_portfolio.py`: ShadowPortfolioManager
  - Records AGGRESSIVE_BUY and ACCUMULATE recommendations with entry price, date, asset class
  - Populates outcome labels (CORRECT/INCORRECT/NEUTRAL) after 90-day hold period
  - CORRECT: actual return >= +5%, INCORRECT: return <= -5%, NEUTRAL: in between
  - Error handling: skips entries with no entry_price or missing exit data
- `app/scoring/weight_tuner.py`: QuarterlyWeightTuner
  - Analyzes CORRECT vs INCORRECT outcomes
  - Computes normalized pillar fraction signals from outcome data
  - Proposes weight adjustments (±5 percentage point max per pillar)
  - Enforces weight sum = 100 invariant and per-pillar floor/ceiling constraints
  - Skips review if fewer than 10 usable outcomes or signal too weak
- New ORM tables in `platform_shared` schema:
  - `shadow_portfolio_entries`: id, ticker, asset_class, entry_score, entry_grade, entry_recommendation, entry_price, entry_date, hold_period_days, exit_price, exit_date, actual_return_pct, outcome_label, outcome_populated_at, created_at
  - `weight_review_runs`: id, asset_class, status, outcomes_analyzed, correct_count, incorrect_count, weight_before, weight_after, delta_yield, delta_durability, delta_technical, skip_reason, created_at
- New API endpoints:
  - `GET /learning-loop/shadow-portfolio/`: List entries (filterable by asset_class, outcome, limit)
  - `POST /learning-loop/populate-outcomes`: Batch populate outcomes {exit_prices: {ticker: price}}
  - `POST /learning-loop/review/{asset_class}`: Trigger quarterly weight review, returns WeightReviewRun
  - `GET /learning-loop/reviews`: List review run history
- `app/api/learning_loop.py`: API router for all learning loop endpoints
- `tests/test_learning_loop.py`: 74 tests covering ShadowPortfolioManager (record entry, skip non-qualifying, populate outcomes, CORRECT/INCORRECT/NEUTRAL labels, error handling), QuarterlyWeightTuner (insufficient samples, no signal, compute adjustment), API endpoints (shadow portfolio list, populate outcomes, review trigger, review history)

**Changed**
- `app/api/scores.py`: POST /scores/evaluate logs shadow portfolio entry for AGGRESSIVE_BUY and ACCUMULATE recommendations

---

### Phase 4 — Detector Confidence Learning

**Added**
- `app/scoring/classification_feedback.py`: ClassificationFeedbackTracker
  - Records how asset_class was determined per scoring call (AGENT04 auto-classify vs MANUAL_OVERRIDE)
  - Detects mismatch when Agent 04 auto-classification disagrees with manual override
  - Mismatch detection only active when `CLASSIFICATION_VERIFY_OVERRIDES=True`
  - Computes monthly accuracy rollup (total_calls, agent04_trusted, manual_overrides, mismatches, accuracy_rate)
- New ORM tables in `platform_shared` schema:
  - `classification_feedback`: id, ticker, asset_class_used, source (AGENT04 | MANUAL_OVERRIDE), agent04_class, agent04_confidence, is_mismatch, captured_at, income_score_id, created_at
  - `classifier_accuracy_runs`: id, period_month, asset_class (nullable), total_calls, agent04_trusted, manual_overrides, mismatches, accuracy_rate, override_rate, mismatch_rate, computed_at, computed_by
- New API endpoints:
  - `GET /classification-accuracy/feedback`: List recent feedback entries (filterable by ticker, source, limit)
  - `GET /classification-accuracy/runs`: List monthly accuracy rollup runs
  - `POST /classification-accuracy/rollup`: Trigger monthly rollup for calendar month {period_month: "YYYY-MM"}
- `app/api/classification_accuracy.py`: API router for classification accuracy endpoints
- `tests/test_classification_accuracy.py`: 47 tests covering ClassificationFeedbackTracker (record AGENT04/MANUAL, mismatch detection, monthly rollup accuracy, rollup with no data), Classification Accuracy API (feedback list, runs list, rollup trigger, auth guard)

**Changed**
- `app/api/scores.py`: POST /scores/evaluate logs classification feedback entry (source=AGENT04 or MANUAL_OVERRIDE, with mismatch detection)
- `app/config.py`: New config var `classification_verify_overrides` (bool, default False)

---

### Infrastructure
- Service version: 2.0.0
- DB schema: `platform_shared` (now contains 11 tables: 3 from v1.0 + 2 from Phase 0 + 2 from Phase 2 + 2 from Phase 3 + 2 from Phase 4)
- Migration: `scripts/migrate.py` creates all 11 tables
- Test count: 438 tests (all passing)

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
| test_chowder.py | 14 | ✅ All passing |
| test_weight_profiles.py | 27 | ✅ All passing |
| test_dynamic_weights.py | 47 | ✅ All passing |
| test_signal_penalty.py | 60 | ✅ All passing |
| test_learning_loop.py | 74 | ✅ All passing |
| test_classification_accuracy.py | 47 | ✅ All passing |
| **Total** | **438** | **✅ 438/438** |
