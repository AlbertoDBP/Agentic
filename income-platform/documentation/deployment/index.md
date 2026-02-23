# Income Fortress Platform — Documentation Index
**Last Updated:** 2026-02-23
**Version:** 1.2.0

---

## Platform Overview

The Income Fortress Platform is a tax-efficient income investment system built around 24 specialized AI agents. Core principles: capital preservation first (70% threshold with VETO power), proposal-based workflows (no auto-execution), and sophisticated analysis including Monte Carlo simulation and NAV erosion detection.

**Production:** https://legatoinvest.com
**Repository:** https://github.com/AlbertoDBP/Agentic/income-platform

---

## Agent Status

| Agent | Name | Version | Status |
|-------|------|---------|--------|
| 01 | Market Data Service | 1.2.0 | ✅ Production |
| 02 | TBD | — | 🔲 Planned |
| 03 | Income Scorer | — | 🔲 Planned (after data provider migration) |
| 04-24 | TBD | — | 🔲 Planned |

---

## Documentation

### Architecture
- [Reference Architecture](architecture/reference-architecture.md) — System overview, data flows, infrastructure

### Implementation Specifications
- [Agent 01 — Historical Price Queries](implementation/agent-01-historical-price-queries.md) — v1.2.0 Session 2
- Agent 01 — Database Persistence *(Session 1 — to be documented)*

### Decisions
- [Decisions Log](decisions/decisions-log.md) — ADR-001 through ADR-007
- [Security Incident 2026-02-23](decisions/security-incident-2026-02-23.md) — Redis public exposure

### Change History
- [CHANGELOG](CHANGELOG.md) — v1.1.0, v1.2.0

---

## Infrastructure Quick Reference

| Resource | Details |
|----------|---------|
| Droplet | DigitalOcean NYC3, 2vCPU/4GB, Ubuntu LTS |
| IP | 138.197.78.238 |
| Domain | legatoinvest.com |
| PostgreSQL | Managed DO, VPC-only |
| Valkey | Managed DO, VPC-only |
| Firewall | Ports 22, 80, 443 only |

---

## Upcoming: Data Provider Migration

After Agent 02, the platform will migrate from Alpha Vantage to:
- **Polygon.io** — real-time data, full history
- **Financial Modeling Prep** — dividends, fundamentals, ETF holdings

This unlocks full capabilities for Agent 03 Income Scorer and NAV Erosion Analyzer.

---
