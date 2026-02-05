# Reference Architecture - Tax-Efficient Income Investment Platform

**Version:** 1.0.0  
**Date:** 2026-01-28  
**Status:** Design Complete

## Executive Summary

The Tax-Efficient Income Investment Platform is a comprehensive AI-powered system designed to help investors build and manage income-generating portfolios with a focus on capital preservation, tax efficiency, and sustainable income. The platform employs 22 specialized AI agents, manages data across 97 database tables, and exposes 88+ REST API endpoints.

### Design Principles

1. **Capital Safety First** - 70% safety threshold with VETO power overrides all income considerations
2. **Income Generation Second** - Maximize sustainable income only after capital safety is ensured
3. **Avoid Yield Traps** - Intelligent analysis to detect unsustainable high yields
4. **Tax Efficiency** - Comprehensive tax optimization across account types
5. **User Control** - All major actions require user approval via proposal workflow

---

## System Architecture Overview

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
│  React Web App • React Native Mobile • Claude Code CLI       │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                          │
│          Kong Gateway • Rate Limiting • Auth • TLS           │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Application Services Layer                    │
│   FastAPI Microservices • WebSocket Server • File Service   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI Agent Layer (22 Agents)                 │
│   Data Processing • Scoring • Analysis • Recommendations    │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                        │
│   Temporal Workflows • Prefect Flows • N8N • Redis Streams  │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                               │
│   PostgreSQL (Supabase) • Redis • S3 • pgvector             │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  External Integrations                        │
│  Plaid • Alpaca • Schwab • yfinance • Anthropic • OpenAI    │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Data Model (97 Tables)

**Core Portfolio Management (10 tables)**
- portfolios, portfolio_holdings, portfolio_configurations
- portfolio_preferences, portfolio_daily_snapshot, holdings_daily_snapshot
- holdings_transactions, holdings_dividend_history
- portfolio_rebalance_history, portfolio_optimization_history

**Asset Classification (3 tables)**
- asset_classes, etf_look_through_data, sector_exposure_analysis

**Analyst Intelligence (5 tables)**
- analyst_profiles, analyst_articles, analyst_recommendations
- analyst_performance_evaluations, analyst_reasoning_frameworks

**Scoring & Prediction (3 tables)**
- stock_scores_history, stock_predictions, model_performance_metrics

**Alerts & Monitoring (15 tables)**
- concern_tracker, alerts, alert_rules, alert_configurations
- notification_inbox, notification_channels, notification_preferences
- notification_delivery_log, notification_templates
- optimization_proposals, proposal_execution_log
- alert_effectiveness_tracking, alert_false_positive_log
- dividend_cut_concern_history, nav_erosion_concern_history

**Simulation (4 tables)**
- portfolio_simulations, simulation_paths, simulation_risk_metrics
- simulation_distribution_data, safe_withdrawal_analysis

**Time-Series Data (5 tables)**
- market_data_daily, market_sentiment_daily, dividend_calendar
- earnings_calendar, exchange_rates

**Analytics (8 tables)**
- tenant_financial_summary, tenant_income_breakdown
- tenant_tax_projections, tenant_performance_kpis
- financial_goals, goal_progress_history, goal_milestones
- goal_recommendations

**Tax Processing (7 tables)**
- tax_documents, tax_document_analysis, tax_patterns_learned
- tax_optimization_suggestions, tax_loss_harvesting_opportunities
- wash_sale_tracker, asset_location_optimization

**External Integrations (14 tables)**
- connected_accounts, plaid_items, plaid_accounts, plaid_transactions
- alpaca_accounts, alpaca_orders, alpaca_positions
- schwab_accounts, schwab_orders, schwab_positions
- integration_sync_log, webhook_events, webhook_delivery_log
- api_call_log

**Security & Compliance (10 tables)**
- tenants, users, user_consents, api_keys, api_key_usage_log
- active_sessions, session_activity_log, trusted_devices
- data_subject_requests, roles

**Advanced Features (7 tables)**
- backtests, backtest_trades, backtest_daily_snapshots, backtest_metrics
- drip_pending_transactions, drip_execution_history, drip_configurations
- rebalancing_schedules, rebalancing_history
- generated_documents

**Utilities (6 tables)**
- market_holidays, benchmark_data, platform_configuration
- feature_flags, scheduled_jobs, audit_log

