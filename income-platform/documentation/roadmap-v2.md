# Income Fortress Platform — Version 2 Roadmap

**Document Type:** Deferred Decisions + v2 Feature Roadmap
**Last Updated:** 2026-03-11
**Status:** Living document — updated as decisions are deferred during development

---

## Purpose

This document captures all decisions, features, and architectural improvements
that were explicitly deferred during v1 development. Each item includes the
rationale for deferral, the trigger condition for implementation, and the
ADR/session where the decision was made.

---

## Deferred Technical Decisions

### D1 — Sector-Aware Chowder Thresholds
**ADR:** P11
**Current state:** Asset-class based thresholds (DIVIDEND_STOCK 12/8, ETF+BOND 8/5)
**Problem:** A utility stock classified as DIVIDEND_STOCK uses 12% threshold but
should use 8% (same as REITs). Results in conservative bias — some BORDERLINE
signals shown as UNATTRACTIVE.

**v2 implementation:**
- Read `sector` from `platform_shared.securities` (populated after FMP paid plan)
- Add sector-specific threshold layer: UTILITY → 8/5, REIT-like stocks → 8/5
- `_chowder_signal_from_number()` accepts optional `sector` parameter

**Trigger:** FMP paid plan active AND Agent 12 DESIGN begins
**Impact:** Agent 03 `income_scorer.py` — `CHOWDER_THRESHOLDS` + `_chowder_signal_from_number()`
**Risk if deferred:** Conservative bias on utility/REIT dividend stocks only. Chowder
is 0% score weight — no scoring impact, only signal label.

---

### D2 — ElasticNet GLM Stress Model
**ADR:** P12
**Current state:** Asset-class shock table (deterministic, hardcoded percentages)
**Problem:** Shock values are literature-based estimates, not empirically derived.
Cannot adapt to changing market regimes without manual update.

**v2 implementation:**
1. Add `platform_shared.model_coefficients` table
2. Add `scripts/fit_glm.py` — ElasticNet training (scikit-learn), monthly refit
3. Add `simulation/glm_engine.py` — replaces shock table lookup
4. Keep shock table as fallback when GLM confidence is low
5. A/B validate: run both models in parallel for one quarter

**New dependencies:** `scikit-learn>=1.4.0`, `joblib>=1.3.0`
**Trigger:** `features_historical` > 500 observations per asset class (est. Q1 2028)
**Impact:** Agent 06 `stress_engine.py` — full replacement of shock calculation
**Risk if deferred:** Stress test accuracy degrades if market regimes shift significantly
from historical literature values. Manual shock table review recommended annually.

---

### D3 — UUID Primary Keys for Securities
**ADR:** P09
**Current state:** `securities.symbol` TEXT primary key
**Problem:** Symbol changes (ticker renames, spin-offs) break FK relationships.
Cannot represent the same company across multiple exchanges cleanly.

**v2 implementation:**
- Add `security_id UUID` as new PK
- Migrate all FK references in `features_historical`, `positions`, `asset_classifications`
- Keep `symbol` as unique indexed column for lookups
- Data migration script: backfill UUID for all existing rows

**Trigger:** Platform universe exceeds 200 unique symbols OR first symbol rename event
**Impact:** All tables with `symbol` FK — migrations required across 8+ tables
**Risk if deferred:** Low until first ticker rename occurs. Well-documented migration path.

---

### D4 — Tax Lot Cost Basis Tracking
**ADR:** P10
**Current state:** Average cost basis per position (`positions.avg_cost_basis`)
**Problem:** Average cost basis prevents optimal tax-loss harvesting. Cannot
identify specific lots for wash sale prevention or HIFO/LIFO strategies.

**v2 implementation:**
- Add `platform_shared.tax_lots` table (lot_id, position_id, acquired_date,
  quantity, cost_basis, lot_method)
- Update `transactions` to reference lot_id
- Agent 05 harvester uses lot-level data for precise TLH proposals

**Trigger:** Agent 05 v2 development OR user requests HIFO/LIFO selection
**Impact:** `positions`, `transactions` schema + Agent 05 harvester module
**Risk if deferred:** Tax harvesting proposals are less precise. Acceptable for v1
where portfolio sizes are small.

---

### D5 — asyncpg Connection Pooling
**Current state:** Each `get_features()` (Agent 03) and `portfolio_reader.py`
(Agent 06) opens a new asyncpg connection per request.
**Problem:** Under load, connection exhaustion is possible. New connection
overhead adds ~20-50ms per request.

**v2 implementation:**
- Add shared asyncpg connection pool at startup (min=2, max=10)
- Pass pool reference into reader methods instead of creating connections
- Add pool health check to `/health` endpoint

**Trigger:** p95 latency on scoring or simulation endpoints exceeds SLA, OR
concurrent user count exceeds 10
**Impact:** `app/database.py` in Agents 03 and 06 — pool initialization at startup
**Risk if deferred:** Minimal at current scale. DigitalOcean managed PostgreSQL
supports up to 25 concurrent connections on current plan.

---

