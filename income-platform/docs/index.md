# Income Fortress Platform — Documentation Index

**Master Navigation for all Platform Documentation**

---

## Quick Navigation

### For Platform Users

- **[README.md](../README.md)** — Platform overview and getting started
- **[DESIGN-SUMMARY.md](../DESIGN-SUMMARY.md)** — Complete platform architecture
- **[Deployment Guide](deployment/deployment-guide.md)** — How to deploy the platform

### For Developers

- **[DEVELOPMENT-GUIDE.md](../DEVELOPMENT-GUIDE.md)** — Local development setup
- **[Agent Documentation](agents/)** — Per-agent specifications
- **[API Reference](../INTEGRATION_GUIDE.md)** — REST API and integration guide
- **[Architecture Decisions](decisions/)** — Design rationale and tradeoffs

### For Operations

- **[Deployment Guide](deployment/deployment-guide.md)** — Step-by-step deployment instructions
- **[Operational Runbook](deployment/operational-runbook.md)** — Daily operations and troubleshooting
- **[Disaster Recovery](deployment/disaster-recovery.md)** — Recovery procedures for failures
- **[Monitoring Guide](deployment/monitoring-guide.md)** — Prometheus/Grafana setup and alerts
- **[Troubleshooting Guide](troubleshooting/README.md)** — Service startup, database, auth, Docker issues
- **[Quick Reference](troubleshooting/QUICK_REFERENCE.md)** — Fast lookup for common commands

---

## Agent Documentation (Agents 01–06 Production)

| Agent | Name | Status | Docs |
|-------|------|--------|------|
| **01** | Market Data Sync | Production | [docs/agents/agent-01/](agents/agent-01/) |
| **02** | Newsletter Ingestion | Production | [docs/agents/agent-02/](agents/agent-02/) |
| **03** | Income Scoring | Production | [docs/agents/agent-03/](agents/agent-03/) |
| **04** | Asset Classification | Production | [docs/agents/agent-04/](agents/agent-04/) |
| **05** | Tax Optimization | Planned | [docs/agents/agent-05/](agents/agent-05/) |
| **06** | Scenario Simulation | Planned | [docs/agents/agent-06/](agents/agent-06/) |

### Per-Agent Structure

Each agent folder contains:
- `index.md` — Agent overview, quick start, file structure
- `functional/` — Functional specifications
- `architecture/` — System design and diagrams
- `decisions/` — Agent-specific ADRs
- `testing/` — Test matrix and coverage

**Example:** [Agent 03 Documentation](agents/agent-03/index.md)

---

## Deployment & Operations

| Document | Purpose |
|----------|---------|
| [Deployment Guide](deployment/deployment-guide.md) | Full deployment walkthrough (15 steps) |
| [Deployment Checklist](deployment/deployment-checklist.md) | 100+ verification items |
| [Operational Runbook](deployment/operational-runbook.md) | Daily operations, troubleshooting, emergencies |
| [Monitoring Guide](deployment/monitoring-guide.md) | Prometheus metrics, Grafana dashboards, alerts |
| [Disaster Recovery](deployment/disaster-recovery.md) | RTO/RPO targets, recovery procedures |
| [Circuit Breaker Monitoring](deployment/circuit-breaker-monitoring-update.md) | Position health monitoring |
| [Security Incident Playbook](deployment/security-incident-2026-02-23.md) | Incident response |

---

## Architecture & Design

| Document | Content |
|----------|---------|
| [DESIGN-SUMMARY.md](../DESIGN-SUMMARY.md) | Complete design (97 DB tables, 22 agents, 88+ endpoints) |
| [Reference Architecture](agents/agent-03/architecture/reference-architecture.md) | System diagrams and component interactions |
| [Architecture Decisions](decisions/) | ADRs explaining design rationale |
| [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md) | API integration and authentication |

---

## Decision Records (ADRs)

### Platform-Level Decisions

- **ADR-P01**: Monte Carlo NAV erosion prevents yield traps
- **ADR-P02**: Shared asset classifier ensures consistent taxonomy
- **ADR-P03**: Tax output decoupled from income score
- **ADR-P04**: Proposal-only architecture (no auto-execution)
- **ADR-P05**: Analyst signals stored with provenance
- **ADR-A01**: Finnhub + FMP credit rating cascade

See [decisions/README.md](decisions/README.md) for complete index.

---

## Frequently Referenced Files

### Root Level
- `README.md` — Platform overview
- `DESIGN-SUMMARY.md` — 100-page design spec
- `DEVELOPMENT-GUIDE.md` — Local setup
- `DEPLOYMENT.md` — Production deployment
- `INTEGRATION_GUIDE.md` — API documentation

### Documentation Hierarchy

```
docs/
├── index.md                          ← YOU ARE HERE
├── deployment/                       ← Operations
│   ├── deployment-guide.md
│   ├── deployment-checklist.md
│   ├── operational-runbook.md
│   ├── monitoring-guide.md
│   ├── disaster-recovery.md
│   └── ...
├── troubleshooting/                  ← Troubleshooting Guides
│   ├── README.md                     (index of all troubleshooting docs)
│   ├── QUICK_REFERENCE.md            (common commands and fast lookup)
│   ├── service-startup.md            (module errors, startup failures)
│   ├── database.md                   (connection, pool, schema issues)
│   ├── authentication.md             (JWT, auth, token problems)
│   ├── docker-deployment.md          (image caching, git, env vars)
│   └── tests.md                      (pytest, fixtures, test failures)
├── decisions/                        ← ADRs
│   ├── README.md
│   ├── decisions-log.md
│   └── ...
└── agents/                           ← Per-Agent Docs
    ├── agent-01/
    ├── agent-03/
    ├── agent-04/
    └── ...
```

---

## How to Use This Index

1. **New to the project?** → Start with [README.md](../README.md) and [DESIGN-SUMMARY.md](../DESIGN-SUMMARY.md)
2. **Setting up locally?** → [DEVELOPMENT-GUIDE.md](../DEVELOPMENT-GUIDE.md)
3. **Deploying to production?** → [Deployment Guide](deployment/deployment-guide.md)
4. **Integrating via API?** → [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md)
5. **Understanding design decisions?** → [ADRs](decisions/)
6. **On-call for production?** → [Operational Runbook](deployment/operational-runbook.md)
7. **Emergency incident?** → [Disaster Recovery](deployment/disaster-recovery.md)

---

## Current Version

- **Platform Version**: 1.0.0
- **Last Updated**: March 12, 2026
- **Status**: Production Ready

---

## Getting Help

- **Service not starting?** → [Service Startup Failures](troubleshooting/service-startup.md)
- **Database connection issue?** → [Database Errors](troubleshooting/database.md)
- **Auth/JWT problem?** → [Authentication Errors](troubleshooting/authentication.md)
- **Docker or deployment issue?** → [Docker & Deployment](troubleshooting/docker-deployment.md)
- **Test failure?** → [Test Failures](troubleshooting/tests.md)
- **Quick command lookup?** → [Quick Reference](troubleshooting/QUICK_REFERENCE.md)
- **Architecture Questions**: Review relevant [ADRs](decisions/README.md)
- **API Integration**: See [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md)
- **Feature Request**: Submit issue to GitHub

---

**Next:** Pick a section above based on your role or task.
