# Income Fortress Platform — Comprehensive Documentation

**Version:** 1.0.0
**Last Updated:** March 2026
**Target Audience:** Developers, DevOps Engineers, Product Managers
**Status:** Production-Ready

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Architecture & Design](#architecture--design)
3. [Agent Specifications](#agent-specifications)
4. [Database Schema](#database-schema)
5. [Authentication & Security](#authentication--security)
6. [Deployment](#deployment)
7. [Configuration & Environment Variables](#configuration--environment-variables)
8. [Inter-Service Communication](#inter-service-communication)
9. [API Reference](#api-reference)
10. [Troubleshooting](#troubleshooting)

---

## Platform Overview

### Mission

Income Fortress is a tax-efficient income investment platform with AI-powered analysis. It helps investors:

- **Preserve Capital** — 70% score threshold (VETO gate) prevents deteriorating assets
- **Generate Income** — Scores yield without falling into yield traps
- **Optimize Taxes** — Tracks ROC, qualified dividends, Section 1256 treatment
- **Maintain Control** — Proposal-based workflow (never auto-executes)

### Core Principles

1. **Capital preservation first** — Income is secondary to protecting capital
2. **User control always** — All actions require explicit user approval (proposals only)
3. **Transparency** — Every recommendation includes reasoning and confidence scores
4. **No hidden overrides** — The platform never silently overrides analyst signals
5. **Quality gates** — Poor-quality assets are vetoed before scoring begins

### Key Statistics

| Metric | Value |
|--------|-------|
| Agents | 12 microservices |
| Ports | 8001-8012 |
| Programming Language | Python 3.11+ |
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 15+ |
| Cache | Redis 7+ |
| Message Queue | Redis (future: Celery) |
| API Authentication | JWT HS256 |
| Deployment | Docker Compose + DigitalOcean |
| Expected Latency (p95) | < 500ms |
| SLA Target | 99.9% uptime |

---

## Architecture & Design

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         External Users                               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
         ┌───────────────────▼────────────────────┐
         │        Nginx (SSL/TLS + Rate Limit)     │
         └───────────────────┬────────────────────┘
                             │
         ┌───────────────────▼──────────────────────────┐
         │   FastAPI Gateway (Port 8000, future)        │
         │   - Routing to 12 agents                      │
         │   - Rate limiting (3-tier)                    │
         │   - Request logging & tracing                 │
         └─────┬─────────────┬─────────────────┬────────┘
               │             │                 │
    ┌──────────▼──┐ ┌────────▼──────┐ ┌───────▼────────┐
    │  Agent 01   │ │  Agent 02-12   │ │  Shared Layer  │
    │ Market Data │ │ (11 services)  │ │  - Auth        │
    │ (Port 8001) │ │ (Ports 8002-12)│ │  - DB Mgmt     │
    └──────┬──────┘ └────────┬───────┘ │  - Monitoring  │
           │                 │         └────┬───────────┘
           └────────┬────────┘              │
                    │                       │
         ┌──────────▼──────────────┐       │
         │   PostgreSQL (Shared)   │───────┘
         │   - platform_shared schema        │
         │   - Row-level security (RLS)      │
         │   - Multi-tenant isolation        │
         └──────────┬──────────────┘
                    │
         ┌──────────▼──────────────┐
         │   Redis / Valkey        │
         │   - Cache layer         │
         │   - Session store       │
         │   - Future: task queue  │
         └─────────────────────────┘
```

### Microservices Architecture

The platform uses **loosely coupled, independently deployable services** connected via HTTP/REST and shared PostgreSQL database.

**Design patterns:**
- **Service-to-service HTTP calls** use HS256 JWT tokens (inter-service auth)
- **Shared database** — all services read/write to `platform_shared` schema
- **Cache-aside pattern** — Redis for frequently accessed data (prices, features)
- **Fire-and-forget persistence** — async upserts to database don't block responses
- **Graceful degradation** — services remain operational if downstream dependencies are slow/down

### Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Language** | Python | 3.11+ | Core implementation |
| **Web Framework** | FastAPI | 0.100+ | REST API, async I/O |
| **App Server** | Uvicorn | 0.24+ | ASGI server |
| **Database** | PostgreSQL | 15+ | Persistent data storage |
| **Cache** | Redis/Valkey | 7+ | Session + data caching |
| **Container** | Docker | 20.10+ | Service containerization |
| **Orchestration** | Docker Compose | 2.0+ | Multi-service coordination |
| **AI/LLM** | Anthropic Claude | Opus/Sonnet/Haiku | Intelligent analysis |
| **HTTP Client** | httpx/aiohttp | Latest | Async inter-service calls |
| **ORM** | SQLAlchemy | 2.0+ | Database abstraction |
| **Validation** | Pydantic | v2 | Request/response validation |
| **Monitoring** | Prometheus/Sentry | Latest | Observability (future) |

---

## Agent Specifications

Each agent is an independent FastAPI service with dedicated port and schema. All agents use the shared `platform_shared` PostgreSQL schema for data interchange.

### Agent 01: Market Data Service

**Port:** 8001
**Schema:** `platform_shared`
**Responsibility:** Real-time and historical market data aggregation

**Overview:**
Foundational data layer providing current prices, historical OHLCV, dividend history, fundamentals, and ETF holdings. Multi-provider fallback strategy (Polygon → FMP → yfinance → Finnhub) ensures graceful degradation during API outages.

**Key Features:**
- Current price retrieval with 5-minute Redis cache
- 20-year historical price data with 6-hour cache
- Dividend payment history (FMP primary, yfinance fallback)
- Fundamental metrics (P/E, debt-to-equity, payout ratio, free cash flow, market cap, sector)
- ETF metadata (expense ratio, AUM, covered call flag, top 20 holdings)
- Provider health monitoring with last-used timestamps
- Fire-and-forget security metadata persistence

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Service info |
| GET | `/health` | None | Health check (DB + cache) |
| GET | `/stocks/{symbol}/price` | JWT | Current price (cached 5 min) |
| GET | `/stocks/{symbol}/history` | JWT | OHLCV for date range |
| GET | `/stocks/{symbol}/history/stats` | JWT | Min/max/avg/volatility/returns |
| POST | `/stocks/{symbol}/history/refresh` | JWT | Force-fetch & persist |
| GET | `/stocks/{symbol}/dividends` | JWT | Dividend history |
| GET | `/stocks/{symbol}/fundamentals` | JWT | P/E, debt/equity, sector, etc. |
| GET | `/stocks/{symbol}/etf` | JWT | ETF metadata & holdings |
| GET | `/api/v1/providers/status` | JWT | Provider health status |
| POST | `/stocks/{symbol}/sync` | JWT | Fetch & persist fundamentals |
| GET | `/api/v1/cache/stats` | JWT | Cache statistics |

**Example Requests:**

```bash
# Get current price
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JEPI/price

# Get historical data
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/stocks/JEPI/history?start_date=2025-01-01&end_date=2025-12-31"

# Get statistics over period
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/stocks/JEPI/history/stats?start_date=2025-01-01&end_date=2025-12-31"

# Get dividend history
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JEPI/dividends

# Get ETF metadata
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/stocks/JEPI/etf
```

**Response Examples:**

```json
{
  "symbol": "JEPI",
  "price": 54.32,
  "timestamp": "2026-03-13T14:30:00Z",
  "source": "polygon"
}
```

**Dependencies:** PostgreSQL, Redis, external APIs (Polygon, FMP, yfinance, Finnhub)

**Called by:** Agent 03, 04, 05, 06, 07, 08, 09, 10

---

### Agent 02: Newsletter Ingestion

**Port:** 8002
**Schema:** `platform_shared`
**Responsibility:** Analyst content ingestion and intelligence extraction

**Overview:**
The Dividend Detective service ingests Seeking Alpha analyst articles, extracts income investment signals, maintains analyst accuracy profiles, and produces AnalystSignal objects for Agent 12 (Proposal Engine). Bridges the gap between human analysts and the AI platform.

**Key Features:**
- Seeking Alpha article ingestion (via API)
- Income sentiment extraction (AI-powered)
- Analyst profile building (accuracy tracking over time)
- Recommendation consensus scoring
- Signal production for Agent 12

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Service info |
| GET | `/health` | None | Health check |
| POST | `/flows/harvest` | JWT | Trigger article harvesting |
| GET | `/analysts` | JWT | List analysts & profiles |
| GET | `/analysts/{analyst_id}` | JWT | Individual analyst metrics |
| GET | `/recommendations` | JWT | List recommendations |
| GET | `/recommendations/{ticker}` | JWT | Recommendations for ticker |
| GET | `/consensus/{ticker}` | JWT | Consensus signal for ticker |
| GET | `/signal/{ticker}` | JWT | Full signal package |

**Dependencies:** PostgreSQL, Anthropic Claude API, Seeking Alpha API

**Called by:** Agent 12

---

### Agent 03: Income Scoring

**Port:** 8003
**Schema:** `platform_shared`
**Responsibility:** Asset evaluation with quality gates and hybrid scoring

**Overview:**
Core scoring engine combining Income Fortress + SAIS methodologies. Enforces a 70% capital preservation threshold (VETO gate) that prevents poor-quality assets from proceeding. Uses multi-factor quality assessment before calculating income scores.

**Key Features:**
- Quality gate evaluation (capital preservation threshold: 70%)
- Three scoring methods (Income Fortress, SAIS, Blended)
- Dividend stock scoring (yield, growth, payout ratio, sustainability)
- Covered call ETF scoring (with NAV erosion penalty)
- Bond scoring (credit quality, duration, yield)
- NAV erosion detection for covered calls
- Learning loop for model refinement

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/scores/evaluate` | JWT | Score a single asset |
| POST | `/scores/batch` | JWT | Score multiple assets |
| GET | `/scores/{symbol}` | JWT | Get cached score |
| POST | `/quality-gate/check` | JWT | Check if asset meets VETO |
| GET | `/weights/{method}` | JWT | Get scoring weights |
| POST | `/weights/{method}` | JWT | Update weights |
| GET | `/learning/accuracy` | JWT | Model accuracy metrics |

**Response Example:**

```json
{
  "symbol": "JEPI",
  "method": "blended",
  "score": 78.5,
  "capital_preservation_score": 82.0,
  "income_score": 75.0,
  "quality_gate_passed": true,
  "components": {
    "dividend_yield": 10.2,
    "dividend_growth": -2.1,
    "payout_ratio": 85.0,
    "covered_call_strike_otm": 5.5,
    "nav_erosion_penalty": -3.0
  },
  "confidence": 0.92,
  "timestamp": "2026-03-13T14:30:00Z"
}
```

**Dependencies:** Agent 01 (market data), Agent 04 (classification), PostgreSQL, Anthropic Claude

**Calls:** Agent 01, Agent 04

**Called by:** Agent 07, 08, 11, 12

---

### Agent 04: Asset Classification

**Port:** 8004
**Schema:** `platform_shared`
**Responsibility:** Asset taxonomy and classification rules

**Overview:**
Determines asset type (dividend stock, covered call ETF, bond, etc.) and calculates entry price scoring. Applies classification rules based on ticker metadata, fundamental characteristics, and regulatory definitions.

**Key Features:**
- Asset type classification (stock vs. ETF vs. bond vs. CEF/BDC)
- Covered call ETF detection
- Dividend sustainability assessment
- Entry price scoring (cost basis analysis)
- Tax treatment classification (qualified vs. ordinary dividends)

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/classify/{symbol}` | JWT | Classify asset |
| GET | `/classify/{symbol}` | JWT | Get cached classification |
| POST | `/rules` | JWT | Define/update rules |
| GET | `/rules` | JWT | List all rules |
| POST | `/entry-price` | JWT | Calculate entry price score |
| GET | `/entry-price/{symbol}` | JWT | Get entry price analysis |

**Dependencies:** Agent 01 (market data), PostgreSQL

**Calls:** Agent 01

**Called by:** Agent 03, 05, 12

---

### Agent 05: Tax Optimization

**Port:** 8005
**Schema:** `platform_shared`
**Responsibility:** Tax-efficient account placement strategy

**Overview:**
Provides tax treatment profiling, after-tax yield calculation, and account placement optimization. Tracks return-of-capital (ROC), qualified vs. ordinary dividends, and Section 1256 contract designations.

**Key Features:**
- Tax treatment classification (ROC, qualified dividend, ordinary income, Section 1256)
- After-tax yield calculation
- Account placement recommendations (taxable vs. tax-deferred vs. tax-free)
- Tax-loss harvesting identification
- Marginal tax rate analysis

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/tax-profile` | JWT | Analyze tax treatment |
| GET | `/tax-profile/{symbol}` | JWT | Get cached profile |
| POST | `/account-placement` | JWT | Recommend placement |
| GET | `/account-placement/{symbol}` | JWT | Get recommendation |
| POST | `/after-tax-yield` | JWT | Calculate after-tax yield |
| GET | `/tlh-opportunities` | JWT | Find TLH candidates |

**Dependencies:** Agent 04 (classification), PostgreSQL

**Calls:** Agent 04

**Called by:** Agent 08, 12

---

### Agent 06: Scenario Simulation

**Port:** 8006
**Schema:** `platform_shared`
**Responsibility:** Stress testing and income projection

**Overview:**
Conducts Monte Carlo simulations to project portfolio outcomes under various market conditions. Tests resilience against market crashes, interest rate changes, and dividend cuts.

**Key Features:**
- Monte Carlo income projection (12-month forward)
- Stress scenario testing (market crash, interest rate shock, dividend cut)
- Confidence interval analysis (10th, 25th, 50th, 75th, 90th percentiles)
- Sensitivity analysis (yield sensitivity, volatility impact)
- Portfolio-level simulation with position-level detail

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/scenarios/baseline` | JWT | Project baseline scenario |
| POST | `/scenarios/stress` | JWT | Run stress test |
| GET | `/scenarios/{portfolio_id}` | JWT | Get simulation results |
| POST | `/scenarios/{portfolio_id}/sensitivity` | JWT | Sensitivity analysis |

**Dependencies:** PostgreSQL, NumPy (Monte Carlo engine)

**Called by:** User dashboards (future)

---

### Agent 07: Opportunity Scanner

**Port:** 8007
**Schema:** `platform_shared`
**Responsibility:** Universe scanning and candidate ranking

**Overview:**
Scans a universe of income-generating tickers (dividend stocks, covered call ETFs, bonds, REITs, CEFs, BDCs). Calls Agent 03 to score each candidate and applies yield/quality filters. Enforces VETO gate: tickers with score < 70 are flagged.

**Key Features:**
- Configurable ticker universe definition
- Batch scoring via Agent 03
- Yield filter (customizable min/max)
- Quality filter (market cap, liquidity, age thresholds)
- Ranked candidate list with VETO flags
- Opportunity change detection (new highs, dividend cuts detected)

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/scan` | JWT | Scan universe & rank |
| GET | `/scan/{run_id}` | JWT | Get scan results |
| GET | `/candidates` | JWT | List top candidates |
| POST | `/universe` | JWT | Define custom universe |
| GET | `/opportunities/{ticker}` | JWT | Get opportunity card |

**Dependencies:** Agent 03 (scoring), PostgreSQL

**Calls:** Agent 03

**Called by:** Agent 11, 12

---

### Agent 08: Rebalancing

**Port:** 8008
**Schema:** `platform_shared`
**Responsibility:** Portfolio rebalancing analysis

**Overview:**
Analyzes portfolio positions against constraints and return targets. Calls Agent 03 for scoring and Agent 05 for tax impact. Returns prioritized rebalancing proposals without executing trades.

**Key Features:**
- Position-level analysis against constraints
- Drift detection (positions exceeding target allocation)
- Rebalancing trade suggestion (sell low-score positions, buy high-score replacements)
- Tax-loss harvesting impact (calls Agent 05)
- Multi-objective optimization (yield, tax efficiency, concentration risk)
- Transaction cost estimation

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/rebalance/{portfolio_id}` | JWT | Analyze & suggest rebalancing |
| GET | `/rebalance/{portfolio_id}` | JWT | Get proposals |
| POST | `/rebalance/{portfolio_id}/validate` | JWT | Validate proposed trades |

**Dependencies:** Agent 03 (scoring), Agent 05 (tax), PostgreSQL

**Calls:** Agent 03, Agent 05

**Called by:** Agent 12

---

### Agent 09: Income Projection

**Port:** 8009
**Schema:** `platform_shared`
**Responsibility:** 12-month forward income forecasting

**Overview:**
Produces position-level income forecasts for 12 months ahead. Enriches projections with yield data and dividend-growth trends from Agent 01's fundamentals cache.

**Key Features:**
- 12-month position-level income forecast
- Dividend growth rate estimation
- Monthly cash flow projection
- Confidence intervals (low/base/high scenarios)
- Alerts for positions at risk of dividend cuts
- Portfolio-level income summary

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/project/{portfolio_id}` | JWT | Generate 12-month forecast |
| GET | `/project/{portfolio_id}` | JWT | Get projection results |
| POST | `/project/{portfolio_id}/compare` | JWT | Compare vs. historical income |

**Dependencies:** Agent 01 (dividend history), PostgreSQL

**Calls:** Agent 01

**Called by:** User dashboards (future)

---

### Agent 10: NAV Erosion Monitor

**Port:** 8010
**Schema:** `platform_shared`
**Responsibility:** Covered call ETF NAV erosion tracking

**Overview:**
Monitors NAV erosion in covered call ETFs/CEFs/BDCs over time by comparing nav_snapshots data against Agent 03 income scores. Detects premium/discount drift and triggers alerts when NAV erosion threatens capital preservation.

**Key Features:**
- Historical NAV tracking by ticker
- Premium/discount calculation and trend analysis
- NAV erosion percentage calculation
- Comparison with income score stability
- Alert generation when erosion exceeds threshold
- Causation analysis (option premium capture, market dislocation)

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| GET | `/monitor/{symbol}` | JWT | Get NAV erosion analysis |
| POST | `/monitor/{symbol}` | JWT | Force re-analyze |
| GET | `/alerts/{symbol}` | JWT | Get alerts for symbol |
| GET | `/erosion-report` | JWT | Full erosion report (all tickers) |

**Dependencies:** Agent 01 (market data), Agent 03 (scoring), PostgreSQL

**Calls:** Agent 01, Agent 03

**Called by:** Agent 11, 12

---

### Agent 11: Smart Alert & Circuit Breakers

**Port:** 8011
**Schema:** `platform_shared`
**Responsibility:** Alert aggregation and circuit breaker detection

**Overview:**
Aggregates signals from Agents 07-10 and runs circuit-breaker detection on income scores and feature data. Routes alerts through a confirmation gate before surfacing as CONFIRMED.

**Key Features:**
- Multi-source signal aggregation
- Circuit breaker detection (score drops > 15 points, dividend cuts, NAV erosion > 5%)
- Alert confirmation logic (eliminates false positives)
- Alert routing (email, webhook, dashboard)
- Position health dashboard
- Real-time monitoring (5-minute evaluation cycles)

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| GET | `/alerts` | JWT | List alerts (all statuses) |
| GET | `/alerts/{status}` | JWT | Filter by status (NEW, CONFIRMED, RESOLVED) |
| POST | `/alerts/{alert_id}/confirm` | JWT | Manually confirm alert |
| POST | `/alerts/{alert_id}/dismiss` | JWT | Dismiss false positive |
| GET | `/circuit-breakers` | JWT | Active circuit breaker list |
| POST | `/circuit-breakers/{ticker}` | JWT | Manual circuit breaker trigger |

**Dependencies:** Agent 10 (NAV monitor), PostgreSQL

**Calls:** Agent 10

**Called by:** Agent 12

---

### Agent 12: Proposal Engine

**Port:** 8012
**Schema:** `platform_shared`
**Responsibility:** Unified recommendation synthesis

**Overview:**
Synthesizes analyst signals (Agent 02) with platform assessment (Agents 03, 04, 05) into structured proposals. Presents both lenses side by side. The platform never silently overrides an analyst.

**Key Features:**
- Analyst signal integration (Agent 02)
- Platform assessment synthesis (Agents 03-05)
- Dual-lens proposal (analyst view + platform view)
- Transparent reasoning
- User approval workflow (proposals never auto-execute)
- Proposal history & audit trail

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/proposals` | JWT | Generate proposal |
| GET | `/proposals` | JWT | List proposals |
| GET | `/proposals/{proposal_id}` | JWT | Get proposal detail |
| POST | `/proposals/{proposal_id}/approve` | JWT | User approves proposal |
| POST | `/proposals/{proposal_id}/reject` | JWT | User rejects proposal |
| GET | `/proposals/{proposal_id}/history` | JWT | Proposal change history |

**Example Response:**

```json
{
  "proposal_id": "prop-12345",
  "created_at": "2026-03-13T14:30:00Z",
  "asset": {
    "symbol": "JEPI",
    "name": "Janus Equity Premium Income ETF",
    "action": "BUY" | "SELL" | "HOLD"
  },
  "analyst_view": {
    "recommendation": "BUY",
    "analyst": "John Smith",
    "reason": "Covered call capture attractive, premium modest",
    "confidence": 0.85
  },
  "platform_view": {
    "recommendation": "BUY",
    "income_score": 78.5,
    "quality_gate_passed": true,
    "capital_preservation_score": 82.0,
    "nav_erosion_risk": "LOW",
    "tax_efficiency": "MODERATE"
  },
  "alignment": "AGREEMENT",
  "requires_user_approval": true,
  "user_action": null
}
```

**Dependencies:** Agent 02, 03, 04, 05, 11, PostgreSQL

**Calls:** Agent 02, 03, 04, 05, 11

---

## Database Schema

### Overview

All agents share a single PostgreSQL database in the `platform_shared` schema. This shared schema enables cross-service data access and maintains transactional consistency.

**Database:** PostgreSQL 15+
**Schema:** `platform_shared`
**Authentication:** HS256 JWT (inter-service); row-level security (future)

### Core Tables

#### Market Data Tables

##### `securities` — Security metadata

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `symbol` | VARCHAR(10) | No | Ticker symbol (PK) |
| `name` | VARCHAR(255) | Yes | Company/fund name |
| `asset_type` | VARCHAR(50) | Yes | STOCK, ETF, BOND, CEF, BDC, REIT |
| `sector` | VARCHAR(100) | Yes | Industry sector |
| `exchange` | VARCHAR(10) | Yes | NYSE, NASDAQ, etc. |
| `currency` | CHAR(3) | Yes | USD, EUR, etc. |
| `expense_ratio` | NUMERIC(6,4) | Yes | Annual expense ratio (for ETFs) |
| `aum_millions` | NUMERIC(15,2) | Yes | Assets under management in millions |
| `created_at` | TIMESTAMPTZ | No | Insert timestamp |
| `updated_at` | TIMESTAMPTZ | No | Last update timestamp |

**Primary Key:** `symbol`
**Owned by:** Agent 01
**Indexes:** `ix_securities_asset_type`, `ix_securities_sector`

##### `price_history` — Historical OHLCV data

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `symbol` | VARCHAR(10) | No | Ticker symbol (FK) |
| `date` | DATE | No | Date of price bar |
| `open_price` | NUMERIC(12,4) | Yes | Opening price |
| `high_price` | NUMERIC(12,4) | Yes | Daily high |
| `low_price` | NUMERIC(12,4) | Yes | Daily low |
| `close_price` | NUMERIC(12,4) | Yes | Closing price |
| `adjusted_close` | NUMERIC(12,4) | Yes | Dividend/split adjusted |
| `volume` | BIGINT | Yes | Trading volume |
| `data_source` | VARCHAR(50) | No | API provider (polygon, fmp, yfinance, etc.) |
| `created_at` | TIMESTAMPTZ | No | Insert timestamp |

**Primary Key:** `id`
**Unique Constraint:** `(symbol, date)` — one record per ticker per date
**Owned by:** Agent 01
**Indexes:** `ix_price_history_symbol`, `ix_price_history_date`

##### `features_historical` — Cached fundamental features

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `symbol` | VARCHAR(10) | No | Ticker symbol (FK) |
| `feature_date` | DATE | No | Date feature was measured |
| `yield_percentage` | NUMERIC(8,4) | Yes | Dividend yield (%) |
| `dividend_per_share` | NUMERIC(12,4) | Yes | Annual dividend per share |
| `payout_ratio` | NUMERIC(6,4) | Yes | Payout ratio (0-1 or 0-100 normalized) |
| `pe_ratio` | NUMERIC(10,2) | Yes | Price-to-earnings |
| `debt_to_equity` | NUMERIC(10,4) | Yes | Debt-to-equity ratio |
| `free_cash_flow` | BIGINT | Yes | Free cash flow in millions |
| `market_cap` | BIGINT | Yes | Market cap in millions |
| `dividend_growth_rate` | NUMERIC(8,4) | Yes | YoY dividend growth rate |
| `expense_ratio` | NUMERIC(6,4) | Yes | Annual expense ratio (for ETFs) |
| `created_at` | TIMESTAMPTZ | No | Insert timestamp |

**Primary Key:** `id`
**Owned by:** Agent 01 (data collection)
**Read by:** Agent 03, 06, 09
**Indexes:** `ix_features_historical_symbol_date`

##### `covered_call_etf_metrics` — Covered call ETF analysis

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | SERIAL | No | Primary key |
| `ticker` | VARCHAR(20) | No | ETF ticker |
| `data_date` | DATE | No | Date of measurement |
| `nav` | FLOAT | No | Net asset value |
| `market_price` | FLOAT | No | Market price per share |
| `premium_discount_pct` | FLOAT | Yes | Premium/discount to NAV (%) |
| `monthly_distribution` | FLOAT | Yes | Monthly distribution per share |
| `distribution_yield_ttm` | FLOAT | Yes | Trailing twelve-month yield (%) |
| `roc_percentage` | FLOAT | Yes | Return of capital % |
| `monthly_premium_yield` | FLOAT | Yes | Option premium yield (%) |
| `implied_volatility` | FLOAT | Yes | IV of underlying |
| `underlying_return_1m` | FLOAT | Yes | 1-month underlying return (%) |
| `underlying_volatility_30d` | FLOAT | Yes | 30-day underlying volatility (%) |
| `expense_ratio` | FLOAT | Yes | Annual expense ratio (%) |
| `leverage_ratio` | FLOAT | No | Leverage multiplier (default: 1.0) |
| `created_at` | TIMESTAMP | No | Insert timestamp |
| `updated_at` | TIMESTAMP | No | Last update timestamp |

**Primary Key:** `id`
**Unique Constraint:** `(ticker, data_date)`
**Owned by:** NAV erosion data collector
**Used by:** Agent 03 (NAV erosion penalty), Agent 10 (erosion tracking)
**Indexes:** `idx_cc_etf_ticker_date`, `idx_cc_etf_date`

#### Income Scoring Tables

##### `scoring_runs` — Audit log of scoring batches

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `run_timestamp` | TIMESTAMPTZ | No | When run was executed |
| `symbols_scored` | INTEGER | No | Count of symbols scored |
| `method` | VARCHAR(50) | No | Scoring method used (income_fortress, sais, blended) |
| `total_duration_seconds` | NUMERIC(10,4) | No | Total execution time |
| `avg_score` | NUMERIC(5,2) | Yes | Mean score across run |
| `quality_gate_pass_rate` | NUMERIC(5,4) | Yes | Fraction passing VETO |
| `created_by` | VARCHAR(100) | Yes | Service/user that triggered run |

**Primary Key:** `id`
**Owned by:** Agent 03
**Indexes:** `ix_scoring_runs_timestamp`

##### `asset_scores` — Individual asset scores

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `symbol` | VARCHAR(10) | No | Ticker symbol |
| `scoring_run_id` | UUID | No | FK to scoring_runs |
| `asset_type` | VARCHAR(50) | No | STOCK, ETF, BOND, etc. |
| `method` | VARCHAR(50) | No | Scoring method |
| `income_score` | NUMERIC(5,2) | No | Income component score (0-100) |
| `capital_preservation_score` | NUMERIC(5,2) | No | Capital preservation score (0-100) |
| `blended_score` | NUMERIC(5,2) | No | Final score if blended method |
| `quality_gate_passed` | BOOLEAN | No | Whether score >= 70 (VETO gate) |
| `components` | JSONB | Yes | Detailed scoring breakdown |
| `confidence` | NUMERIC(5,4) | No | Model confidence (0-1) |
| `scored_at` | TIMESTAMPTZ | No | Timestamp |

**Primary Key:** `id`
**Foreign Keys:** `(symbol) -> securities`, `(scoring_run_id) -> scoring_runs`
**Owned by:** Agent 03
**Read by:** Agents 07, 08, 11, 12
**Indexes:** `ix_asset_scores_symbol`, `ix_asset_scores_run_id`, `(symbol, scored_at DESC)`

#### Classification Tables

##### `asset_classifications` — Asset type and attributes

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `symbol` | VARCHAR(10) | No | Ticker symbol (FK) |
| `asset_type` | VARCHAR(50) | No | STOCK, ETF, BOND, CEF, BDC, REIT |
| `is_covered_call_etf` | BOOLEAN | No | True if covered call strategy detected |
| `is_dividend_stock` | BOOLEAN | No | True if dividend-paying stock |
| `dividend_frequency` | VARCHAR(50) | Yes | MONTHLY, QUARTERLY, ANNUALLY |
| `dividend_safety_score` | NUMERIC(5,2) | Yes | Sustainability of dividend (0-100) |
| `entry_price_score` | NUMERIC(5,2) | Yes | Entry price valuation score (0-100) |
| `classified_at` | TIMESTAMPTZ | No | Classification timestamp |

**Primary Key:** `id`
**Foreign Keys:** `(symbol) -> securities`
**Owned by:** Agent 04
**Read by:** Agents 03, 05, 12
**Indexes:** `ix_asset_classifications_symbol`

#### Tax Optimization Tables

##### `tax_profiles` — Tax treatment for each asset

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `symbol` | VARCHAR(10) | No | Ticker symbol |
| `distribution_type` | VARCHAR(50) | No | ROC, QUALIFIED, ORDINARY, SECTION_1256 |
| `qualified_dividend_pct` | NUMERIC(5,4) | No | Fraction of dividends that are qualified (0-1) |
| `roc_pct` | NUMERIC(5,4) | No | Fraction that is return of capital (0-1) |
| `ordinary_income_pct` | NUMERIC(5,4) | No | Fraction that is ordinary income (0-1) |
| `is_section_1256` | BOOLEAN | No | True if 60/40 tax treatment applies |
| `account_placement_recommendation` | VARCHAR(50) | Yes | TAXABLE, TAX_DEFERRED, TAX_FREE |
| `after_tax_yield_at_rate` | JSONB | Yes | After-tax yield at various marginal rates |
| `analyzed_at` | TIMESTAMPTZ | No | Analysis timestamp |

**Primary Key:** `id`
**Foreign Keys:** `(symbol) -> securities`
**Owned by:** Agent 05
**Read by:** Agents 08, 12
**Indexes:** `ix_tax_profiles_symbol`

#### Portfolio & Position Tables (Future)

Future versions will add:
- `portfolios` — user portfolios
- `positions` — portfolio holdings
- `transactions` — buy/sell history
- `proposals` — pending/executed recommendations

#### Alert & Monitoring Tables

##### `alerts` — System-generated alerts

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | UUID | No | Primary key |
| `symbol` | VARCHAR(10) | No | Ticker symbol |
| `alert_type` | VARCHAR(50) | No | DIVIDEND_CUT, NAV_EROSION, SCORE_DROP, etc. |
| `status` | VARCHAR(50) | No | NEW, CONFIRMED, RESOLVED, DISMISSED |
| `severity` | VARCHAR(20) | No | INFO, WARNING, CRITICAL |
| `message` | TEXT | No | Alert description |
| `detected_at` | TIMESTAMPTZ | No | When alert was detected |
| `confirmed_at` | TIMESTAMPTZ | Yes | When confirmed (if applicable) |
| `resolved_at` | TIMESTAMPTZ | Yes | When resolved (if applicable) |

**Primary Key:** `id`
**Owned by:** Agent 11
**Indexes:** `ix_alerts_symbol`, `ix_alerts_status`, `ix_alerts_detected_at`

### Relationships & Constraints

```
securities (symbol PK)
    ├── price_history (symbol FK)
    ├── features_historical (symbol FK)
    ├── asset_classifications (symbol FK)
    ├── asset_scores (symbol FK)
    ├── tax_profiles (symbol FK)
    └── alerts (symbol FK)

scoring_runs (id PK)
    └── asset_scores (scoring_run_id FK)
```

### Key Design Decisions

1. **Shared schema** — Simplifies data interchange; trades off isolation for convenience (multi-tenant isolation handled at application layer)
2. **JSONB columns** — `components` in `asset_scores`, `after_tax_yield_at_rate` in `tax_profiles` allow flexible, extensible structures
3. **Fire-and-forget writes** — Async upserts don't block API responses
4. **Indexed date lookups** — `(symbol, date DESC)` indexes on historical tables for fast "latest value" queries
5. **No foreign key cascades** — Delete-on-cascade avoided; orphaned records cleaned up by periodic jobs

---

## Authentication & Security

### Authentication Scheme: JWT HS256

All agent-to-agent and user-to-agent API calls require **HS256 JWT Bearer tokens**.

#### Token Structure

Tokens are standard JWT format: `<header>.<payload>.<signature>`

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "sub": "user-123",  // subject (user/service ID)
  "exp": 1746123456, // expiration time (Unix timestamp)
  "iat": 1746119856  // issued at time
}
```

**Signature:**
HMAC-SHA256 of `header.payload` signed with `JWT_SECRET` environment variable.

#### Token Generation

**Python (stdlib only):**

```python
import base64
import hashlib
import hmac
import json
import time

def generate_token(secret: str, user_id: str, expires_in_seconds: int = 3600) -> str:
    """Generate HS256 JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).rstrip(b"=").decode()

    now = int(time.time())
    payload = {
        "sub": user_id,
        "exp": now + expires_in_seconds,
        "iat": now,
    }
    payload_encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    message = f"{header_encoded}.{payload_encoded}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).rstrip(b"=").decode()

    return f"{header_encoded}.{payload_encoded}.{signature}"

# Usage
token = generate_token("your-jwt-secret", "user-123", expires_in_seconds=3600)
```

#### Token Verification

All agents implement the same verification logic (in `auth.py`):

```python
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """
    Verify HS256 JWT token.
    - Checks signature
    - Validates expiration
    - Returns payload
    """
    secret = os.environ.get("JWT_SECRET")
    token = credentials.credentials

    # Parse token
    header_b64, payload_b64, sig_b64 = token.split(".")

    # Verify signature
    message = f"{header_b64}.{payload_b64}".encode()
    expected_sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).rstrip(b"=").decode()

    if not hmac.compare_digest(expected_sig, sig_b64):
        raise HTTPException(status_code=401, detail="Invalid token")

    # Decode payload
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))

    # Check expiration
    if payload["exp"] < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return payload
```

#### Usage in API Calls

**cURL:**
```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/stocks/JEPI/price
```

**Python (requests):**
```python
import requests

token = generate_token(secret, "user-123")
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8001/stocks/JEPI/price", headers=headers)
```

**Python (httpx):**
```python
import httpx

token = generate_token(secret, "user-123")
headers = {"Authorization": f"Bearer {token}"}
async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:8001/stocks/JEPI/price", headers=headers)
```

### Security Best Practices

1. **Keep JWT_SECRET secure** — Store in environment variables, never commit to git
2. **Use short expiration** — Default 1 hour; refresh tokens not yet implemented
3. **HTTPS only** — All production traffic encrypted (TLS 1.2+)
4. **Rate limiting** — 3-tier: IP-based, user-based, service-based (future)
5. **Input validation** — All requests validated via Pydantic models
6. **SQL injection prevention** — All DB queries use parameterized statements (SQLAlchemy)
7. **XSS protection** — API responses are JSON only (no HTML templates)
8. **CORS policy** — Restricted to allowed origins (configurable per environment)
9. **Non-root containers** — All Docker containers run as non-root user
10. **Database isolation** — Row-level security (RLS) planned for multi-tenant future

### CORS Configuration

**Development:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.incomefortress.com",
        "https://api.incomefortress.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## Deployment

### Deployment Architecture

**Infrastructure:**
- **Compute:** DigitalOcean Droplet (4GB RAM, 2 vCPUs, 80GB SSD)
- **Database:** PostgreSQL 15 (managed)
- **Cache:** Redis 7 (managed)
- **Container Orchestration:** Docker Compose
- **Reverse Proxy:** Nginx (SSL/TLS, rate limiting)
- **DNS:** Custom domain (CNAME to DigitalOcean)
- **Backups:** PostgreSQL snapshots (daily)

### Running Services Locally

#### Prerequisites

```bash
# Check versions
docker --version        # Docker 20.10+
docker-compose --version # Docker Compose 2.0+
python --version       # Python 3.11+
```

#### Quick Start

```bash
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

# Copy example environment
cp .env.example .env

# Edit environment variables
nano .env

# Build images
docker-compose build

# Start services
docker-compose up -d

# Verify health
curl http://localhost:8001/health
curl http://localhost:8002/health
# ... etc for all 12 agents

# View logs
docker-compose logs -f market-data-service
docker-compose logs -f agent-03-income-scoring
# ... etc

# Stop services
docker-compose down
```

#### Environment File (`.env`)

```bash
# Database
DATABASE_URL=postgresql://user:password@postgres:5432/income_platform

# Cache
REDIS_URL=redis://redis:6379

# External APIs
POLYGON_API_KEY=your_polygon_key
FMP_API_KEY=your_fmp_key
MARKET_DATA_API_KEY=your_alpha_vantage_key
FINNHUB_API_KEY=your_finnhub_key
ANTHROPIC_API_KEY=your_anthropic_key
APIDOJO_SA_API_KEY=your_seeking_alpha_key

# Auth
JWT_SECRET=your-dev-secret-change-in-production

# Logging
LOG_LEVEL=INFO

# Service config
ENVIRONMENT=development
```

### Docker Compose Configuration

The `docker-compose.yml` file orchestrates all 12 agents:

```yaml
version: '3.8'

services:
  # Agent 01: Market Data
  market-data-service:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: market-data-service
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      POLYGON_API_KEY: ${POLYGON_API_KEY}
      FMP_API_KEY: ${FMP_API_KEY}
      JWT_SECRET: ${JWT_SECRET}
      SERVICE_PORT: 8001
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  # Agent 02: Newsletter Ingestion
  agent-02-newsletter-ingestion:
    build:
      context: src/agent-02-newsletter-ingestion
      dockerfile: Dockerfile
    depends_on:
      market-data-service:
        condition: service_healthy
    ports:
      - "8002:8002"
    # ... (similar structure for all agents)

  # ... (Agents 03-12)

  # PostgreSQL
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: income_platform
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### Health Checks

All services implement `/health` endpoint for container orchestration:

```bash
# Agent 01 health
curl http://localhost:8001/health
# Response: {"status": "healthy", "database": "connected", "cache": "connected"}

# Other agents
curl http://localhost:8002/health
curl http://localhost:8003/health
# ... etc
```

### Service Dependencies

Startup order is enforced via `depends_on` clauses in docker-compose.yml:

```
Agent 01 (Market Data)
    ├── Agent 02 (Newsletter)
    ├── Agent 03 (Income Scoring)
    │   ├── Agent 04 (Classification)
    │   ├── Agent 07 (Opportunity Scanner)
    │   └── Agent 08 (Rebalancing)
    ├── Agent 05 (Tax Optimization)
    │   └── Agent 08 (Rebalancing)
    ├── Agent 06 (Scenario Simulation)
    ├── Agent 09 (Income Projection)
    ├── Agent 10 (NAV Monitor)
    │   └── Agent 11 (Smart Alerts)
    ├── Agent 11 (Smart Alerts)
    │   └── Agent 12 (Proposal Engine)
    └── Agent 12 (Proposal Engine)
```

### Scaling Considerations

**Horizontal scaling (future):**
- Add replicas of stateless agents (Agent 01-12)
- Use load balancer (HAProxy/Nginx) in front
- Shared PostgreSQL database bottleneck → consider read replicas

**Vertical scaling:**
- Increase Droplet RAM (currently 4GB)
- Increase Droplet CPU (currently 2 vCPU)
- Upgrade PostgreSQL/Redis to larger managed instances

---

## Configuration & Environment Variables

### Environment Variables by Service

#### All Services

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | Yes | — | Redis/Valkey connection string |
| `JWT_SECRET` | Yes | — | Shared JWT signing secret (HS256) |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `ENVIRONMENT` | No | production | Execution environment (development, staging, production) |

#### Agent 01 (Market Data)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POLYGON_API_KEY` | No | — | Polygon.io API key (primary) |
| `FMP_API_KEY` | No | — | Financial Modeling Prep API key (secondary) |
| `MARKET_DATA_API_KEY` | Yes | — | Alpha Vantage API key (legacy reference) |
| `FINNHUB_API_KEY` | No | — | Finnhub API key (credit ratings) |
| `SERVICE_PORT` | No | 8001 | Port to listen on |
| `CACHE_TTL_CURRENT_PRICE` | No | 300 | Cache TTL for current prices (seconds) |

#### Agent 02 (Newsletter Ingestion)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic Claude API key |
| `APIDOJO_SA_API_KEY` | No | — | Seeking Alpha API key (APIDojo) |
| `OPENAI_API_KEY` | No | — | OpenAI API key (fallback LLM) |
| `FMP_API_KEY` | No | — | Financial Modeling Prep API key |
| `SERVICE_TOKEN` | Yes | — | Inter-service auth token |

#### Agent 03 (Income Scoring)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MARKET_DATA_SERVICE_URL` | Yes | http://market-data-service:8001 | Agent 01 URL |
| `NEWSLETTER_SERVICE_URL` | Yes | http://agent-02-newsletter-ingestion:8002 | Agent 02 URL |
| `ASSET_CLASSIFICATION_SERVICE_URL` | Yes | http://agent-04-asset-classification:8004 | Agent 04 URL |
| `ADMIN_USERNAME` | No | admin | Admin username (future) |
| `ADMIN_PASSWORD` | No | — | Admin password (future) |

#### Agent 05 (Tax Optimization)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ASSET_CLASSIFICATION_URL` | Yes | http://agent-04-asset-classification:8004 | Agent 04 URL |

#### Agent 07 (Opportunity Scanner)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INCOME_SCORING_URL` | Yes | http://agent-03-income-scoring:8003 | Agent 03 URL |

#### Agent 08 (Rebalancing)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INCOME_SCORING_URL` | Yes | http://agent-03-income-scoring:8003 | Agent 03 URL |
| `TAX_OPTIMIZATION_URL` | Yes | http://tax-optimization-service:8005 | Agent 05 URL |

#### Agent 12 (Proposal Engine)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENT02_URL` | Yes | http://agent-02-newsletter-ingestion:8002 | Agent 02 URL |
| `AGENT03_URL` | Yes | http://agent-03-income-scoring:8003 | Agent 03 URL |
| `AGENT04_URL` | Yes | http://agent-04-asset-classification:8004 | Agent 04 URL |
| `AGENT05_URL` | Yes | http://tax-optimization-service:8005 | Agent 05 URL |

### Configuration Files

Each service has a `config.py` file in its root directory:

```python
# Example: src/market-data-service/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_name: str = "market-data-service"
    service_port: int = 8001
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    polygon_api_key: str = ""
    fmp_api_key: str = ""
    market_data_api_key: str = ""
    jwt_secret: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

---

## Inter-Service Communication

### HTTP Request Pattern

Services use **httpx** (async HTTP client) to call other services:

```python
import httpx

async def call_agent_03(symbol: str, token: str) -> dict:
    """Call Agent 03 to score an asset."""
    agent_03_url = os.environ.get("INCOME_SCORING_URL", "http://agent-03-income-scoring:8003")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{agent_03_url}/scores/evaluate",
            json={"symbol": symbol},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
```

### Service Call Graph

```
User Request
    ↓
Agent 12 (Proposal Engine) ← User-facing
    ├→ Agent 02 (Newsletter) — analyst signals
    ├→ Agent 03 (Income Scoring) — platform assessment
    │   ├→ Agent 01 (Market Data) — current prices, fundamentals
    │   └→ Agent 04 (Classification) — asset classification
    ├→ Agent 04 (Asset Classification)
    ├→ Agent 05 (Tax Optimization)
    │   └→ Agent 04 (Classification)
    ├→ Agent 08 (Rebalancing)
    │   ├→ Agent 03 (Income Scoring)
    │   └→ Agent 05 (Tax Optimization)
    ├→ Agent 11 (Smart Alerts)
    │   └→ Agent 10 (NAV Monitor)
    │       └→ Agent 03 (Income Scoring)
    └→ Agent 10 (NAV Monitor)
        └→ Agent 03 (Income Scoring)

Agent 07 (Opportunity Scanner)
    └→ Agent 03 (Income Scoring)

Agent 09 (Income Projection)
    └→ Agent 01 (Market Data)

Agent 06 (Scenario Simulation)
    ├→ Agent 01 (Market Data)
    └→ (Monte Carlo engine — no external calls)
```

### Error Handling

All inter-service calls include retry logic and timeout protection:

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def call_with_retry(url: str, token: str, timeout: float = 30.0) -> dict:
    """Call service with exponential backoff retry."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"Timeout calling {url}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} from {url}")
            raise
```

### Circuit Breaker Pattern (Future)

```python
# Planned: fallback strategies when downstream service is degraded
if service_down:
    # Use cached result if available
    cached = await cache_manager.get(f"cache:{symbol}")
    if cached:
        return cached
    # Otherwise return degraded response
    return {"error": "service_unavailable", "status": "degraded"}
```

---

## API Reference

### Base URLs

| Environment | URL |
|-------------|-----|
| **Local** | http://localhost:{port} |
| **Docker Compose** | http://{service_name}:{port} |
| **DigitalOcean Production** | https://api.incomefortress.com |

### Request/Response Format

**Content-Type:** `application/json`

**All requests (except `/health`) require:**
```
Authorization: Bearer <token>
```

### Standard Response Format

**Success (2xx):**
```json
{
  "data": {...},
  "status": "success",
  "timestamp": "2026-03-13T14:30:00Z"
}
```

**Error (4xx/5xx):**
```json
{
  "detail": "Error description",
  "status": "error",
  "timestamp": "2026-03-13T14:30:00Z"
}
```

### API Versioning

Currently v1. Future: prefix routes with `/api/v1`, `/api/v2`, etc.

### Rate Limiting (Future)

Planned 3-tier rate limiting:

| Tier | Limit | Window |
|------|-------|--------|
| **IP-based** | 1000 req/min | 1 minute |
| **User-based** | 500 req/min | 1 minute |
| **Service-based** | 100 req/min | 1 minute |

---

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Symptom:** `docker-compose up` returns error

**Root causes:**
- Missing environment variables in `.env`
- Database connection failed
- Redis connection failed
- Port already in use

**Solutions:**
```bash
# Check environment variables
cat .env | grep DATABASE_URL
cat .env | grep REDIS_URL
cat .env | grep JWT_SECRET

# Check if ports are available
netstat -an | grep 8001
netstat -an | grep 5432

# View service logs
docker-compose logs market-data-service
docker-compose logs postgres
docker-compose logs redis
```

#### 2. Database Connection Error

**Symptom:** `psycopg2.OperationalError: could not connect to server`

**Solutions:**
```bash
# Check database is running
docker-compose ps postgres

# Check database is ready
docker-compose logs postgres | grep "database system is ready"

# Wait for database startup
docker-compose up -d postgres
sleep 10
docker-compose up -d

# Verify connection manually
psql postgresql://user:password@localhost:5432/income_platform
```

#### 3. Redis Connection Error

**Symptom:** `redis.exceptions.ConnectionError: Error 111 connecting`

**Solutions:**
```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check if port is available
lsof -i :6379
```

#### 4. JWT Token Invalid

**Symptom:** `401 Unauthorized: Invalid token`

**Solutions:**
```bash
# Verify JWT_SECRET matches across all services
grep JWT_SECRET .env

# Generate new token with same secret
python -c "
import base64, hashlib, hmac, json, time

secret = 'your-jwt-secret'
header = {'alg': 'HS256', 'typ': 'JWT'}
payload = {'sub': 'user-123', 'exp': int(time.time()) + 3600}

header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
message = f'{header_b64}.{payload_b64}'.encode()
sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).rstrip(b'=').decode()

print(f'{header_b64}.{payload_b64}.{sig}')
"
```

#### 5. Service-to-Service Communication Failed

**Symptom:** Agent 12 cannot call Agent 03

**Root causes:**
- Service URL environment variable incorrect
- Downstream service not healthy
- JWT token mismatch
- Network connectivity issue

**Solutions:**
```bash
# Check environment variables
docker-compose exec agent-12-proposal env | grep AGENT03_URL

# Test connectivity from one service to another
docker-compose exec agent-12-proposal curl -H "Authorization: Bearer $TOKEN" http://agent-03-income-scoring:8003/health

# Check service is healthy
curl http://localhost:8003/health
```

#### 6. Database Schema Not Initialized

**Symptom:** Table not found errors

**Solutions:**
```bash
# Run migrations
docker-compose exec market-data-service python -m alembic upgrade head

# Or manually create schema
docker-compose exec postgres psql -U user -d income_platform -c "
CREATE SCHEMA IF NOT EXISTS platform_shared;
CREATE TABLE platform_shared.securities (...);
"
```

### Debug Mode

Enable debug logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in .env
LOG_LEVEL=DEBUG

# Restart services
docker-compose down
docker-compose up -d
```

### Health Check Commands

```bash
# Check all services
for port in 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011 8012; do
  echo "Agent on port $port:"
  curl -s http://localhost:$port/health | python -m json.tool
done

# Check database
psql postgresql://user:password@localhost:5432/income_platform -c "\dt platform_shared.*"

# Check Redis
redis-cli -h localhost -p 6379 PING
redis-cli -h localhost -p 6379 INFO stats
```

### Performance Profiling

```python
# Example: add timing middleware to FastAPI
from time import time

@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"{request.method} {request.url.path} took {process_time:.3f}s")
    return response
```

---

## Appendix

### Useful Commands

```bash
# View all services and status
docker-compose ps

# View logs for specific service
docker-compose logs -f agent-03-income-scoring

# View logs for all services
docker-compose logs -f

# Execute command in service container
docker-compose exec market-data-service python -c "import sys; print(sys.version)"

# Restart a single service
docker-compose restart agent-03-income-scoring

# Stop all services
docker-compose down

# Remove all volumes (DESTRUCTIVE)
docker-compose down -v

# Rebuild image for single service
docker-compose build market-data-service

# Pull latest image
docker-compose pull
```

### References

- **FastAPI Documentation:** https://fastapi.tiangolo.com
- **PostgreSQL Documentation:** https://www.postgresql.org/docs
- **Redis Documentation:** https://redis.io/docs
- **Docker Compose Documentation:** https://docs.docker.com/compose
- **JWT RFC 7519:** https://tools.ietf.org/html/rfc7519

---

**Document Version:** 1.0.0
**Last Updated:** March 2026
**Maintained by:** Income Fortress Platform Team
**Status:** Production

For updates and changes, refer to `/docs/CHANGELOG.md`
