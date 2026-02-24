# Income Fortress Platform — Documentation Index
**Last Updated:** 2026-02-23
**Version:** 2.0.0

---

## Platform Overview

The Income Fortress Platform is a tax-efficient income investment system built around 24 specialized AI agents. Core principles: capital preservation first (70% threshold with VETO power), proposal-based workflows (no auto-execution), and sophisticated analysis including Monte Carlo simulation and NAV erosion detection.

**Production:** https://legatoinvest.com
**Repository:** https://github.com/AlbertoDBP/Agentic/income-platform

---

## Agent Status

| Agent | Name | Version | Status |
|-------|------|---------|--------|
| 01 | Market Data Service | 2.0.0 | ✅ Production |
| 02 | Newsletter Ingestion | — | 🔲 Planned |
| 03 | Income Scorer | — | 🔲 Planned (data layer ready) |
| 04–24 | TBD | — | 🔲 Planned |

---

## Documentation

### Architecture
- [Reference Architecture v2.0.0](architecture/reference-architecture.md) — Provider routing, data flows, infrastructure

### Implementation Specifications
- [Agent 01 — Multi-Provider Architecture](implementation/agent-01-multi-provider-architecture.md) — v2.0.0 Session 3
- [Agent 01 — Historical Price Queries](implementation/agent-01-historical-price-queries.md) — v1.2.0 Session 2

### Decisions
- [Decisions Log](decisions/decisions-log.md) — ADR-001 through ADR-012
- [Security Incident 2026-02-23](decisions/security-incident-2026-02-23.md) — Redis public exposure resolved

### Change History
- [CHANGELOG](CHANGELOG.md) — v1.1.0, v1.2.0, v2.0.0

---

## Data Provider Stack

| Provider | Plan | Cost | Primary Use |
|----------|------|------|-------------|
| Polygon.io | Stocks Starter | $29/mo | OHLCV, price history |
| Financial Modeling Prep | Starter (annual) | $22/mo | Dividends, fundamentals |
| yfinance | Free | $0 | ETF holdings, fallback |
| SEC EDGAR | Free | $0 | Future: authoritative filings |
| **Total** | | **$51/mo** | |

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

## Upgrade Triggers

| Condition | Action |
|-----------|--------|
| Backtesting engine (Agent 08+) needs 10yr intraday | Polygon → Stocks Developer ($79/mo) |
| Monte Carlo needs 30yr dividend history | FMP → Premium ($59/mo) |
| ETF NAV analysis needs holdings data from FMP | FMP → Ultimate ($149/mo) |
| Real-time portfolio monitoring | Polygon → Developer or Advanced |

---

## Next Steps

1. **Agent 02 — Newsletter Ingestion** — email parsing + LLM extraction, pgvector semantic search
2. **Agent 03 — Income Scorer** — data layer now ready; dividend history, fundamentals, ETF holdings all available
3. **`requests_today` tracking** — rate limit monitoring for Polygon and FMP
4. **`docker-compose.yml` reconciliation** — resolve full-platform vs production-only conflict permanently

---
