# Income Fortress Platform — CHANGELOG

---

## [1.4.0] — 2026-03-11

### Added
- **Agent 06** — Scenario Simulation Service (port 8006)
  - 5 predefined scenarios × 7 asset classes (asset-class shock table)
  - Custom scenario support (NL/LLM compatible)
  - Monte Carlo income projection P10/P50/P90
  - Cross-scenario vulnerability ranking
  - Explicit save to `scenario_results` with label
  - 33/33 tests passing
- **ADR-P12** — ElasticNet GLM deferred to v2 (trigger: 24+ months features_historical)
- **roadmap-v2.md** — Consolidated deferred decisions and v2 feature roadmap
- **index.md** — Updated master index reflecting all 6 deployed agents

### Infrastructure
- docker-compose.yml: added `agent-06-scenario-simulation` entry
- Nginx: `/api/scenario-simulation/` route (configured separately)

---

## [1.3.1] — 2026-03-11

### Fixed
- **Agent 03** — `quality_gate.py` evaluate_single() now persists gate result to DB
- **Agent 03** — All ORM models set `schema="platform_shared"` (was None / missing)
- **Agent 03** — `asyncpg` added to requirements for `get_features()` DB read

---

## [1.3.0] — 2026-03-09

### Added
- **Agent 03 v1.1.0** — Amendment A2: Chowder Number signal
  - Chowder Number sourced from `features_historical` via asyncpg
  - `chowder_signal`: ATTRACTIVE / BORDERLINE / UNATTRACTIVE / INSUFFICIENT_DATA
  - Asset-class aware thresholds (DGI 12/8, ETF+BOND 8/5)
  - 0% score weight — total_score/grade/recommendation unchanged
  - 17 unit tests (test_chowder.py)
- **ADR-P11** — Sector-aware Chowder threshold refinement deferred to v2

---

## [1.2.0] — 2026-03-09

### Added
- **Agent 01 v1.1.0** — Finnhub credit ratings, securities upsert, features upsert
  - `POST /stocks/{symbol}/sync` endpoint
  - Writes to `platform_shared.securities` and `platform_shared.features_historical`
  - Chowder Number computed and stored (`yield_trailing_12m + div_cagr_5y`)
  - 76 tests passing

### Fixed
- `securities_repository.py`: `currency = currency or "USD"` before upsert (NOT NULL constraint)
- DB grants: `doadmin` granted SELECT/INSERT/UPDATE on all 12 portfolio schema tables

---

## [1.1.0] — 2026-02-XX

### Added
- **Portfolio schema migration** — 12 tables in `platform_shared`:
  securities, features_historical, user_preferences, nav_snapshots,
  accounts, portfolios, portfolio_constraints, positions, transactions,
  dividend_events, portfolio_income_metrics, portfolio_health_scores
- **ADR-P09** — Symbol TEXT PK v1 (UUID migration path documented for v2)
- **ADR-P10** — Average cost basis v1 (tax lot migration path documented for v2)

---

## [1.0.0] — 2026-01-XX

### Added
- Agent 01 — Market Data Service (Polygon.io, FMP, yfinance)
- Agent 02 — Newsletter Ingestion (Seeking Alpha, Claude Haiku, S-curve decay)
- Agent 03 — Income Scoring (quality gate, weighted scoring, NAV erosion Monte Carlo)
- Agent 04 — Asset Classification (7 asset classes, shared utility)
- Agent 05 — Tax Optimization (2024 IRS brackets, 51 states, Section 1256)
- DigitalOcean infrastructure (Ubuntu droplet, managed PostgreSQL, Valkey, Nginx+SSL)
- GitHub Actions CI
