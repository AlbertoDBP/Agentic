# ADR-P12 — Scenario Simulation Model: Shock Table v1, ElasticNet GLM v2

**Status:** Accepted — v1 implemented, v2 migration path documented
**Date:** 2026-03-11

## Context

Agent 06 (Scenario Simulation Service) requires a stress model that applies
market shocks to portfolio positions and projects income/value impact.

Two approaches were evaluated:

**Option A — Asset-Class Shock Table (chosen for v1)**
Predefined percentage shocks per asset class per scenario. Deterministic,
explainable, requires no training data.

**Option B — ElasticNet GLM**
Fit regularized linear regression (L1+L2) on historical return series per
asset class. Produces data-driven beta coefficients. Requires sufficient
historical depth in `features_historical`.

## Decision

**v1: Asset-Class Shock Table**

Shock table implemented in `simulation/scenario_library.py`. Each predefined
scenario (RATE_HIKE_200BPS, MARKET_CORRECTION_20, RECESSION_MILD,
INFLATION_SPIKE, CREDIT_STRESS) defines `price_pct` and `income_pct` shocks
per asset class (7 classes: EQUITY_REIT, MORTGAGE_REIT, BDC, COVERED_CALL_ETF,
DIVIDEND_STOCK, BOND, PREFERRED_STOCK).

Custom scenarios use the same shock table structure — NL/LLM compatible.

## Rationale for Deferring GLM

- `features_historical` launched with Agent 01 v1.1.0 (March 2026)
- GLM requires minimum 24 months of return observations per asset class
  for stable coefficient estimation
- ElasticNet adds scikit-learn dependency and a model training/refit pipeline
  (scheduled refit, model versioning, coefficient drift detection)
- Shock table values are sourced from established DGI/income investing
  literature and are defensible without empirical fitting

## v2 Migration Path — ElasticNet GLM

**Trigger:** `features_historical` has 24+ months of data (est. Q1 2028)

**Implementation plan:**
1. Add `model_coefficients` table to `platform_shared` — stores fitted
   beta coefficients per asset class per scenario type
2. Add `scripts/fit_glm.py` — ElasticNet training script (scikit-learn),
   scheduled monthly via cron/Prefect
3. Add `simulation/glm_engine.py` — replaces `stress_engine.py` shock
   table lookup with matrix multiplication on fitted coefficients
4. Keep shock table as fallback when GLM confidence interval is wide
   (sparse data for a given asset class)
5. A/B validate: run both models in parallel for one quarter, compare
   stress test outcomes against realized drawdowns

**scikit-learn additions required:**
```
scikit-learn>=1.4.0
joblib>=1.3.0   # model serialization
```

**ADR to create at migration:** ADR-P12b — ElasticNet GLM Production Rollout

## Consequences

- v1 shock table values require periodic manual review as market regimes change
- Custom scenario shocks are user-defined — no statistical validation
- GLM migration will require backward compatibility for saved scenario_results
  (store model_version field to distinguish shock-table vs GLM results)

## Review Trigger

Revisit this ADR when:
1. `features_historical` row count exceeds 500 observations per asset class
2. Agent 12 feedback loop surfaces systematic stress test inaccuracies
3. Platform expands to international securities (different beta profiles)
