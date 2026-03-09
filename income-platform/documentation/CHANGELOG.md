# CHANGELOG — Income Fortress Platform

## [Unreleased]

### Added — 2026-03-09

#### Agent 05 — Tax Optimization Service (port 8005)

- **Tax Profiler** (`app/tax/profiler.py`)
  - Rule-based tax treatment mapping for 10 asset classes
  - Agent 04 callout with 3-second timeout and graceful fallback to ORDINARY_INCOME
  - `asset_class_fallback` flag surfaced in every response

- **Tax Calculator** (`app/tax/calculator.py`)
  - 2024 IRS federal brackets for all 4 filing statuses (ordinary + qualified/LTCG)
  - 51-jurisdiction state rate table (50 states + DC)
  - NIIT (3.8%) with income thresholds by filing status
  - Special handling: Section 1256 60/40 blended, ROC ($0 tax), tax-exempt, REIT/MLP ~70% ROC approximation
  - Tax-sheltered accounts (IRA/HSA/401k) return $0 tax automatically

- **Account Placement Optimizer** (`app/tax/optimizer.py`)
  - Recommends TAXABLE vs TRAD_IRA vs ROTH_IRA per holding
  - MLP UBTI rule enforced — MLPs always stay in TAXABLE
  - High-ordinary-income assets (REITs, BDCs, Bond ETFs, Covered Call ETFs) → shelter first
  - QDI-eligible assets (dividend stocks, preferred) → taxable preferred
  - Proposals only — no auto-execution

- **Tax-Loss Harvester** (`app/tax/harvester.py`)
  - Scans candidate positions for harvestable losses
  - $100 minimum threshold (below → MONITOR)
  - Wash-sale risk flagging (holding period < 30 days)
  - Actions: HARVEST_NOW / MONITOR / HOLD / REVIEW_WASH_SALE
  - Sheltered accounts always return HOLD
  - Proposals only — no auto-execution

- **API** (`app/api/routes.py`) — 8 endpoints:
  - `GET /health`
  - `GET /tax/asset-classes`
  - `GET|POST /tax/profile/{symbol}`
  - `GET|POST /tax/calculate/{symbol}`
  - `POST /tax/optimize`
  - `POST /tax/harvest`

- **Infrastructure**
  - Self-contained Docker build (`context: src/tax-optimization-service`)
  - No new DB tables — read-only access to `user_preferences`
  - No-op `scripts/migrate.py`
  - 24 pytest test cases

- **Local Testing Validated (2026-03-09)**
  - Python 3.13.7 arm64 Mac mini
  - All 8 endpoints responding correctly
  - Tax math verified against expected IRS bracket outputs
  - Agent 04 fallback confirmed (DB unavailable — service continues)

---

## Previous Entries

### [Agent 04] — Asset Classification Service — port 8004
### [Agent 03] — Income Scoring Service — port 8003
### [Agent 02] — Newsletter Ingestion Service — port 8002
### [Agent 01] — Market Data Service — port 8001
