# Tax-Efficient Income Investment Platform - Documentation Index

**Version**: 1.0  
**Date**: 2026-01-23  
**Status**: Active Development

## Quick Navigation

### Getting Started
1. [README](../../README.md) - Platform overview and quick start
2. [Architecture Overview](#architecture-documentation) - System design and components
3. [Setup Instructions](#deployment-setup) - How to deploy and run
4. [Development Guide](#development-documentation) - Contributing and coding standards

### For Product Managers
- [Executive Summary](../EXECUTIVE_SUMMARY.md) - Business value and ROI
- [Feature Roadmap](../ROADMAP.md) - Implementation timeline
- [Success Metrics](../testing/acceptance-criteria.md) - KPIs and targets

### For Architects & Tech Leads
- [Reference Architecture](architecture/reference-architecture.md) - Complete system design
- [Security Architecture](security/security-architecture.md) - Auth, RLS, encryption
- [Data Model](diagrams/data-model.mmd) - Database schema
- [Technology Decisions](decisions-log.md) - ADRs and rationale

### For Developers
- [Functional Specifications](#functional-specifications) - What each component does
- [Implementation Specifications](#implementation-specifications) - How to build it
- [API Documentation](#api-documentation) - Service interfaces
- [Testing Guide](testing/test-matrix.md) - Test coverage requirements

---

## Architecture Documentation

### Core Architecture
| Document | Description | Status |
|----------|-------------|--------|
| [Reference Architecture](architecture/reference-architecture.md) | Complete system design with layers, components, data flows | ✅ Complete |
| [System Diagram](diagrams/system-architecture.mmd) | Visual architecture (Mermaid) | ✅ Complete |
| [Data Model](diagrams/data-model.mmd) | Database schema (ER diagram) | ✅ Complete |
| [Component Interactions](diagrams/component-interactions.mmd) | Sequence diagrams for key workflows | ✅ Complete |

### Specialized Architecture
| Document | Description | Status |
|----------|-------------|--------|
| [Security Architecture](security/security-architecture.md) | Auth, RLS, encryption, audit logging | ✅ Complete |
| [Deployment Architecture](deployment/deployment-architecture.md) | Infrastructure, CI/CD, monitoring | ✅ Complete |
| [Data Governance](deployment/data-governance.md) | Data quality, lineage, retention | ✅ Complete |

---

## Functional Specifications

Functional specs define **what** each component does, its responsibilities, interfaces, and success criteria.

### Agent Specifications
| Agent | Document | Description | Priority |
|-------|----------|-------------|----------|
| Agent 1 | [Market Data Sync](functional/agent-01-market-data-sync.md) | Daily data refresh from yFinance + Alpaca | P0 |
| Agent 2 | [Newsletter Ingestion](functional/agent-02-newsletter-ingestion.md) | Email parsing + LLM extraction | P0 |
| Agent 3 ⭐ | [Income Scoring](functional/agent-03-income-scoring.md) | ML-powered ticker quality scoring (XGBoost) | P0 |
| Agent 4 | [Entry Price](functional/agent-04-entry-price.md) | Technical + valuation buy/sell zones | P1 |
| Agent 5 | [Tax Optimization](functional/agent-05-tax-optimization.md) | Account placement recommendations | P1 |
| Agent 6 | [Scenario Simulation](functional/agent-06-scenario-simulation.md) | Portfolio stress testing (GLM) | P1 |
| Agent 7 | [Opportunity Scanner](functional/agent-07-opportunity-scanner.md) | Find new investment candidates | P2 |
| Agent 8 | [Rebalancing](functional/agent-08-rebalancing.md) | Portfolio optimization (CVXPY) | P2 |
| Agent 9 | [Income Projection](functional/agent-09-income-projection.md) | Forward 12-month income forecast | P2 |
| Agent 10 | [NAV Monitor](functional/agent-10-nav-monitor.md) | ETF NAV erosion tracking | P1 |
| Agent 11 ⭐ | [Alert Classification](functional/agent-11-alert-classification.md) | Smart alert generation (XGBoost) | P0 |

### Frontend Specifications
| Component | Document | Description | Priority |
|-----------|----------|-------------|----------|
| Web App | [Next.js Frontend](functional/frontend-webapp.md) | Complete web interface specification | P0 |
| Dashboard | [Dashboard Page](functional/page-dashboard.md) | Portfolio overview and metrics | P0 |
| Research | [Research Page](functional/page-research.md) | Ticker search and advisor insights | P1 |
| Alerts | [Alerts Page](functional/page-alerts.md) | Alert management with ML feedback | P0 |
| Analysis | [Analysis Page](functional/page-analysis.md) | Scenario planning and tax analysis | P1 |

### Infrastructure Specifications
| Component | Document | Description | Priority |
|-----------|----------|-------------|----------|
| Orchestration | [Hybrid Orchestration](functional/orchestration-hybrid.md) | n8n + Prefect strategy | P0 |
| Database | [Supabase Data Layer](functional/data-layer-supabase.md) | Postgres + pgvector + RLS | P0 |
| Caching | [Redis Cache Layer](functional/cache-layer-redis.md) | Hot data caching strategy | P1 |

---

## Implementation Specifications

Implementation specs include everything from functional specs PLUS technical design, API details, testing requirements, and acceptance criteria.

### ML-Powered Agents (Critical Path)
| Agent | Document | Key Technologies | Status |
|-------|----------|------------------|--------|
| Agent 3 | [Income Scoring Implementation](implementation/agent-03-income-scoring-impl.md) | XGBoost, 50+ features, SHAP | ✅ Complete |
| Agent 6 | [Scenario Simulation Implementation](implementation/agent-06-scenario-impl.md) | ElasticNet GLM, stress tests | ✅ Complete |
| Agent 11 | [Alert Classification Implementation](implementation/agent-11-alerts-impl.md) | XGBoost classifier, feedback loop | ✅ Complete |

### Data Agents (Foundation)
| Agent | Document | Key Technologies | Status |
|-------|----------|------------------|--------|
| Agent 1 | [Market Data Implementation](implementation/agent-01-market-data-impl.md) | yFinance, Alpaca API, Prefect | ✅ Complete |
| Agent 2 | [Newsletter Implementation](implementation/agent-02-newsletter-impl.md) | LLM extraction, pgvector, n8n | ✅ Complete |

### Analysis Agents
| Agent | Document | Key Technologies | Status |
|-------|----------|------------------|--------|
| Agent 4 | [Entry Price Implementation](implementation/agent-04-entry-price-impl.md) | Technical indicators, valuation | ✅ Complete |
| Agent 5 | [Tax Optimization Implementation](implementation/agent-05-tax-impl.md) | Tax calculation engine | ✅ Complete |
| Agent 7 | [Opportunity Scanner Implementation](implementation/agent-07-opportunity-impl.md) | Composite scoring, filters | ⏳ Pending |
| Agent 8 | [Rebalancing Implementation](implementation/agent-08-rebalancing-impl.md) | CVXPY optimization | ⏳ Pending |
| Agent 9 | [Income Projection Implementation](implementation/agent-09-projection-impl.md) | Dividend forecasting | ⏳ Pending |
| Agent 10 | [NAV Monitor Implementation](implementation/agent-10-nav-impl.md) | Trend analysis, erosion detection | ✅ Complete |

### Frontend Implementation
| Component | Document | Key Technologies | Status |
|-----------|----------|------------------|--------|
| Web App Setup | [Next.js Implementation](implementation/frontend-nextjs-impl.md) | Next.js 15, Supabase client, TanStack Query | ✅ Complete |
| Dashboard | [Dashboard Implementation](implementation/page-dashboard-impl.md) | Server Components, Recharts | ⏳ Pending |
| Research Page | [Research Implementation](implementation/page-research-impl.md) | Semantic search, ticker details | ⏳ Pending |

### Infrastructure Implementation
| Component | Document | Key Technologies | Status |
|-----------|----------|------------------|--------|
| Supabase Setup | [Database Implementation](implementation/supabase-setup-impl.md) | Postgres schema, RLS policies, migrations | ✅ Complete |
| n8n Workflows | [n8n Implementation](implementation/n8n-workflows-impl.md) | Email trigger, webhook handlers | ✅ Complete |
| Prefect Workflows | [Prefect Implementation](implementation/prefect-workflows-impl.md) | Daily pipeline, agent flows | ✅ Complete |
| Deployment | [Production Deployment](implementation/deployment-production-impl.md) | Docker, Fly.io, Vercel, CI/CD | ✅ Complete |

---

## Testing Documentation

### Test Coverage Requirements
| Document | Description | Status |
|----------|-------------|--------|
| [Test Matrix](testing/test-matrix.md) | Complete test coverage across all components | ✅ Complete |
| [Edge Cases](testing/edge-cases.md) | Known failure modes and boundary conditions | ✅ Complete |
| [ML Model Testing](testing/ml-model-testing.md) | Validation strategies for ML agents | ✅ Complete |
| [Integration Testing](testing/integration-testing.md) | End-to-end workflow validation | ✅ Complete |

### Acceptance Criteria
Each implementation spec includes specific, measurable acceptance criteria. See individual implementation docs for details.

---

## API Documentation

### FastAPI Services
| Service | OpenAPI Spec | Description |
|---------|-------------|-------------|
| Income Scoring | [Scoring API](api/scoring-service.yaml) | `/score`, `/batch-score` endpoints |
| Alert Service | [Alert API](api/alert-service.yaml) | `/generate-alerts`, `/classify-alert` |
| Tax Service | [Tax API](api/tax-service.yaml) | `/optimize-placement`, `/calculate-drag` |
| Newsletter RAG | [RAG API](api/rag-service.yaml) | `/search`, `/embed`, `/extract` |

All services have auto-generated docs at `<service-url>/docs` (FastAPI default).

### Next.js API Routes
| Route | Description | Auth Required |
|-------|-------------|---------------|
| `/api/portfolios` | CRUD for portfolios | ✅ Yes |
| `/api/positions` | CRUD for positions | ✅ Yes |
| `/api/analysis/run` | Trigger analysis workflow | ✅ Yes |
| `/api/alerts/feedback` | Submit alert feedback (ML training) | ✅ Yes |

---

## Security Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [Security Architecture](security/security-architecture.md) | Complete security design | ✅ Complete |
| [Authentication Guide](security/authentication.md) | Supabase Auth setup, MFA | ✅ Complete |
| [RLS Policies](security/rls-policies.md) | All Row-Level Security rules | ✅ Complete |
| [Audit Logging](security/audit-logging.md) | What gets logged, retention policy | ✅ Complete |
| [Compliance](security/compliance.md) | GDPR, CCPA, financial disclaimers | ✅ Complete |

---

## Deployment & Setup

### Infrastructure
| Document | Description | Status |
|----------|-------------|--------|
| [Local Development](deployment/local-setup.md) | Docker Compose setup | ✅ Complete |
| [Production Deployment](deployment/production-deployment.md) | Fly.io + Vercel + Supabase Cloud | ✅ Complete |
| [CI/CD Pipeline](deployment/ci-cd-pipeline.md) | GitHub Actions workflows | ✅ Complete |
| [Monitoring Setup](deployment/monitoring-setup.md) | Sentry, metrics, dashboards | ✅ Complete |
| [Backup & Recovery](deployment/disaster-recovery.md) | Backup strategy, failover procedures | ✅ Complete |

### Configuration
| File | Purpose | Location |
|------|---------|----------|
| `docker-compose.yml` | Local development stack | `/config/` |
| `fly.toml` | Fly.io deployment config | `/config/` |
| `supabase-migrations/` | Database schema migrations | `/config/` |
| `.env.example` | Environment variables template | `/` |

---

## Development Documentation

### Standards & Conventions
| Document | Description | Status |
|----------|-------------|--------|
| [Coding Standards](development/coding-standards.md) | Python, TypeScript, SQL conventions | ✅ Complete |
| [Git Workflow](development/git-workflow.md) | Branching, commits, PRs | ✅ Complete |
| [Documentation Standards](development/documentation-standards.md) | How to write good docs | ✅ Complete |
| [Code Review Checklist](development/code-review-checklist.md) | What to check in PRs | ✅ Complete |

### Development Guides
| Document | Description | Status |
|----------|-------------|--------|
| [Adding a New Agent](development/guide-add-agent.md) | Step-by-step for new agents | ✅ Complete |
| [Adding a Frontend Page](development/guide-add-page.md) | Next.js page creation | ✅ Complete |
| [ML Model Training](development/guide-train-model.md) | Training and deploying ML models | ✅ Complete |
| [Database Migrations](development/guide-migrations.md) | Schema change process | ✅ Complete |

---

## Code Scaffolds

### Python Services
```
src/agents/
├── scoring_service/          # Agent 3: Income Scoring
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic models
│   ├── ml_model.py          # XGBoost model loading
│   ├── features.py          # Feature engineering
│   └── test_scoring.py      # Unit tests
│
├── alert_service/           # Agent 11: Alerts
│   └── ...
│
└── shared/                  # Shared utilities
    ├── supabase_client.py
    ├── redis_client.py
    └── auth.py
```

### Frontend (Next.js)
```
src/frontend/
├── app/                     # Next.js 15 App Router
│   ├── dashboard/
│   │   └── page.tsx
│   ├── portfolios/
│   │   └── [id]/
│   │       └── page.tsx
│   └── api/                 # API routes
│       └── portfolios/
│           └── route.ts
│
├── components/              # Shared components
│   ├── ui/                  # shadcn/ui components
│   ├── IncomeOverviewCard.tsx
│   ├── AlertFeed.tsx
│   └── ...
│
└── lib/                     # Utilities
    ├── supabase.ts
    ├── api-client.ts
    └── types.ts
```

### Workflows
```
src/workflows/
├── n8n/
│   ├── newsletter-ingestion.json
│   ├── webhook-handlers.json
│   └── health-checks.json
│
└── prefect/
    ├── daily_pipeline.py
    ├── portfolio_analysis.py
    └── ml_training.py
```

---

## Project Status

### Phase 1 (Months 1-4): Foundation ✅ Design Complete
- [x] Architecture design
- [x] Data model design
- [x] Security design
- [ ] Supabase schema implementation
- [ ] Agent 1, 2, 3, 11 implementation
- [ ] Basic dashboard

### Phase 2 (Months 5-8): ML & Research 🚧 In Progress
- [x] Feature engineering design
- [x] ML model specifications
- [ ] Agent 4, 5, 10 implementation
- [ ] Research page
- [ ] ML model training pipeline

### Phase 3 (Months 9-12): Advanced Analytics ⏳ Planned
- [ ] Agent 6, 7, 8, 9 implementation
- [ ] Performance tab
- [ ] PDF report generation
- [ ] Production deployment

---

## Change History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

| Version | Date | Major Changes |
|---------|------|---------------|
| 1.0 | 2026-01-23 | Initial documentation package |

---

## Decision Log

See [decisions-log.md](decisions-log.md) for all Architecture Decision Records (ADRs).

Key decisions:
- **ADR-001**: Hybrid orchestration (n8n + Prefect) over single solution
- **ADR-002**: Supabase over self-hosted Postgres for RLS and Auth
- **ADR-003**: XGBoost over neural networks for interpretability
- **ADR-004**: Next.js App Router over Pages Router for SSR
- **ADR-005**: yFinance primary, Alpaca secondary for cost control

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Setting up development environment
- Running tests
- Submitting pull requests
- Documentation updates

---

## Support & Contact

- **Technical Issues**: [GitHub Issues](https://github.com/your-org/income-platform/issues)
- **Documentation Feedback**: Submit PR to `docs/` folder
- **Security Concerns**: security@your-domain.com

---

## License

[Your License Here]

---

**Last Updated**: 2026-01-23  
**Maintained By**: Platform Team  
**Documentation Version**: 1.0
