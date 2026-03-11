# CHANGELOG — Agent 06: Scenario Simulation Service

---

## [1.0.0] — 2026-03-11 — Initial Release

### Added
- **5 predefined scenarios**: RATE_HIKE_200BPS, MARKET_CORRECTION_20, RECESSION_MILD,
  INFLATION_SPIKE, CREDIT_STRESS
- **Asset-class shock table**: 7 asset classes × 5 scenarios (ADR-P12 — GLM deferred to v2)
- **Custom scenario support**: uniform shock structure, NL/LLM compatible
- **`POST /scenarios/stress-test`**: predefined or custom, optional `save: true` + `label`
- **`POST /scenarios/income-projection`**: Monte Carlo N=1000, 1–60 month horizon, P10/P50/P90
- **`POST /scenarios/vulnerability`**: cross-scenario worst-case ranking per symbol
- **`GET /scenarios/library`**: all 5 predefined scenarios with full shock tables
- **`platform_shared.scenario_results`** table (explicit save only)
- **asyncpg direct reads** from `positions` + `asset_classifications`
- **33 unit tests** (12 stress engine, 8 income projector, 6 scenario library, 7 API)

### Architecture Decisions
- ADR-P12: Asset-class shock table in v1; ElasticNet GLM deferred to v2
  (trigger: 24+ months of features_historical depth)
- Always portfolio_id scoped — no ad-hoc position lists
- Explicit save only — scenario_results table stays clean
- No inter-agent HTTP — reads platform_shared directly

### Notes
- BOND in RECESSION_MILD has positive price_pct (+3%) — flight to safety
- INFLATION_SPIKE EQUITY_REIT income_pct positive (+5%) — pricing power
- MORTGAGE_REIT hardest hit in CREDIT_STRESS (-30% price, -20% income)
