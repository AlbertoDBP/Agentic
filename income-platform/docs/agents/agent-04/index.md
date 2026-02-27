# Agent 04 — Asset Classification Service
## Master Documentation Index

**Service:** `asset-classification-service`  
**Port:** 8004  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-02-27  
**Version:** 1.0.0

---

## Overview

Agent 04 classifies income-generating securities into one of 7 asset classes using a rule-based detection engine. It produces benchmarks, tax efficiency profiles, and class-specific characteristics consumed by Agent 03 (Income Scorer) and Agent 05 (Tax Optimizer). The shared detection utility (`src/shared/asset_class_detector/`) is importable by any agent in the platform.

---

## Quick Reference

| Item | Value |
|---|---|
| Port | 8004 |
| Base URL | `http://localhost:8004` |
| Health | `GET /health` |
| Classify | `POST /classify` |
| Batch | `POST /classify/batch` |
| DB Schema | `platform_shared` |
| Cache TTL | 24 hours |
| Confidence Threshold | 0.70 (below → enrich via Agent 01) |

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](architecture/reference-architecture.md) | System design, component interactions, data flow |
| [Classification Engine](functional/classification-engine.md) | Core pipeline functional spec |
| [Shared Detector](functional/shared-detector.md) | Shared utility functional spec |
| [Tax Profile](functional/tax-profile.md) | Tax efficiency output spec |
| [Test Matrix](testing/test-matrix.md) | 55 tests across 7 asset classes |
| [Decisions Log](decisions/decisions-log.md) | 6 ADRs |
| [CHANGELOG](CHANGELOG.md) | Version history |

---

## Asset Classes

| Class | Parent | Valuation | Account |
|---|---|---|---|
| DIVIDEND_STOCK | EQUITY | P/E + yield | TAXABLE |
| COVERED_CALL_ETF | FUND | yield + nav_trend | IRA |
| BOND | FIXED_INCOME | yield_to_maturity | IRA |
| EQUITY_REIT | EQUITY | P/FFO | IRA |
| MORTGAGE_REIT | EQUITY | P/BV | IRA |
| BDC | ALTERNATIVE | P/NAV | IRA |
| PREFERRED_STOCK | EQUITY | yield_to_call | TAXABLE |

---

## API Endpoints

### `POST /classify`
```json
Request:  { "ticker": "JEPI", "security_data": {} }
Response: { "ticker", "asset_class", "parent_class", "confidence",
            "is_hybrid", "characteristics", "benchmarks",
            "sub_scores", "tax_efficiency", "source",
            "classified_at", "valid_until" }
```

### `POST /classify/batch`
```json
Request:  { "tickers": ["JEPI", "AGNC", "ARCC"] }
Response: { "total", "classified", "errors", "results", "error_details" }
```

### `GET /classify/{ticker}`
Returns latest classification, runs fresh if not cached.

### `GET /rules` / `POST /rules`
List and add classification rules. DB-driven — no redeploy needed.

### `PUT /overrides/{ticker}` / `DELETE /overrides/{ticker}`
Manual override management. confidence=1.0, bypasses all rules.

---

## Integration Points

| Upstream | Purpose |
|---|---|
| Agent 01 (port 8001) | Enrichment when confidence < 0.70 |

| Downstream | Consumes |
|---|---|
| Agent 03 (port 8003) | `asset_class` + `characteristics` for quality gate routing |
| Agent 05 (port 8005) | `tax_efficiency` for account placement optimization |