**Total: 97 Tables**

### 2. AI Agent Architecture (22 Agents)

**Data Processing Agents (5)**
1. **Asset Class Identifier** - Classifies securities by asset class
2. **ETF Look-Through Analyzer** - Performs 80/20 analysis on ETFs
3. **Analyst Reasoning Extractor** - Extracts frameworks from analyst content
4. **Tax Document Processor** - Processes and learns from tax documents
5. **Market Sentiment Analyzer** - Analyzes market sentiment signals

**Scoring Agents (4)**
6. **Capital Protection Scorer** - Primary safety scoring (70% threshold, VETO)
7. **Portfolio Fit Scorer** - Scores fit within portfolio context
8. **Asset Class-Specific Scorers** - 9 specialized scorers for each asset class
9. **Conflict Resolver** - Resolves scoring conflicts across agents

**Analysis Agents (4)**
10. **Portfolio Analyzer** - Comprehensive portfolio analysis
11. **Tenant Risk Aggregator** - Cross-portfolio risk aggregation
12. **Portfolio Simulator** - What-if scenario simulation
13. **Market Scenario Predictor** - Stress testing under scenarios
14. **Stock Evaluation Agent** - Single stock deep evaluation

**Recommendation Agents (3)**
15. **Optimization Proposal Generator** - Generates trade/rebalancing proposals
16. **Alert & Monitoring Agent** - Monitors portfolios and generates alerts
17. **Market Scanner** - Scans market for opportunities
18. **Trade Proposal Generator** - Generates buy/sell proposals

**Support Agents (4)**
19. **Price Target Calculator** - Calculates entry/exit targets
20. **Explanation Generator** - Generates human-readable explanations
21. **Composite Framework Generator** - Synthesizes analyst frameworks
22. **Conversational Agent** - Natural language interface (Claude)

### 3. API Architecture (88+ Endpoints)

**Authentication (3)**: login, refresh, me  
**Portfolios (10)**: CRUD, analyze, simulate, currency, configurations  
**Holdings (4)**: CRUD, history  
**Stocks (3)**: evaluate, scan, price-target  
**Trading (3)**: place, get, history  
**Alerts (11)**: CRUD rules, templates, configurations  
**Proposals (4)**: CRUD, execute  
**Analytics (4)**: overview, performance, fx-impact  
**Tax (3)**: documents, projections  
**Integrations (3)**: accounts, sync  
**Goals (6)**: CRUD, simulate, recommendations, milestones  
**Simulations (8)**: monte-carlo, retirement, safe-withdrawal-rate, historical-bootstrap  
**Backtesting (4)**: CRUD, run  
**DRIP (5)**: configuration, pending, execute, history, accumulated-cash  
**Rebalancing (4)**: schedule, check, execute, history  
**Documents (3)**: generate, list, download  
**GDPR (4)**: data-request, export, consents  
**Admin (8)**: tenants, rate-limits, legal-holds, analysts  
**Public (4)**: analysts, compare, articles  
**WebSocket**: Real-time updates on 6 channels

---

## Data Flow Architecture

### Critical Data Flows

#### 1. Account Sync Flow
```
User Connects Account (Plaid/Alpaca/Schwab)
  ↓
Fetch Holdings & Transactions
  ↓
Asset Class Identifier → Classify Securities
  ↓
ETF Look-Through (if applicable) → Analyze Underlying
  ↓
Store in portfolio_holdings + holdings_transactions
  ↓
Trigger Portfolio Analysis
```

#### 2. Portfolio Analysis Flow
```
Trigger Analysis (Manual/Scheduled/Post-Sync)
  ↓
Portfolio Analyzer Agent (Temporal Workflow)
  ↓
├→ Capital Protection Scorer (All Holdings)
├→ Portfolio Fit Scorer (Context-Aware)
├→ Asset Class Scorers (Specialized)
└→ Conflict Resolver (Reconcile)
  ↓
Calculate Aggregates (Yield, Safety, Allocation)
  ↓
Tenant Risk Aggregator (Cross-Portfolio)
  ↓
Store Results + Update Dashboard
```

