# CHANGELOG — Agent 04 Asset Classification Service

All notable changes to the Asset Classification Service.

---

## [1.0.0] — 2026-02-27

### Added
- `src/shared/asset_class_detector/` — shared classification utility
  - `taxonomy.py` — 7 asset classes with full characteristics
  - `rule_matcher.py` — 4 rule types with weighted confidence scoring
  - `seed_rules.py` — 19 seed rules covering all 7 MVP classes
  - `detector.py` — `AssetClassDetector` with `detect()` and `detect_with_fallback()`
- Agent 04 service on port 8004
  - `app/config.py` — centralized config with root `.env` pattern
  - `app/database.py` — SQLAlchemy engine with connection verification
  - `app/models.py` — 3 ORM models: `AssetClassification`, `AssetClassRule`, `ClassificationOverride`
  - `app/classification/engine.py` — full 7-step classification pipeline
  - `app/classification/benchmarks.py` — class-specific peer groups and benchmark values
  - `app/classification/tax_profile.py` — tax drag estimates and account placement
  - `app/classification/data_client.py` — Agent 01 enrichment HTTP client
  - `app/api/classify.py` — POST /classify, POST /classify/batch, GET /classify/{ticker}
  - `app/api/rules.py` — GET/POST /rules, PUT/DELETE /overrides/{ticker}
  - `app/api/health.py` — GET /health
  - `scripts/migrate.py` — creates 3 tables + seeds 19 rules
- 55 unit tests, 100% passing

### Infrastructure
- Root `.env` centralized at `income-platform/` for all agents
- Service identity variables moved to `config.py` defaults
- `platform_shared` schema permissions granted to `dbpmanager`
- Validated with JEPI (COVERED_CALL_ETF), AGNC (MORTGAGE_REIT), ARCC (BDC)

### Fixed (during deployment)
- Python 3.9 → 3.13 migration: `Optional[X]` / `List[X]` / `Dict[X]` throughout
- `shared` module not found in uvicorn subprocess: absolute PYTHONPATH required
- `cast(:x as jsonb)` vs `::jsonb` parameter style conflict in migrate.py
- `platform_shared` schema permission denied: granted USAGE+CREATE to `dbpmanager` via `doadmin`
- Service identity showing agent-03: removed identity vars from root `.env`
