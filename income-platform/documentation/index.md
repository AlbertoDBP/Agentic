# Agent 05 — Tax Optimization Service: Documentation Index

**Version:** 1.0.0 | **Date:** 2026-03-09 | **Status:** ✅ Complete — Tested Locally

---

## Quick Reference

| | |
|---|---|
| **Port** | 8005 |
| **Service path** | `src/tax-optimization-service/` |
| **Python** | 3.11 (Docker) / 3.13 (local dev) |
| **DB access** | Read-only (`user_preferences`) |
| **New tables** | None |
| **Agent 01 dependency** | None |
| **Agent 04 dependency** | Soft (fallback to ORDINARY_INCOME) |
| **Endpoints** | 8 |
| **Test cases** | 24 |

---

## Documentation Map

### Specifications
- [Functional Specification](functional/agent-05-tax-optimization-functional-spec.md)
- [Implementation Specification](implementation/agent-05-tax-optimization-implementation-spec.md)

### Diagrams
- [System Architecture](diagrams/agent-05-system-diagram.mmd)
- [Tax Calculation Sequence](diagrams/agent-05-calculation-sequence.mmd)
- [Portfolio Optimization Sequence](diagrams/agent-05-optimization-sequence.mmd)
- [Data Model](diagrams/agent-05-data-model.mmd)

### Change History
- [CHANGELOG](CHANGELOG.md)
- [Architecture Decision Records](decisions-log.md)

---

## Agent Status in Platform

| Agent | Service | Port | Status |
|---|---|---|---|
| 01 | Market Data Service | 8001 | ✅ Production |
| 02 | Newsletter Ingestion Service | 8002 | ✅ Production |
| 03 | Income Scoring Service | 8003 | ✅ Production |
| 04 | Asset Classification Service | 8004 | ✅ Production |
| **05** | **Tax Optimization Service** | **8005** | ✅ **Complete — Pending Docker Deploy** |
| 06–24 | TBD | — | ⏳ Planned |

---

## API Quick Reference

```
GET  /health                          → Service + DB status
GET  /tax/asset-classes               → Reference table (10 asset classes)
GET  /tax/profile/{symbol}            → Tax treatment profile
POST /tax/profile                     → Tax treatment profile (complex)
GET  /tax/calculate/{symbol}          → After-tax calculation
POST /tax/calculate                   → After-tax calculation (complex)
POST /tax/optimize                    → Account placement recommendations
POST /tax/harvest                     → Tax-loss harvesting opportunities
```

---

## Key Design Decisions (Summary)

| Decision | Choice | ADR |
|---|---|---|
| Tax data source | Rule-based constants (2024 IRS) — no external API | ADR-005-01 |
| Agent 04 unavailability | Fallback to ORDINARY_INCOME + flag | ADR-005-02 |
| MLP in IRA | Hard rule: always TAXABLE (UBTI) | ADR-005-03 |
| Optimizer/Harvester execution | Proposals only — never auto-execute | ADR-005-04 |
| DB footprint | Read-only, no new tables | ADR-005-05 |

---

## Annual Maintenance Checklist

Each January, update the following in `app/tax/calculator.py`:

- [ ] `_ORDINARY_BRACKETS` — new IRS inflation-adjusted thresholds
- [ ] `_QUALIFIED_BRACKETS` — new LTCG/QDI thresholds
- [ ] `_NIIT_THRESHOLD` — confirm unchanged (static since 2013, not inflation-adjusted)
- [ ] `_STATE_RATES` — update any state rate changes

---

## GitHub Commit Instructions

```bash
# From monorepo root
git add src/tax-optimization-service/
git add documentation/functional/agent-05-tax-optimization-functional-spec.md
git add documentation/implementation/agent-05-tax-optimization-implementation-spec.md
git add documentation/diagrams/agent-05-*.mmd
git add documentation/CHANGELOG.md
git add documentation/decisions-log.md
git add documentation/index.md

git commit -m "feat(agent-05): add Tax Optimization Service

- Tax profiler: 10 asset classes, Agent 04 fallback with flag
- Tax calculator: 2024 IRS brackets, 51 state rates, NIIT
- Account optimizer: MLP UBTI rule, shelter-first for ordinary income assets
- Loss harvester: wash-sale detection, \$100 minimum threshold
- 8 endpoints, 24 tests, Python 3.13 compatible
- No new DB tables, read-only user_preferences access
- Proposals-only architecture (no auto-execution)

Tested locally: Python 3.13.7 arm64 Mac mini
All endpoints validated, tax math verified"

git push origin main
```
