# Income Fortress Platform — Product Roadmap

**Document:** ROADMAP.md
**Location:** `income-platform/docs/ROADMAP.md`
**Last Updated:** 2026-03-12
**Owner:** Platform Architecture

---

## Versioning Philosophy

Each version groups related enhancements that form a coherent capability upgrade. Phases documented inside individual agent specs are consolidated here so they can be sequenced across releases as priorities evolve.

| Version | Theme | Status |
|---|---|---|
| v1.0 | Core Income Pipeline | ✅ Complete |
| v1.1 | Classification & Tax Foundation | ✅ Complete |
| v2.0 | Adaptive Intelligence | ✅ Complete (Agent 03) |
| v2.1 | Portfolio Optimization Suite | 🟡 In Progress |
| v3.0 | Predictive & Explainable AI | 🔵 Planned |
| v3.1 | Multi-Tenant & Scale | 🔵 Planned |

---

## v1.0 — Core Income Pipeline ✅ Complete

**Theme:** Foundation agents live in production. Ticker evaluation pipeline operational end-to-end.

### Completed
- ✅ Agent 01 — Market Data Service (Polygon + FMP + yfinance, port 8001)
- ✅ Agent 02 — Newsletter Ingestion Service (Seeking Alpha, Claude Haiku extraction, port 8002)
- ✅ Agent 03 — Income Scoring Service (Quality Gate + 8-component scorer + Monte Carlo NAV erosion, port 8003)
- ✅ Agent 04 — Asset Classification Service (port 8004) — 7-class rule engine, shared detector, benchmarks, tax profiles, 201 tests (2026-03-12)

---

## v1.1 — Classification & Tax Foundation ✅ Complete

**Theme:** Complete the classification layer and establish tax efficiency as a platform-wide output. Agent 03 becomes fully autonomous (no caller-provided asset_class required).

### Completed

Agent 03 enhancements now in production:
- ✅ Auto-classification integration: Agent 03 calls Agent 04 if no `asset_class` provided
- ✅ Inline fallback: imports shared detector directly if Agent 04 unavailable
- ✅ `tax_efficiency` field added to ScoreResponse (parallel output, 0% composite weight)
- ✅ `classification_verify_overrides` config flag: when True, calls Agent 04 even for manual overrides to detect mismatches

### Agent 04 — Asset Classification Service (port 8004)
- Full rule engine with 4 rule types (ticker pattern, sector, feature, metadata)
- 7 MVP asset classes: DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT, MORTGAGE_REIT, BDC, PREFERRED_STOCK
- Hybrid class detection (mREIT, PREFERRED_CEF, BDC_CEF)
- Benchmark comparison + class sub-scores
- `tax_efficiency` parallel output (income_type, tax_drag_pct, preferred_account)
- Manual override API with audit trail
- Shared utility: `src/shared/asset_class_detector/` importable by all agents
- Status: ✅ Complete (v1.0, 2026-03-12)

### Agent 05 — Tax Optimization Service (port 8005) ✅ Complete
- Consumes `asset_class` from Agent 04 (HTTP, 3s timeout, graceful fallback)
- After-tax yield calculation: 2024 IRS brackets, all 4 filing statuses, all 50 states + DC
- Account placement optimization: heuristic engine recommends IRA vs TAXABLE
- Tax-loss harvesting: wash-sale-aware opportunity identification (proposals only)
- Asset class reference endpoint: GET /tax/asset-classes
- 135 tests, 8 API endpoints
- Status: ✅ Complete (v1.0, 2026-03-12)

---

## v2.0 — Adaptive Intelligence ✅ Complete (Agent 03)

**Theme:** The platform begins learning from outcomes. Scoring weights adapt quarterly. Agent 02 signals influence scoring dynamically.

### Agent 03 — Completed (2026-03-12)

