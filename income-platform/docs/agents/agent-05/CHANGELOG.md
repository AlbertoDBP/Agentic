# CHANGELOG — Agent 05 Tax Optimization Service

All notable changes to the Tax Optimization Service.

---

## [1.0.1] — 2026-03-12

### Fixed
- `app/config.py`: replaced Pydantic v2 deprecated `class Config` with `model_config = ConfigDict(env_file=..., case_sensitive=False)`

### Tests
- 135 tests passing (2 files) — no new tests added, no regressions

---

## [1.0.0] — 2026-02-27

### Added
- Tax profiler: `app/tax/profiler.py` — 8 asset class profiles, Agent 04 integration with fallback
- Tax calculator: `app/tax/calculator.py` — 2024 IRS brackets (all 4 filing statuses), all 50 states + DC, NIIT support, Section 1256 60/40 treatment
- Portfolio optimizer: `app/tax/optimizer.py` — account placement heuristics to minimize tax drag
- Tax harvester: `app/tax/harvester.py` — wash-sale-aware harvesting opportunity identification
- 8 API endpoints (GET/POST profile, calculate, optimize, harvest, asset-classes)
- Pydantic models: `AssetClass`, `TaxTreatment`, `AccountType`, `FilingStatus` enums
- Full request/response schemas for all 4 capabilities
- 135 unit tests across `test_tax_optimization.py` (30 tests) and `test_tax_extended.py` (105 tests)

### Architecture Decisions
- Rule-based engine only — no external tax API dependencies
- Agent 04 integration via HTTP with 3-second timeout; graceful fallback to ORDINARY_INCOME
- Tax-sheltered accounts (IRA, Roth, 401K, HSA) short-circuit all calculations (0 tax)
- Florida (FL) state rate = 0.00 — primary deployment state; all 50 states + DC supported
- Proposals only — no trade execution, no account writes
