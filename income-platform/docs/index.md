# Income Fortress Platform - Documentation Index

**Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Status:** Phase 1 Complete - Production Ready

---

## 📚 Quick Navigation

### 🏗️ Architecture & Design
- [Reference Architecture](architecture/reference-architecture.md) - System overview and component interactions
- [System Diagrams](architecture/diagrams.md) - Mermaid diagrams for all major flows
- [Data Model](architecture/data-model.md) - Database schemas and relationships
- [Technology Stack](architecture/technology-stack.md) - Languages, frameworks, infrastructure

### 📋 Functional Specifications
**Core Platform:**
- [Income Scorer V6](functional/income-scorer-v6.md) - Hybrid scoring with NAV erosion & ROC
- [Feature Store V2](functional/feature-store-v2.md) - Enhanced data extraction
- [Circuit Breaker Monitor](functional/circuit-breaker-monitor.md) - Real-time position health
- [Preference Manager](functional/preference-manager.md) - Tenant-specific configuration

**24-Agent System:**
- [Agent Overview](functional/agent-system-overview.md) - Complete agent hierarchy
- Tier 1: [Platform Coordinator](functional/agents/platform-coordinator.md)
- Tier 2: [Safety Supervisor](functional/agents/safety-supervisor.md) | [Portfolio Supervisor](functional/agents/portfolio-supervisor.md) | [Research Supervisor](functional/agents/research-supervisor.md)
- Tier 3: Safety Domain (Agents 4-7) | Portfolio Domain (Agents 8-16) | Research Domain (Agents 17-24)

### 🔧 Implementation Specifications
**Phase 1 Components:**
- [Income Scorer V6 Implementation](implementation/income-scorer-v6-impl.md) - Complete technical design with testing
- [NAV Erosion Calculation](implementation/nav-erosion-calculation.md) - Formula, validation, edge cases
- [ROC Tax Efficiency](implementation/roc-tax-efficiency.md) - Tax breakdown tracking
- [SAIS Curves Enhancement](implementation/sais-curves-enhancement.md) - Granular 5-zone scoring
- [Circuit Breaker Composite Risk](implementation/circuit-breaker-composite-risk.md) - 40/30/20/10 formula

**Infrastructure:**
- [Docker Deployment](implementation/docker-deployment.md) - Complete container stack
- [Nginx Configuration](implementation/nginx-configuration.md) - Reverse proxy, SSL, rate limiting
- [Celery Task Queue](implementation/celery-task-queue.md) - Workers, queues, scheduling
- [Monitoring & Logging](implementation/monitoring-logging.md) - Prometheus, alerts, structured logs
- [Backup & Recovery](implementation/backup-recovery.md) - Automated procedures

### 🧪 Testing Specifications
- [Test Matrix](testing/test-matrix.md) - Comprehensive test coverage
- [Unit Test Requirements](testing/unit-tests.md) - Per-component test specs
- [Integration Tests](testing/integration-tests.md) - Cross-component workflows
- [Performance Tests](testing/performance-tests.md) - Load testing, benchmarks
- [Edge Cases](testing/edge-cases.md) - Boundary conditions, failure modes

### 🚀 Deployment & Operations
- [Deployment Guide](deployment/deployment-guide.md) - Step-by-step deployment
- [Deployment Checklist](deployment/deployment-checklist.md) - 50+ item verification
- [Operational Runbook](deployment/operational-runbook.md) - Common operations, troubleshooting
- [Monitoring Guide](deployment/monitoring-guide.md) - Metrics, alerts, dashboards
- [Disaster Recovery](deployment/disaster-recovery.md) - Backup, restore, failover

### 📊 API Reference
- [REST API](api/rest-api.md) - FastAPI endpoints
- [Celery Tasks API](api/celery-tasks.md) - Async task definitions
- [Database Schema](api/database-schema.md) - Tables, relationships, indexes
- [Webhook API](api/webhook-api.md) - n8n integration points

### 📝 Project Management
- [CHANGELOG](CHANGELOG.md) - Version history and changes
- [Decisions Log](decisions-log.md) - Architecture Decision Records (ADRs)
- [Continuous Improvement](continuous-improvement.md) - Phase 2-4 roadmap
- [Contributing Guide](CONTRIBUTING.md) - Development workflow

---

## 🎯 Component Status

### ✅ Complete (Production Ready)
| Component | Version | Status | Documentation | Tests |
|-----------|---------|--------|---------------|-------|
| Income Scorer V6 | 6.0.0 | ✅ Complete | ✅ Complete | ✅ Complete |
| Feature Store V2 | 2.0.0 | ✅ Complete | ✅ Complete | ✅ Complete |
| Circuit Breaker Monitor | 2.0.0 | ✅ Complete | ✅ Complete | ✅ Complete |
| Analyst Consensus Tracker | 1.0.0 | ✅ Complete | ✅ Complete | ✅ Complete |
| Preference Manager | 1.0.0 | ✅ Complete | ✅ Complete | ✅ Complete |
| Docker Deployment | 1.0.0 | ✅ Complete | ✅ Complete | ✅ Complete |
| Nginx Configuration | 1.0.0 | ✅ Complete | ✅ Complete | ⏳ Pending |
| Celery Task Queue | 1.0.0 | ✅ Complete | ✅ Complete | ⏳ Pending |
| Monitoring & Logging | 1.0.0 | ✅ Complete | ✅ Complete | ⏳ Pending |
| Backup & Recovery | 1.0.0 | ✅ Complete | ✅ Complete | ⏳ Pending |