**Phase 0 — DB Foundation & Dynamic Weights** ✅ Complete
- New ORM tables: `scoring_weight_profiles`, `weight_change_audit`
- Weight profile loader with in-process cache
- 7 seed profiles per asset class (MORTGAGE_REIT 30/45/25, BDC 35/40/25, etc.)
- GET/POST /weights/* API endpoints
- IncomeScorer uses profile ceilings instead of hardcoded universals

**Phase 2 — Signal Penalty Layer** ✅ Complete
- Agent 02 signal integration: BEARISH (strong/moderate/weak) = -8/-5/-2 points
- Architecture constraint: bullish signals NEVER inflate scores (cap = 0.0)
- Eligibility gates: min analysts, min decay weight, consensus thresholds
- Score floor enforcement: penalty cannot reduce score below 0.0
- GET /signal-config/ returns active penalty configuration
- 60 tests covering all scenarios

**Phase 3 — Learning Loop** ✅ Complete
- Shadow portfolio tracking: AGGRESSIVE_BUY/ACCUMULATE recommendations tracked 90 days
- Outcome labeling: CORRECT (+5% return), INCORRECT (-5% return), NEUTRAL
- Quarterly weight review engine: proposes ±5pt max adjustments per pillar
- Weight sum=100 invariant enforcement
- GET/POST /learning-loop/* API endpoints
- 74 tests covering tuner logic and API contracts

**Phase 4 — Detector Confidence Learning** ✅ Complete
- Classification feedback tracking: records AGENT04 vs MANUAL_OVERRIDE per scoring call
- Mismatch detection when `CLASSIFICATION_VERIFY_OVERRIDES=True`
- Monthly accuracy rollup: computes accuracy_rate, override_rate, mismatch_rate
- GET/POST /classification-accuracy/* API endpoints
- 47 tests covering feedback capture and rollup logic

**Overall v2.0 metrics:**
- 438 total tests (all passing)
- 11 new tables in platform_shared schema
- 12 new API endpoints
- Full audit trail for all weight changes

### Future Phases (Not Yet Scheduled)

Agent 04 — Asset Classification Service (port 8004)
- Full rule engine with 4 rule types (ticker pattern, sector, feature, metadata)
- 7 MVP asset classes: DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT, MORTGAGE_REIT, BDC, PREFERRED_STOCK
- Hybrid class detection (mREIT, PREFERRED_CEF, BDC_CEF)
- Benchmark comparison + class sub-scores
- Status: DESIGN complete, Develop pending

Agent 05 — Tax Optimization Service (port 8005)
- Consumes `tax_efficiency` output from Agent 04
- After-tax yield scenarios (taxable vs. Roth/IRA)
- Account placement optimization
- Status: Planned

---

## v2.1 — Portfolio Optimization Suite 🟡 In Progress

**Theme:** From individual ticker evaluation to full portfolio management. Rebalancing, income projection, NAV monitoring.

### Foundation — Agent 06 Housekeeping ✅ Complete (2026-03-12)

- Fixed `class Config:` → `model_config = ConfigDict(...)` Pydantic v2 deprecation in scenario-simulation-service
- 135 tests passing, 0 deprecation warnings

### Foundation — Portfolio Schema ✅ Deployed (2026-03-12)

- 12 tables created in `platform_shared` via `src/portfolio-positions-schema/scripts/migrate.py`
- Phase 0: `securities`, `features_historical`, `user_preferences`
- Phase 1: `nav_snapshots`
- Phase 2: `accounts`, `portfolios`, `portfolio_constraints`
- Phase 3: `positions`, `transactions`, `dividend_events`
- Phase 4: `portfolio_income_metrics`, `portfolio_health_scores`

### Agent 06 — Scenario Simulation Service (port 8006) ✅ Complete (2026-03-12)

- 5 predefined stress scenarios (RATE_HIKE_200BPS, MARKET_CORRECTION_20, RECESSION_MILD, INFLATION_SPIKE, CREDIT_STRESS)
- Monte Carlo N=1000 log-normal GBM income projection, P10/P50/P90 bands
- Vulnerability ranking, asyncpg direct reads from platform_shared
- 135 tests

### Agent 07 — Opportunity Scanner (port 8007) ✅ Complete (2026-03-12)

- `POST /scan` — score up to 200 tickers via Agent 03, apply filters, rank results
- `GET /scan/{scan_id}` — retrieve persisted scan result
- `GET /universe` — list tracked securities from `platform_shared.securities`
- VETO gate: tickers with score < 70 flagged (`veto_flag: true`); excluded when `quality_gate_only: true`
- Concurrent scoring: asyncio semaphore (10 parallel Agent 03 calls)
- Graceful degradation: Agent 03 failures skip ticker, scan continues
- Results persisted to `platform_shared.scan_results`
- 100 tests (40 engine, 25 client, 35 API)

### Agent 08 — Rebalancing Service (port 8008) 🔵 Planned

- Greedy heuristic optimizer (sort by after-tax yield, enforce concentration limits)
- VETO gate: all buy proposals require score ≥ 70
- Output: rebalancing proposals (never auto-executed — user approval required)

### Agent 09 — Income Projection Service (port 8009) 🔵 Planned

- Runs in parallel with Agent 06 (not a replacement)
- Dividend-calendar-aware projection using actual ex-div dates from `dividend_events` table
- Reuses Agent 06 GBM engine for Monte Carlo uncertainty bands

### Agent 10 — NAV Monitor Service (port 8010) 🔵 Planned

- Real-time NAV trend tracking for ETF holdings
- Erosion alerts: configurable threshold triggers (default -5% over 90d)
- Feeds circuit breaker patterns in Agent 11

### Agent 11 — Alert Service (port 8011) 🔵 Planned

- Circuit breaker patterns: Capital safety / Yield sustainability / Growth trajectory
- Multi-day confirmation before alert fires (reduces false positives)
- Delivery: in-app (DB record) + SMTP email (configurable)
- User-configurable thresholds per portfolio

---

## v3.0 — Predictive & Explainable AI 🔵 Planned

**Theme:** Rule-based scoring replaced with ML. Full explainability via SHAP. Feature importance pipeline driven by analyst signal data.

### Agent 03 — ML Scoring Engine (v2 model)
- **XGBoost model** replaces rule-based scoring engine
- 50+ features per ticker (fundamentals, technicals, dividend history, analyst signals)
- **SHAP explainability layer:** every score accompanied by top-5 feature drivers
- Fast inference: CPU-only, <100ms per prediction
- Model versioning: `.pkl` files with registry table
- A/B testing framework: shadow scoring against rule-based v1 before cutover
- Source: ADR from platform design sessions (Jan 2026).

### Feature Importance Pipeline
- Agent 02 signal extraction feeds feature candidate pool
- Quarterly evaluation: statistical significance test against shadow portfolio outcomes
- Confirmed signals promoted as new scoring features with regression-derived initial weights
- Valuation methods per asset class remain fixed (accounting identities — not learned)
- New discriminating features that CAN learn: coverage ratio weighting for BDCs, distribution sustainability for mREITs, analyst consensus momentum
- Source: Architecture note from Agent 04 design session (2026-02-26).

### Asset Class Detector — ML v2
- Rule-based classifier (v1) runs in parallel with ML classifier (v2) initially
- ML model trained on shadow classification outcomes
- Cutover when ML confidence consistently exceeds rule-based across all 7 asset classes
- Source: Decision #4 from Agent 04 brainstorm.

---

## v3.1 — Multi-Tenant & Scale 🔵 Planned

**Theme:** Platform hardened for multiple tenants. Shared learning, isolated execution. Production-grade observability.

### Multi-Tenancy Architecture
- Tenant-isolated execution and results
- Shared learning: newsletter analysis, learning algorithm, simulation engine aggregate across tenants
- Row-level security (RLS) on all tenant data
- Per-tenant scoring weight overrides (user-level customization of class weights — Phase 2 of weight framework)
- Source: Platform architecture brainstorm (Feb 2026), Decision on shared vs. tenant-segregated entities.

### Agent 12 — Proposal Generator (port 8012)
- Synthesizes Agent 03 scores + Agent 04 classifications + Agent 07 opportunities
- Dual-lens proposal model: income safety lens + yield optimization lens
- Proposal workflow: generated → user review → approved/rejected/modified
- Never auto-executes — explicit user approval required at every step
- Source: Platform design docs (Jan 2026).

### Observability & Operations
- Distributed tracing across all 12+ agents
- Per-agent SLA monitoring
- Automated retraining triggers (data drift detection)
- Cost optimization: Haiku for classification/routing, Sonnet for analysis, Opus reserved for complex proposals

---

## Enhancement Backlog (Unscheduled)

Items identified but not yet assigned to a version:

| Enhancement | Source | Notes |
|---|---|---|
| Multi-account tax optimization | Agent 05 design | Cross-account placement across taxable + Roth/IRA |
| Backtesting engine | Agent design catalog | Historical validation of scoring model accuracy |
| Monte Carlo for full portfolio | Agent 06 design | Stress testing entire portfolio, not just individual ETFs |
| DRIP automation tracking | Platform design | Dividend reinvestment impact on position sizing |
| Alpaca/Schwab trade execution | Platform design | Execution only after explicit user approval |
| Dividend calendar agent | Research agent catalog | Forward dividend schedule aggregation |
| Sector concentration analyzer | Research agent catalog | Cross-portfolio sector exposure monitoring |
| Frontend dashboard | Next.js spec | Portfolio overview, research page, alerts page |
| WebSocket real-time updates | API design | Live score updates, alert notifications |

---

## Version Gate Criteria

Before any version is marked complete:

- All agents in scope have 134+ tests passing (matching v1.0 standard)
- Migration scripts tested on production schema
- docker-compose entries added for all new services
- Documentation suite generated (reference architecture + functional specs + test matrix + ADRs + CHANGELOG)
- No breaking changes to existing agent APIs without versioned endpoint

---

## Document Maintenance

This roadmap is updated when:
- A new phase is promoted from an agent spec to a version
- A brainstorm session concludes with committed decisions
- A version ships and items move to completed
- New enhancement items are identified in design sessions

**Update command:** `Quick Update — add [item] to roadmap under [version]`
