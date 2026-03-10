# CHANGELOG — Agent 03: Income Scoring Service

---

## [1.1.0] — 2026-03-09 — Amendment A2

### Added
- **Chowder Number** computed from `features_historical` (yield_trailing_12m + div_cagr_5y)
- **`chowder_signal`** classification: ATTRACTIVE / BORDERLINE / UNATTRACTIVE / INSUFFICIENT_DATA
- **Asset-class aware thresholds**: DIVIDEND_STOCK (12/8), COVERED_CALL_ETF + BOND (8/5)
- **`get_features()`** in `data_client.py` — asyncpg direct read from `platform_shared.features_historical`
- **`chowder_number`** and **`chowder_signal`** added to `ScoreResponse` (Optional, default None)
- **`chowder_number`** and **`chowder_signal`** added to `factor_details` JSONB
- **Fallback path**: uses pre-computed `chowder_number` from DB when yield_trailing_12m absent
- **17 new unit tests** in `tests/test_chowder.py` (all passing)
- `asyncpg==0.30.0` added to requirements

### Changed
- `income_scorer.py`: chowder inputs now sourced from `features_historical` not `fundamentals`
- `_compute_chowder()` delegates signal logic to shared `_chowder_signal_from_number()`
- `test_income_scorer.py`: updated to handle chowder scalar fields alongside factor dicts

### Notes
- Chowder weight = **0%** — total_score, grade, recommendation unchanged
- ADR-P11 filed: sector-aware threshold refinement deferred to before Agent 12 design
- Pre-existing test failures in `test_quality_gate.py` unrelated to this update

---

## [1.0.0] — 2026-01-XX

### Added
- Initial deployment
- Quality gate engine (credit rating, FCF, dividend history, AUM, track record)
- Weighted scoring: valuation/yield (40%), financial durability (35%), technical entry (25%)
- NAV erosion Monte Carlo penalty for covered call ETFs
- Endpoints: /scores/evaluate, /scores/, /scores/{ticker}, /quality-gate/evaluate