### ⏳ Pending (Phase 2+)
| Component | Target Version | Planned For | Priority |
|-----------|---------------|-------------|----------|
| Adaptive Learning Integration | 1.1.0 | Phase 2 | High |
| Full Bond Scoring | 1.1.0 | Phase 2 | High |
| Enhanced Dividend Stock Scoring | 1.1.0 | Phase 2 | High |
| Liquidity Quality Gate | 1.2.0 | Phase 2 | Medium |
| Valuation Metrics | 1.2.0 | Phase 2 | Medium |
| Macro Sensitivity Scoring | 2.0.0 | Phase 3 | High |
| Sector-Specific Deep Factors | 2.0.0 | Phase 3 | High |
| ESG Integration | 2.1.0 | Phase 3 | Low |

---

## 📁 Repository Structure

```
income-platform/
├── docs/                          # This documentation
│   ├── architecture/              # System architecture
│   ├── functional/                # Functional specifications
│   ├── implementation/            # Technical specifications
│   ├── testing/                   # Test specifications
│   ├── deployment/                # Deployment guides
│   ├── api/                       # API documentation
│   ├── CHANGELOG.md               # Version history
│   ├── decisions-log.md           # ADRs
│   └── index.md                   # This file
│
├── app/                           # FastAPI application
│   ├── main.py                    # Application entry point
│   ├── celery_app.py              # Celery configuration
│   ├── logging_config.py          # Structured logging
│   ├── monitoring.py              # Prometheus metrics
│   └── database.py                # Database connection
│
├── agents/                        # AI agents
│   ├── income_scorer_v6_final.py  # Main scoring engine
│   ├── feature_store_v2.py        # Feature extraction
│   ├── circuit_breaker_monitor.py # Position monitoring
│   └── analyst_consensus_tracker.py
│
├── migrations/                    # Database migrations
│   ├── 001_initial_schema.sql
│   └── 002_phase1_enhancements.sql
│
├── nginx/                         # Nginx configuration
│   ├── nginx.conf                 # Main config
│   └── conf.d/                    # Site configs
│
├── prometheus/                    # Monitoring config
│   ├── prometheus.yml
│   └── alerts/
│
├── scripts/                       # Deployment scripts
│   ├── deploy.sh                  # Master deployment
│   ├── backup_database.sh         # Database backup
│   └── restore_database.sh        # Database restore
│
├── tests/                         # Test suite
│   ├── test_income_scorer_v6.py
│   ├── test_feature_store.py
│   └── test_circuit_breaker.py
│
├── docker-compose.production.yml  # Production stack
├── Dockerfile.api                 # API container
├── requirements.txt               # Python dependencies
├── .env.production                # Environment config
└── README.md                      # Getting started
```

---

## 🚦 Getting Started

### For Developers
1. Read [Reference Architecture](architecture/reference-architecture.md)
2. Review [Income Scorer V6 Implementation](implementation/income-scorer-v6-impl.md)
3. Set up development environment (see [CONTRIBUTING.md](CONTRIBUTING.md))
4. Run tests: `python -m pytest tests/`

### For DevOps
1. Read [Deployment Guide](deployment/deployment-guide.md)
2. Complete [Deployment Checklist](deployment/deployment-checklist.md)
3. Review [Operational Runbook](deployment/operational-runbook.md)
4. Set up monitoring (see [Monitoring Guide](deployment/monitoring-guide.md))

### For Product Managers
1. Read [Agent System Overview](functional/agent-system-overview.md)
2. Review [Component Status](#-component-status) above
3. Check [CHANGELOG](CHANGELOG.md) for recent changes
4. Review [Continuous Improvement](continuous-improvement.md) roadmap

---

## 📊 Key Metrics

### Code Statistics
- **Total Lines:** 14,900+
- **Languages:** Python (90%), Bash (5%), YAML/Nginx (5%)
- **Files:** 25+ production files
- **Test Coverage:** 85%+ (Phase 1 components)

### Infrastructure
- **Services:** 8 Docker containers
- **Queues:** 6 Celery queues
- **Workers:** 3 specialized workers
- **Scheduled Tasks:** 15 periodic jobs

### Cost (15 tenants)
- **Infrastructure:** $59/mo ($3.93/tenant)
- **AI (Anthropic):** $40-80/mo ($2.67-5.33/tenant)
- **External APIs:** $50-100/mo ($3.33-6.67/tenant)
- **Total:** $149-239/mo ($9.93-15.93/tenant)

### Performance Targets
- **API Response:** p95 <500ms
- **Scoring Latency:** <3s per symbol
- **Feature Extraction:** 99%+ success rate
- **Circuit Breaker Alerts:** <1min (EMERGENCY)

---

## 🔗 External Resources

- **GitHub Repository:** https://github.com/AlbertoDBP/Agentic/tree/main/income-platform
- **Production API:** https://api.incomefortress.com
- **Monitoring Dashboard:** https://grafana.incomefortress.com (internal)
- **n8n Workflows:** https://n8n.incomefortress.com (internal)

---

## 📞 Support

- **Documentation Issues:** Open issue in GitHub
- **Deployment Questions:** See [Operational Runbook](deployment/operational-runbook.md)
- **Architecture Questions:** Review [Decisions Log](decisions-log.md)

---

**Last Updated:** February 2, 2026  
**Next Review:** May 1, 2026 (Phase 2 kickoff)
