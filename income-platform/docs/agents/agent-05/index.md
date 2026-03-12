# Agent 05 — Tax Optimization Service
## Master Documentation Index

**Service:** `tax-optimization-service`
**Port:** 8005
**Status:** ✅ Production Ready
**Last Updated:** 2026-03-12
**Version:** 1.0.0

---

## Overview

Agent 05 computes tax treatment profiles, after-tax yield calculations, account placement optimization, and tax-loss harvesting proposals for income-generating securities. It uses a rule-based engine with 2024 IRS brackets and all 50-state tax rates — no external tax API required. When `asset_class` is not provided by the caller, it calls Agent 04 (port 8004) to classify the symbol, with a graceful fallback to `ORDINARY_INCOME`.

---

## Quick Reference

| Item | Value |
|---|---|
| Port | 8005 |
| Base URL | `http://localhost:8005` |
| Health | `GET /health` |
| Tax Profile | `GET /tax/profile/{symbol}` or `POST /tax/profile` |
| Tax Calculation | `POST /tax/calculate` or `GET /tax/calculate/{symbol}` |
| Portfolio Optimization | `POST /tax/optimize` |
| Tax-Loss Harvesting | `POST /tax/harvest` |
| Asset Class Reference | `GET /tax/asset-classes` |
| Tax Year | 2024 IRS brackets |
| State Rates | All 50 states + DC |

---

## Documentation

| Document | Description |
|---|---|
| [Test Matrix](testing/test-matrix.md) | 135 tests across 2 files |
| [CHANGELOG](CHANGELOG.md) | Version history |
| [API Reference](../../../docs/api/agent-05-tax.md) | Full endpoint reference |

---

## Supported Asset Classes

| Class | Primary Tax Treatment | Section 199A | K-1 | Preferred Account |
|---|---|---|---|---|
| DIVIDEND_STOCK | QUALIFIED_DIVIDEND | No | No | TAXABLE |
| COVERED_CALL_ETF | ORDINARY_INCOME | No | No | IRA |
| REIT | REIT_DISTRIBUTION | Yes | No | IRA |
| BOND_ETF | ORDINARY_INCOME | No | No | IRA |
| PREFERRED_STOCK | QUALIFIED_DIVIDEND | No | No | TAXABLE |
| MLP | MLP_DISTRIBUTION | Yes | Yes | TAXABLE (avoid IRA — UBTI) |
| BDC | ORDINARY_INCOME | No | No | IRA |
| CLOSED_END_FUND | ORDINARY_INCOME | No | No | IRA |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (no auth) |
| GET | `/tax/profile/{symbol}` | Tax treatment profile for a symbol |
| POST | `/tax/profile` | Tax profile (POST, complex params) |
| POST | `/tax/calculate` | After-tax yield calculation |
| GET | `/tax/calculate/{symbol}` | After-tax yield (GET convenience) |
| POST | `/tax/optimize` | Portfolio account placement optimization |
| POST | `/tax/harvest` | Tax-loss harvesting opportunity scan |
| GET | `/tax/asset-classes` | Asset class tax treatment reference |

---

## Integration Points

| Upstream | Purpose |
|---|---|
| Agent 04 (port 8004) | Asset class lookup when not provided by caller (3s timeout, graceful fallback) |

| Downstream | Consumes |
|---|---|
| Agent 06+ | Tax-adjusted income projections |
| Portfolio UI | Account placement recommendations |