#### 3. Alert Generation Flow
```
Alert & Monitoring Agent (Scheduled: Every 4 Hours)
  ↓
Load Alert Rules (User-Configured)
  ↓
For Each Portfolio:
  ├→ Check Dividend Cut Concerns (Multi-Day Confirmation)
  ├→ Check NAV Erosion (ETFs)
  ├→ Check Safety Score Drops
  ├→ Check Allocation Breaches
  └→ Check Tax Events
  ↓
Generate Alerts (concern_tracker → alerts)
  ↓
Send Notifications (Email, Push, In-App)
```

#### 4. Trade Execution Flow
```
Optimization Proposal Generator
  ↓
Generate Proposal (Buy/Sell Lists)
  ↓
Store in optimization_proposals (Status: Pending)
  ↓
User Reviews + Approves/Rejects/Modifies
  ↓
If Approved:
  ↓
Trade Execution Service
  ↓
├→ Place Orders (Alpaca/Schwab API)
├→ Monitor Fills
└→ Update Holdings
  ↓
Record in proposal_execution_log
  ↓
Trigger Portfolio Re-Analysis
```

#### 5. Tax Document Processing Flow
```
User Uploads Tax Document (PDF/Image)
  ↓
Store in tax_documents (Status: Processing)
  ↓
Tax Document Processor Agent
  ↓
├→ OCR Extraction (if needed)
├→ Parse Tax Forms (1099-DIV, K-1, etc.)
├→ Extract Patterns (Asset Location, Tax Treatment)
└→ Generate Insights
  ↓
Store in tax_document_analysis
  ↓
Update tax_patterns_learned
  ↓
Generate tax_optimization_suggestions
```

#### 6. Analyst Content Ingestion Flow
```
Fetch Analyst Articles (Seeking Alpha API, Scheduled)
  ↓
Store in analyst_articles
  ↓
Analyst Reasoning Extractor (Async, Redis Stream)
  ↓
Use Claude to Extract:
  ├→ Decision Frameworks
  ├→ Red Flags
  └→ Valuation Approaches
  ↓
Store in analyst_reasoning_frameworks
  ↓
Composite Framework Generator (Event-Driven)
  ↓
Synthesize Cross-Analyst Patterns
  ↓
Update Scoring Logic (Feedback Loop)
```

---

## Technology Stack Details

### Frontend
- **Web:** React 18+ with TypeScript, Tailwind CSS, shadcn/ui
- **Mobile:** React Native with Expo
- **Desktop:** Electron wrapper (optional)
- **State Management:** Zustand or Redux Toolkit
- **API Client:** React Query for caching/sync

### Backend
- **API Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL 15+ (via Supabase)
  - Extensions: pgvector, postgis, pg_cron, pg_partman
  - RLS (Row-Level Security) for multi-tenancy
- **Cache:** Redis 7+ (Cluster mode)
- **Object Storage:** S3-compatible (AWS S3 or MinIO)
- **Search:** pgvector for semantic search

### AI/ML Stack
- **LLM:** Claude Sonnet 4 (Anthropic API)
- **Embeddings:** OpenAI ada-002
- **ML Models:** XGBoost, RandomForest (scikit-learn)
- **Vector Database:** pgvector

### Orchestration
- **Workflows:** Temporal (complex, long-running)
- **Batch Jobs:** Prefect (scheduled analytics)
- **Integration:** N8N (low-code workflows)
- **Events:** Redis Streams (lightweight pub/sub)

### External APIs
- **Account Aggregation:** Plaid
- **Trading:** Alpaca, Schwab
- **Market Data:** yfinance (free), Massiv (premium), AlphaVantage
- **Analyst Content:** Seeking Alpha, RapidAPI
- **AI:** Anthropic Claude, OpenAI

### Infrastructure
- **Container Orchestration:** Kubernetes (k3s for on-prem, EKS/GKE for cloud)
- **API Gateway:** Kong (rate limiting, auth, routing)
- **Monitoring:** Grafana Stack (Prometheus, Loki, Tempo)
- **CI/CD:** GitHub Actions
- **Secrets:** Kubernetes Secrets + External Secrets Operator

---

## Security Architecture

### Authentication & Authorization
- **Method:** JWT tokens via Supabase Auth
- **2FA:** Optional for trades and sensitive operations
- **Session Management:** Configurable timeout policies (idle, absolute)
- **Device Trust:** 30-day device memory to skip 2FA
- **API Keys:** Rotation policies (30/60/90 days), scopes-based permissions

