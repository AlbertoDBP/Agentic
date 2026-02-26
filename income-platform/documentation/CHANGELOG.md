# Income Fortress Platform — CHANGELOG

All notable changes to the Income Fortress Platform are documented here.
Format: [Semantic Versioning](https://semver.org/) — `[version] YYYY-MM-DD`

---

## [Unreleased]

### Planned
- Agent 03 Phase 1–6 implementation
- Agent 04 — Asset Class Evaluator design
- Shared Asset Class Detector v1 implementation

---

## [0.3.0] — 2026-02-25 — Agent 03 Design Complete

### Added
- **Agent 03 — Income Scorer**: Complete architecture design
  - 7-class scoring framework (REITs, mREITs, BDCs, CEFs, Covered Call ETFs, Bonds, Preferred Stocks)
  - Quality Gate Router with 8 class-specific gates + universal fallback
  - Composite scorer with full replacement weight sets per asset class
  - VETO engine (post-composite — preserves sub-scores for audit)
  - Monte Carlo NAV erosion analysis (Covered Call ETFs, mREITs, leveraged CEFs)
  - Risk penalty layer with Agent 02 negative-signal integration
  - Tax efficiency as parallel metadata field (0% composite weight)
  - Quarterly adaptive learning loop with shadow portfolio
  - 10 Alembic database migrations specified
  - FastAPI endpoints defined (8 routes)
  - Full test suite spec (unit, integration, acceptance, performance SLAs)
- **ADR-001**: Post-Scoring LLM Explanation Layer
- **Shared Utility**: Asset Class Detector scoped (`/shared/asset_class_detector/`)
- **Agent 04 — Asset Class Evaluator**: Scoped (design pending)
- **Agent 05 — Tax Optimizer**: Role clarified — consumes tax_efficiency metadata from Agent 03
- **`scripts/validate-documentation.py`**: Automated documentation validation (48 checks)
- **`documentation/decisions-log.md`**: Consolidated ADR register (ADR-001 through ADR-010)
- **`documentation/platform-index.md`**: Master agent status tracker

### Changed
- **Data Stack**: yfinance designated as Agent 03 primary provider with FMP/Polygon for gaps
- **Scoring Architecture**: Formally split — Agent 03 = Income Fortress Score, Agent 04 = Asset Class Evaluation

---

## [0.2.0] — 2026-02-25 — Agent 02 Production Complete

### Added
- Agent 02 — Newsletter Ingestion Service: all 5 phases complete and production-deployed
  - Phase 1: FastAPI skeleton, SQLAlchemy ORM (5 tables), pgvector + IVFFlat index, health endpoint, 13 tests
  - Phase 2: APIDojo Seeking Alpha client, Prefect 3 harvester flow, Claude Haiku signal extraction, OpenAI embeddings, 47 tests
  - Phase 3: S-curve decay sweeper, FMP market truth client, accuracy backtest, philosophy synthesis (LLM + K-Means), weighted consensus builder, Intelligence Prefect flow, 57 tests
  - Phase 4: Analysts API, recommendations API, consensus API (Redis-cached 30min), signal endpoint (Agent 12 contract), 18 tests
  - Phase 5: Multi-stage Dockerfile, docker-compose, Nginx config, DigitalOcean deploy script, Prefect schedule, `.env.production.example`

### Fixed
- APIDojo SA API: category-based author discovery after legacy author-filter endpoints removed (2026)
- Consensus builder: chained `.filter()` calls for testability
- Signal endpoint: `rec_metadata` attr to avoid SQLAlchemy MetaData name collision
- Dockerfile: uses `python3 -m uvicorn`; deploy.sh uses `/opt/Agentic` path

---

## [0.1.1] — 2026-02-23 — Agent 01 Provider Migration

### Added
- PolygonClient: Polygon.io REST API v2/v3 implementation
- FMPClient: Financial Modeling Prep stable API implementation
- YFinanceClient: yfinance fallback provider
- BaseDataProvider abstract class + provider exceptions
- ProviderRouter with Polygon/FMP/yfinance fallback chains
- New endpoints: dividends, fundamentals, ETF holdings, provider status

### Changed
- Alpha Vantage retired as primary provider
- FMP migrated from legacy v3 to stable API (all endpoints)

### Fixed
- yfinance ETF field mappings (expense_ratio, AUM, top_holdings)
- Covered call detection expanded (JEPI ELN pattern, buy-write, symbol list)
- FMP: surface ProviderError on empty API key; re-raise on primary request failure
- Routes consolidated to `/stocks/` pattern; legacy `/api/v1/price/` removed

---

## [0.1.0] — 2026-02-12 — Agent 01 Production Deployed

### Added
- Agent 01 — Market Data Service: production deployment
  - FastAPI microservice on port 8001 with Redis caching
  - Alpha Vantage integration with rate limiting and fallback chains
  - Database persistence (PostgreSQL managed, DigitalOcean)
  - Historical price queries v1.2.0
- Platform infrastructure: DigitalOcean App Platform, managed PostgreSQL (68+ tables), Valkey cache, Nginx reverse proxy with SSL at legatoinvest.com
- Monorepo structure: `/Agentic/income-platform/`

---

## [1.0.0-design] — 2026-01-28 — Initial Platform Design

> **Note:** This entry records the original design-phase specification completed before implementation began. Preserved for historical reference.

### Design Complete — Production Ready

Complete design specification for the Tax-Efficient Income Investment Platform.

#### Core Architecture
- Capital preservation scoring system (70% threshold with VETO)
- Income generation optimization (secondary to capital safety)
- Yield trap detection framework
- Tax efficiency optimization system
- User-controlled proposal workflow (no auto-execution)

#### Data Model
- 97 database tables across 12 domains
- Multi-tenant architecture with Row-Level Security (RLS)
- Time-series partitioning for market data
- pgvector for semantic search

#### AI Agent Architecture (22 Agents)
- Data Processing Agents (5): Asset Class Identifier, ETF Look-Through, Analyst Extractor, Tax Processor, Sentiment Analyzer
- Scoring Agents (4): Capital Protection, Portfolio Fit, Asset Class-Specific (9), Conflict Resolver
- Analysis Agents (5): Portfolio Analyzer, Risk Aggregator, Simulator, Scenario Predictor, Stock Evaluator
- Recommendation Agents (4): Proposal Generator, Alert Monitor, Market Scanner, Trade Generator
- Support Agents (4): Price Calculator, Explanation Generator, Framework Generator, Conversational AI

#### API Architecture
- 88+ endpoints (OpenAPI 3.0)
- Authentication, portfolio, trading, alerts, proposals, analytics, tax, goals, simulations, backtesting, DRIP, rebalancing, document generation, GDPR, admin, WebSocket

#### Security & Compliance
- JWT authentication via Supabase
- AES-256 encryption, RBAC, GDPR framework (DSAR, consent, erasure)
- 7-year data retention with legal holds
- Comprehensive audit logging

#### Advanced Features
- Monte Carlo Simulation (10K+ simulations)
- Retirement Planning + Safe Withdrawal Rate
- Backtesting Engine
- Automated Rebalancing (tax-aware)
- DRIP System
- Goals Management
- Multi-Currency (7 currencies)
- Document Generation (PDF/Excel/Word)

#### Learning Systems (6 Layers)
1. Analyst Learning: Extract frameworks from analyst content
2. Tax Learning: Pattern recognition from tax documents
3. Model Learning: XGBoost retraining on outcomes
4. Execution Learning: Optimize order execution
5. Conversational Learning: User preference extraction
6. LLM Self-Learning: Real-time session adaptation

#### Design Metrics
| Metric | Value |
|---|---|
| Design Completeness | 100% |
| Database Tables | 97 |
| AI Agents | 22 |
| API Endpoints | 88+ |
| Supported Asset Classes | 9 |
| Learning Layers | 6 |
| Mermaid Diagrams | 15+ |
| Total Design Sessions | 4 |

---

## Legend
- **Added** — New features or components
- **Changed** — Changes to existing functionality
- **Deprecated** — Features to be removed in future
- **Removed** — Features removed
- **Fixed** — Bug fixes
- **Security** — Security-related changes