### D6 — FMP Paid Plan — Unlock Fundamentals
**Current state:** FMP Starter plan — `/ratios` and `/profile` return HTTP 402.
`securities.name`, `securities.sector`, `features_historical.interest_coverage`
are NULL for most tickers.

**Impact of upgrading:**
- Agent 01 `/sync` populates `name`, `sector`, `interest_coverage`
- Agent 03 financial durability score improves (interest_coverage feeds FCF gate)
- ADR-P11 (sector-aware Chowder thresholds) becomes implementable
- `data_completeness_pct` improves from ~50% to ~85% for most tickers

**Action required:** Subscribe to FMP Growth or higher plan
**Trigger:** Before Agent 07 (Opportunity Scanner) DESIGN — sector data essential
for screening
**Cost:** ~$49/month (FMP Growth)

---

## Planned Agents (v1.x — Near Term)

### Agent 07 — Opportunity Scanner
**Priority:** P1 — design after Agent 06 deployment confirmed
**Purpose:** Screen a universe of tickers for new income investment candidates
**Key inputs:** `features_historical`, `asset_classifications`, Agent 03 scores
**Key outputs:** Ranked candidate list with income score + entry signal
**Dependency:** FMP paid plan recommended (sector filtering)

---

### Agent 08 — Rebalancing
**Priority:** P1
**Purpose:** Generate portfolio rebalancing proposals (never executes)
**Key inputs:** `positions`, `portfolio_constraints`, income scores
**Key outputs:** Rebalancing proposal with tax impact estimate (via Agent 05)
**Dependency:** Agent 05 (tax), Agent 03 (scores)

---

### Agent 09 — Income Projection (Position-Level)
**Priority:** P1
**Purpose:** Forward 12-month income forecast per position, accounting for
dividend schedules, ex-dates, and historical payment patterns
**Note:** Agent 06 already has portfolio-level Monte Carlo. Agent 09 adds
position-level precision with actual dividend calendar data.
**Key inputs:** `dividend_events`, `features_historical`

---

### Agent 10 — NAV Monitor
**Priority:** P1
**Purpose:** Track ETF NAV erosion over time — alert when realized erosion
diverges from Agent 03 simulation
**Key inputs:** `nav_snapshots`, `income_scores`
**Key outputs:** Erosion alerts → `flow_run_log`

---

### Agent 11 — Alert Classification
**Priority:** P2
**Purpose:** Smart alert generation — classifies events by urgency and
routes to appropriate downstream action
**Key inputs:** All agent outputs, `flow_run_log`

---

### Agent 12 — Proposal Agent ⭐ Priority Gate
**Priority:** P0 — all other agents feed into this
**Purpose:** Synthesizes analyst signals (Agent 02) with platform assessments
using a dual-lens model. Generates BUY/SELL/HOLD/WATCH proposals.
**Key principle:** Platform never silently blocks analyst recommendations —
explicit user acknowledgment required for overrides.
**Pre-requisites before DESIGN:**
- ADR-P11 reviewed (Chowder thresholds)
- ADR-P12 reviewed (GLM vs shock table accuracy)
- Agents 07–11 functional specs written
- DCA schedule integration (Amendment A4 — deferred)

---

## Deferred Feature Amendments

### Amendment A3 — Agent 04 Named Entry Signal Flags
**Status:** Designed, not built
**Description:** Add entry signal flags to `asset_classifications` output
(OVERSOLD, AT_SUPPORT, GOLDEN_CROSS, etc.)
**Trigger:** Agent 07 (Opportunity Scanner) DESIGN

---

### Amendment A4 — Agent 12 DCA Schedule on BUY Proposals
**Status:** Concept only
**Description:** When Agent 12 generates a BUY proposal, include a DCA
schedule (divide into 4 tranches, deploy 25% per month or per 5% dip)
consistent with Asset-Gem entry strategy
**Reference:** Asset-Gem.md — "The Best Strategy: Dollar Cost Averaging"
**Trigger:** Agent 12 DESIGN

---

## Annual Review Items

| Item | Review Trigger | Owner |
|------|---------------|-------|
| Shock table values (Agent 06) | Annually or major regime change | Manual review |
| Tax brackets (Agent 05) | Each tax year (January) | IRS publication update |
| Chowder thresholds (Agent 03) | Before Agent 12 design + annually | ADR-P11 |
| FMP API plan tier | Before Agent 07 design | Subscription review |
| DigitalOcean droplet sizing | When p95 latency > SLA | Monitor dashboards |

---

## Technical Debt Log

| Item | Location | Severity | Notes |
|------|----------|----------|-------|
| `datetime.utcnow()` deprecation warnings | Agents 03, 06 | Low | Replace with `datetime.now(UTC)` in v1.x cleanup |
| Pre-existing test failures in `test_quality_gate.py` | Agent 03 | Medium | Unrelated to v1.1.0 — needs investigation |
| Agent 03 connection-per-call asyncpg | `data_client.py` | Low | See D5 above |
| `securities.name` / `sector` NULL for most tickers | DB | Medium | Blocked on FMP paid plan |
| Python 3.13 in local venvs | Dev environment | Low | Docker uses 3.11 correctly |
