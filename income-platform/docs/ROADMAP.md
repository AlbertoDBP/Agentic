# Income Fortress Platform — Product Roadmap

**Document:** ROADMAP.md  
**Location:** `income-platform/docs/ROADMAP.md`  
**Last Updated:** 2026-02-26  
**Owner:** Platform Architecture

---

## Versioning Philosophy

Each version groups related enhancements that form a coherent capability upgrade. Phases documented inside individual agent specs are consolidated here so they can be sequenced across releases as priorities evolve.

| Version | Theme | Status |
|---|---|---|
| v1.0 | Core Income Pipeline | ✅ In Progress |
| v1.1 | Classification & Tax Foundation | 🔵 Planned |
| v2.0 | Adaptive Intelligence | 🔵 Planned |
| v2.1 | Portfolio Optimization Suite | 🔵 Planned |
| v3.0 | Predictive & Explainable AI | 🔵 Planned |
| v3.1 | Multi-Tenant & Scale | 🔵 Planned |

---

## v1.0 — Core Income Pipeline ✅ In Progress

**Theme:** Foundation agents live in production. Ticker evaluation pipeline operational end-to-end.

### Completed
- ✅ Agent 01 — Market Data Service (Polygon + FMP + yfinance, port 8001)
- ✅ Agent 02 — Newsletter Ingestion Service (Seeking Alpha, Claude Haiku extraction, port 8002)
- ✅ Agent 03 — Income Scoring Service (Quality Gate + 8-component scorer + Monte Carlo NAV erosion, port 8003)

### In Progress
- 🔄 Agent 04 — Asset Classification Service (port 8004) — DESIGN complete, Develop pending

### Deferred to v1.1
- Agent 03: Inline quality gate currently requires `asset_class` from caller — will auto-resolve once Agent 04 is live

---

## v1.1 — Classification & Tax Foundation 🔵 Planned

**Theme:** Complete the classification layer and establish tax efficiency as a platform-wide output. Agent 03 becomes fully autonomous (no caller-provided asset_class required).

### Agent 04 — Asset Classification Service (port 8004)
- Full rule engine with 4 rule types (ticker pattern, sector, feature, metadata)
- 7 MVP asset classes: DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT, MORTGAGE_REIT, BDC, PREFERRED_STOCK
- Hybrid class detection (mREIT, PREFERRED_CEF, BDC_CEF)
- Benchmark comparison + class sub-scores
- `tax_efficiency` parallel output (income_type, tax_drag_pct, preferred_account)
- Manual override API with audit trail
- Shared utility: `src/shared/asset_class_detector/` importable by all agents

### Agent 03 Integration
- Auto-classification: Agent 03 calls Agent 04 if no `asset_class` provided
- Inline fallback: imports shared detector directly if Agent 04 unavailable
- `tax_efficiency` field added to ScoreResponse (parallel, 0% composite weight)

### Agent 05 — Tax Optimization Service (port 8005)
- Consumes `tax_efficiency` output from Agent 04
- After-tax yield scenarios (taxable vs. Roth/IRA)
- Account placement optimization
- Florida-specific: no state tax calculations required
- Tax harvesting batch jobs (not real-time)
- Multi-account optimization across portfolio

---

## v2.0 — Adaptive Intelligence 🔵 Planned

**Theme:** The platform begins learning from outcomes. Scoring weights adapt quarterly. Agent 02 signals influence scoring dynamically.

### Agent 03 Enhancements
- **Newsletter signal integration (Agent 02 → Agent 03):** Negative analyst signals apply penalty layer to composite score. Risk flag architecture — signals reduce score, never inflate it. Source: ADR from Agent 03 brainstorm session (Decision #11).
- **Scoring weight framework — class-specific full replacement sets:** Each asset class gets its own complete weight profile (e.g., mREIT = yield 30 / durability 45 / technical 25). Replaces universal weights applied in v1.0.
- **Technical scoring — class-specific factors via Preference Table:** Different technical indicators weighted differently per class. Source: Decision #9.

### Learning Loop — Quarterly Adaptive Weight Tuning
- Shadow portfolio tracking activated: every ACCUMULATE/AGGRESSIVE_BUY recommendation tracked against actual income outcomes (12-month window)
- Quarterly weight review: statistical analysis of which sub-components predicted actual dividend cuts, NAV erosion, coverage failures
- Weight adjustments bounded (±5% per quarter) to prevent overfitting
- Full audit trail — every weight change logged with rationale and supporting data
- Source: Decision #13 from Agent 03/04 brainstorm.

### Asset Class Detector — Confidence Learning
- Confidence scores updated based on classification accuracy vs. actual outcomes
- New hybrid patterns promoted to rule engine via DB insert (no redeploy)
- Source: Agent 04 design — DB-driven rule engine pattern.

---

## v2.1 — Portfolio Optimization Suite 🔵 Planned

**Theme:** From individual ticker evaluation to full portfolio management. Rebalancing, income projection, NAV monitoring.

### Agent 07 — Opportunity Scanner (port 8007)
- Composite scoring across universe of income tickers
- Filters: yield threshold, asset class, quality gate status
- Output: ranked candidate list for proposal generator

### Agent 08 — Rebalancing Service (port 8008)
- CVXPY optimization engine
- Constraints: income target, concentration limits, asset class allocation
- Output: rebalancing proposals (never auto-executed — user approval required)

### Agent 09 — Income Projection Service (port 8009)
- Forward 12-month income forecast per portfolio
- Dividend schedule modeling
- Scenario analysis: dividend cut, yield change, reinvestment

### Agent 10 — NAV Monitor Service (port 8010)
- Real-time NAV trend tracking for ETF holdings
- Erosion alerts: configurable threshold triggers
- Feeds circuit breaker patterns in Agent 11

### Agent 11 — Alert Service (port 8011)
- Circuit breaker patterns: Capital safety / Yield sustainability / Growth trajectory
- Multi-day confirmation before alert fires (reduces false positives)
- Notification hybrid: in-app + email
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