### Multi-Tenancy
- **Database:** Row-Level Security (RLS) on all tenant tables
- **API:** X-Tenant-ID header required, validated at gateway
- **Isolation:** Complete data separation per tenant

### Encryption
- **At Rest:** AES-256 (Fernet) for sensitive credentials
- **In Transit:** TLS 1.3 for all API communication
- **Key Management:** Master key in AWS KMS/Vault, DEKs in database

### RBAC (Role-Based Access Control)
- **Roles:** Owner, Trader, Viewer (system roles)
- **Custom Roles:** Tenant-specific permissions
- **Permissions:** Resource.action granularity (e.g., portfolios.delete)

### Compliance
- **GDPR:** Data export, erasure, consent management
- **Data Retention:** 7-year policy with legal holds
- **Audit Logging:** Comprehensive activity tracking
- **SOX/SEC:** 7-year transaction retention

---

## Scalability Strategy

### Database Scaling
- **Partitioning:** Time-series tables partitioned monthly
- **Materialized Views:** 3 views for analytics (refreshed hourly)
- **Indexes:** Strategic indexing on query patterns
- **Connection Pooling:** PgBouncer for connection management

### Application Scaling
- **Horizontal:** Kubernetes HPA (2-10 pods per service)
- **Caching:** Redis for hot data, 1-hour TTL
- **Rate Limiting:** Per-endpoint cost-based throttling

### Agent Scaling
- **Embedded Agents:** Scale with parent service (scoring agents)
- **Microservice Agents:** Independent scaling (2-10 pods)
- **Temporal Workers:** Auto-scale based on queue depth (2-8 workers)

### Performance Targets
- **API Latency:** p95 < 200ms (read), p95 < 500ms (write)
- **Portfolio Analysis:** < 30 seconds for 100 holdings
- **Alert Generation:** Complete tenant scan in < 5 minutes
- **Simulation:** 10K Monte Carlo runs in < 60 seconds

---

## Deployment Architecture

### Hybrid Deployment Model
- **On-Premise:** Core services for data sovereignty
- **Cloud:** Burst capacity, analytics, long-term storage

### Kubernetes Architecture
```
┌──────────────────────────────────────────┐
│          Ingress (Kong Gateway)          │
└──────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────┐
│         API Services (5-10 pods)         │
│  FastAPI • WebSocket • File Service      │
└──────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────┐
│      Agent Services (10-30 pods)         │
│  Scoring • Analysis • Recommendations    │
└──────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────┐
│     Orchestration (5-10 workers)         │
│  Temporal • Prefect • N8N                │
└──────────────────────────────────────────┘
```

### Data Layer
- **PostgreSQL:** Supabase managed or self-hosted
- **Redis:** 3-node cluster with persistence
- **S3:** Cross-region replication for documents/backups

---

## Disaster Recovery

### Backup Strategy
- **Database:** Every 6 hours, 30-day retention
- **S3:** Cross-region replication
- **Kubernetes:** Velero backups (weekly)

### Recovery Objectives
- **RTO (Recovery Time Objective):** 4 hours
- **RPO (Recovery Point Objective):** 1 hour

### Recovery Priority
1. **P0 (1 hour):** Database, API Gateway, Core APIs
2. **P1 (4 hours):** Agent services, Temporal workflows
3. **P2 (8 hours):** Analytics, Background jobs

---

## Learning Systems (6 Layers)

### Layer 1: Analyst Learning
- **Input:** Analyst articles (Seeking Alpha, etc.)
- **Process:** Claude extracts decision frameworks, red flags, valuation methods
- **Output:** analyst_reasoning_frameworks table
- **Feedback:** Performance tracking validates analyst quality

### Layer 2: Tax Learning
- **Input:** User-uploaded tax documents (1099, K-1)
- **Process:** OCR + pattern recognition
- **Output:** tax_patterns_learned, optimization suggestions
- **Feedback:** User acceptance of suggestions

### Layer 3: Model Learning
- **Input:** Stock predictions vs. actual outcomes
- **Process:** XGBoost retraining on quarterly basis
- **Output:** Updated model weights
- **Feedback:** model_performance_metrics tracking

### Layer 4: Execution Learning
- **Input:** Order fills, slippage, timing
- **Process:** Analyze execution quality
- **Output:** Improved price targets, optimal timing
- **Feedback:** Actual vs. expected execution

