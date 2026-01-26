# Tax-Efficient Income Investment Platform

**AI-Powered Portfolio Optimization for Covered Call ETFs & Income Investing**

[![Status](https://img.shields.io/badge/status-active%20development-blue)]()
[![Version](https://img.shields.io/badge/version-1.0-green)]()
[![Documentation](https://img.shields.io/badge/docs-complete-success)]()

## 🎯 Overview

The Tax-Efficient Income Investment Platform is a sophisticated AI-powered system that helps investors optimize income stocks and covered call ETF portfolios for **12-18% annual income yields** while managing:
- **Tax efficiency** across account types (IRA, 401k, taxable)
- **NAV erosion** common in covered call ETFs
- **Dividend sustainability** and quality
- **Portfolio risk** and concentration

### Key Features

✨ **ML-Powered Intelligence**
- Income Scoring (XGBoost with 50+ features)
- Smart Alert Classification (learns from user feedback)
- Scenario-based stress testing
- Automated rebalancing suggestions

📊 **Comprehensive Analysis**
- Real-time portfolio monitoring
- Tax drag calculations across account types
- NAV erosion tracking for ETFs
- 12-month income projections

🤖 **11 Specialized AI Agents**
- Market data synchronization
- Newsletter ingestion & analysis
- Opportunity scanning
- Entry/exit price recommendations

🔒 **Enterprise-Grade Security**
- Row-Level Security (RLS) for multi-tenancy
- End-to-end encryption
- Complete audit logging
- GDPR/CCPA compliant

---

## 🚀 Quick Start

### For Developers

```bash
# Clone repository
git clone https://github.com/albertoDBP/agentic/income-platform.git
cd income-platform

# Start local environment
docker-compose up

# Access services
# - Frontend: http://localhost:3000
# - n8n: http://localhost:5678
# - Supabase Studio: http://localhost:54323
```

### For Documentation Readers

Start with the [Documentation Index](docs/index.md) for complete navigation.

**Quick Links**:
- [Reference Architecture](docs/architecture/reference-architecture.md) - System design overview
- [Agent 3 Spec](docs/functional/agent-03-income-scoring.md) - Critical ML agent
- [Security Architecture](docs/security/security-architecture.md) - Auth, RLS, compliance
- [Deployment Guide](docs/deployment/production-deployment.md) - How to deploy

---

## 📐 Architecture

### High-Level Stack

```
┌─────────────────────────────────────┐
│   Next.js 15 (Web Interface)       │
│   React + TypeScript + Tailwind    │
└─────────────────────────────────────┘
           ↓ API Calls
┌─────────────────────────────────────┐
│   Hybrid Orchestration              │
│   ┌──────────┐    ┌──────────┐    │
│   │   n8n    │    │ Prefect  │    │
│   │ (Simple) │    │ (Complex)│    │
│   └──────────┘    └──────────┘    │
└─────────────────────────────────────┘
           ↓ Calls Agents
┌─────────────────────────────────────┐
│   11 AI Agents (FastAPI Services)  │
│   • Income Scoring (XGBoost)       │
│   • Alert Classification (XGBoost) │
│   • Scenario Simulation (GLM)      │
│   • Tax Optimization, NAV Monitor  │
│   • Entry Price, Rebalancing...    │
└─────────────────────────────────────┘
           ↓ Reads/Writes
┌─────────────────────────────────────┐
│   Supabase                          │
│   Postgres 15 + pgvector + RLS     │
└─────────────────────────────────────┘
```

### Technology Stack

**Frontend**
- Next.js 15 (App Router, Server Components)
- React 18, TypeScript, Tailwind CSS
- shadcn/ui components, Recharts
- TanStack Query (state management)

**Backend Services**
- Python 3.11, FastAPI
- XGBoost, scikit-learn, pandas
- yFinance (market data)
- OpenAI (embeddings & LLM)

**Orchestration**
- n8n (integration workflows)
- Prefect (core pipelines)

**Data & Storage**
- Supabase (Postgres 15 + pgvector)
- Redis (caching)
- S3 (model artifacts)

**Deployment**
- Docker, Fly.io, Vercel
- GitHub Actions (CI/CD)
- Sentry (monitoring)

---

## 🤖 AI Agents Overview

### ML-Powered Agents ⭐

| Agent | Purpose | Model | Features |
|-------|---------|-------|----------|
| **Agent 3** | Income Scoring | XGBoost | 50+ features, SHAP explanations |
| **Agent 6** | Scenario Simulation | ElasticNet GLM | Stress tests, regime calibration |
| **Agent 11** | Alert Classification | XGBoost | Learns from user feedback |

### Rule-Based Agents

| Agent | Purpose |
|-------|---------|
| **Agent 1** | Market Data Sync (yFinance + Alpaca) |
| **Agent 2** | Newsletter Ingestion (LLM extraction) |
| **Agent 4** | Entry Price Recommendations |
| **Agent 5** | Tax Optimization |
| **Agent 7** | Opportunity Scanner |
| **Agent 8** | Portfolio Rebalancing (CVXPY) |
| **Agent 9** | Income Projection |
| **Agent 10** | NAV Erosion Monitor |

---

## 📊 Key Capabilities

### Income Scoring (Agent 3)

Evaluates tickers across 5 factor categories:
1. **Yield Quality** (35%) - Sustainable high yield with growth
2. **Stability & Risk** (25%) - Low volatility, shallow drawdowns
3. **Fundamentals** (20%) - Strong cash flow, low leverage
4. **Valuation** (10%) - Attractive relative pricing
5. **Advisor Sentiment** (10%) - Expert consensus

**Output**: Letter grade (A/B/C/D/F) with factor breakdown and SHAP values

### Tax Optimization (Agent 5)

Analyzes optimal account placement:
- **IRA/401k**: Ordinary income dividends, high-turnover ETFs
- **Taxable**: Qualified dividends, Section 1256 ETFs, ROC distributions
- **Roth**: Tax-free growth candidates

**Output**: Tax drag calculations, placement recommendations, projected savings

### NAV Erosion Monitor (Agent 10)

Tracks covered call ETF performance:
- NAV change vs benchmark (1m, 3m, 6m, 12m)
- Premium/discount trends
- Upside capture ratio

**Output**: Alerts when NAV erosion exceeds -5% annually

---

## 📈 Success Metrics

### Platform Performance
- Web page load: **<2s** (Lighthouse ≥90)
- API response: **<500ms** (p95)
- Daily pipeline: **<10 min**
- Concurrent users: **100+**

### ML Model Performance
- Income Scoring: **AUC ≥0.80**
- Alert Precision: **≥70%** acted on
- Scenario RMSE: **<10%** on realized drawdowns

### Business Impact
- Tax savings: **≥1%** annually per portfolio
- Alert usefulness: **≥70%** user action rate
- Data freshness: **95%** tickers <24h old

---

## 🔐 Security & Compliance

### Authentication
- Supabase Auth (email/password + magic links)
- Optional MFA (TOTP)
- JWT tokens with automatic refresh

### Authorization
- Row-Level Security (RLS) enforces multi-tenancy
- Per-portfolio access control
- API rate limiting (100 req/hr free, 1000 req/hr premium)

### Data Protection
- AES-256 encryption at rest
- TLS 1.3 in transit
- Complete audit logging
- GDPR/CCPA compliant (right to access, delete, export)

### Compliance
- Financial disclaimers (informational only, not advice)
- 7-year data retention
- SEC/FINRA awareness (no regulated activities)

---

## 📋 Project Roadmap

### Phase 1: Foundation (Months 1-4) 🚧 In Progress
- [x] Complete architecture and design
- [x] Data model finalized
- [ ] Supabase schema implementation
- [ ] Agents 1, 2, 3, 11 deployed
- [ ] Basic dashboard operational

### Phase 2: ML & Research (Months 5-8) ⏳ Planned
- [ ] Feature engineering pipeline
- [ ] XGBoost models trained
- [ ] Agents 4, 5, 10 deployed
- [ ] Research page with semantic search
- [ ] Newsletter integration complete

### Phase 3: Advanced Analytics (Months 9-12) 📅 Future
- [ ] Agents 6, 7, 8, 9 deployed
- [ ] Performance tracking dashboard
- [ ] PDF report generation
- [ ] Production deployment

---

## 💰 Cost Structure

### Estimated Monthly Costs (100 users)

| Service | Monthly Cost |
|---------|-------------|
| Supabase Cloud | $25 |
| Fly.io (agents) | $10 |
| OpenAI API | $5 |
| Redis Cloud | $0 (free tier) |
| Vercel | $0 (free tier) |
| **Total** | **~$40/month** |

**Cost per user**: $0.40/month at 100 users

### Free Tier Strategy
- yFinance: Primary market data (free)
- Alpaca: Real-time data (free tier)
- Vercel: Frontend hosting (free)
- Redis: Cache layer (free tier)
- OpenAI: Aggressive caching to minimize tokens

---

## 🛠️ Development

### Local Setup

**Prerequisites**:
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Git

**Steps**:
```bash
# 1. Clone repo
git clone https://github.com/your-org/income-platform.git
cd income-platform

# 2. Copy environment template
cp .env.example .env
# Edit .env with your API keys (Supabase, OpenAI, Alpaca)

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
cd src/backend
alembic upgrade head

# 5. Seed initial data (optional)
python scripts/seed_data.py

# 6. Access services
# Frontend: http://localhost:3000
# n8n: http://localhost:5678
# Supabase Studio: http://localhost:54323
# API Docs: http://localhost:8000/docs
```

### Testing

```bash
# Backend (Python)
cd src/agents
pytest tests/ --cov=. --cov-report=html

# Frontend (TypeScript)
cd src/frontend
npm run test
npm run test:e2e

# Integration tests
cd tests/integration
pytest test_full_workflow.py
```

### Code Quality

**Python**:
- Linting: `ruff`
- Type checking: `mypy --strict`
- Formatting: `ruff format`

**TypeScript**:
- Linting: ESLint + Prettier
- Type checking: `tsc --noEmit`

---

## 📚 Documentation Structure

```
docs/
├── index.md                    # Master navigation (start here)
├── architecture/
│   └── reference-architecture.md
├── functional/                 # What each component does
│   ├── agent-01-market-data-sync.md
│   ├── agent-03-income-scoring.md
│   ├── agent-11-alert-classification.md
│   └── ...
├── implementation/             # How to build each component
│   ├── agent-03-income-scoring-impl.md
│   ├── supabase-setup-impl.md
│   └── ...
├── security/
│   └── security-architecture.md
├── deployment/
│   ├── local-setup.md
│   └── production-deployment.md
├── testing/
│   ├── test-matrix.md
│   └── edge-cases.md
└── diagrams/                   # Mermaid diagrams
    ├── system-architecture.mmd
    └── data-model.mmd
```

**Start here**: [Documentation Index](docs/index.md)

---

## 🤝 Contributing

We welcome contributions! Please see:
- [Contributing Guide](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Development Standards](docs/development/coding-standards.md)

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run quality checks (`pytest`, `ruff`, `mypy`)
5. Commit with conventional commits (`feat: add income projection`)
6. Push and create a Pull Request

---

## 📞 Support

- **Documentation**: [docs/index.md](docs/index.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/income-platform/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/income-platform/discussions)
- **Security**: security@your-domain.com

---

## 📄 License

[Your License Here - MIT, Apache 2.0, etc.]

---

## 🙏 Acknowledgments

Built with:
- [Next.js](https://nextjs.org/) - React framework
- [Supabase](https://supabase.com/) - Backend as a service
- [n8n](https://n8n.io/) - Workflow automation
- [Prefect](https://www.prefect.io/) - Workflow orchestration
- [XGBoost](https://xgboost.readthedocs.io/) - ML models
- [yFinance](https://github.com/ranaroussi/yfinance) - Market data

Research foundations:
- Agentic AI architectures (Kore.ai, Akka, Databricks)
- Investment scoring methodologies (Morningstar, Piotroski)
- Tax-efficient portfolio construction principles

---

## ⭐ Star Us

If you find this project useful, please consider giving it a star on GitHub!

---

**Last Updated**: 2026-01-23  
**Documentation Version**: 1.0  
**Platform Version**: 1.0 (Active Development)