### Layer 5: Conversational Learning
- **Input:** User chat history, preferences
- **Process:** Memory consolidation, preference extraction
- **Output:** User-specific context for Claude
- **Feedback:** User corrections, thumbs up/down

### Layer 6: LLM Self-Learning
- **Input:** In-session context
- **Process:** Real-time adaptation to user style
- **Output:** Session-specific responses
- **Feedback:** Immediate user reactions

---

## Implementation Roadmap

### Phase 1: Core Platform (Weeks 1-8)
**Goal:** Basic portfolio management with scoring

**Deliverables:**
- Database schema deployed (97 tables)
- Core API (portfolios, holdings, auth) - 30 endpoints
- Basic agents (scoring, analysis) - 8 agents
- Plaid integration (account sync)
- Simple dashboard

**Success Criteria:**
- User can connect account
- Holdings automatically scored
- Basic portfolio analytics visible

### Phase 2: Intelligence (Weeks 9-12)
**Goal:** Add AI-powered insights and alerts

**Deliverables:**
- Analyst extraction pipeline
- Tax document processing
- Alert system (30+ alert types)
- Proposal generation
- Learning systems (layers 1-3)

**Success Criteria:**
- Alerts generated automatically
- Trade proposals suggested
- Tax optimization recommendations

### Phase 3: Advanced Features (Weeks 13-16)
**Goal:** Complete feature set

**Deliverables:**
- DRIP system
- Rebalancing automation
- Goals management
- Document generation
- Backtesting engine
- Monte Carlo simulation

**Success Criteria:**
- Automated DRIP working
- Rebalancing suggestions accurate
- Retirement projections available

### Phase 4: Polish (Weeks 17-20)
**Goal:** Production hardening

**Deliverables:**
- Multi-currency support
- GDPR compliance tools
- Admin features
- Performance optimization
- Security hardening
- Documentation completion

**Success Criteria:**
- All security audits passed
- Performance SLAs met
- Beta user feedback incorporated

---

## Success Metrics

### Technical Metrics
- **API Uptime:** 99.9%
- **API Latency:** p95 < 200ms
- **Database Query Time:** p95 < 50ms
- **Agent Processing Time:** p95 < 5s per stock
- **Error Rate:** < 0.1%

### Business Metrics
- **User Satisfaction:** NPS > 50
- **Portfolio Safety:** Average safety score > 75
- **Alert Accuracy:** False positive rate < 5%
- **Proposal Acceptance:** > 60% approval rate
- **Tax Savings:** Measurable optimization impact

### Operational Metrics
- **Deployment Frequency:** Weekly
- **Mean Time to Recovery:** < 4 hours
- **Incident Response:** < 15 minutes
- **Data Backup Success:** 100%
- **Security Scans:** Daily, zero critical

---

## Risk Mitigation

### Technical Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Database performance | Medium | High | Partitioning, indexes, materialized views |
| AI API rate limits | Medium | Medium | Caching, fallback to rule-based |
| Broker API failures | High | Medium | Multi-broker support, retry logic |
| Data sync issues | Medium | Medium | Conflict resolution, manual override |

### Business Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Regulatory changes | Low | High | GDPR/SOX compliance framework |
| Security breach | Low | Critical | Defense in depth, audit logging |
| User data loss | Low | Critical | Backup strategy, DR plan |
| AI hallucination | Medium | Medium | Human-in-loop, proposal workflow |

---

## Appendices

### A. Complete Table List (97)
See [Data Model Documentation](data-model.md)

### B. Complete Agent Specifications (22)
See [Agent Architecture Documentation](agent-architecture.md)

### C. Complete API Specification (88+)
See [API Architecture Documentation](api-architecture.md)

### D. Mermaid Diagrams
- [System Overview](system-overview.mmd)
- [Agent Interactions](agent-interactions.mmd)
- [Data Model ERD](data-model.mmd)
- [Alert Flow](alert-flow.mmd)
- [Trade Execution Flow](trade-execution-flow.mmd)

---

**Document Version:** 1.0.0  
**Last Updated:** 2026-01-28  
**Next Review:** Upon Phase 1 completion

**Navigation:** [↑ Top](#reference-architecture---tax-efficient-income-investment-platform) | [Index](../index.md) | [README](../../README.md)
