# Decisions Log — Agent 04 Asset Classification Service

**Last Updated:** 2026-02-27

---

## ADR-04-001 — Shared Utility vs Service-Only Classification

**Date:** 2026-02-27  
**Status:** Accepted

**Context:**  
Classification logic could live entirely inside Agent 04 (accessed only via HTTP) or be extracted into a shared utility importable by any agent directly.

**Decision:**  
Extracted to `src/shared/asset_class_detector/` — importable directly by any agent.

**Rationale:**  
- Agent 03 needs asset class at scoring time to apply class-specific quality gates
- Requiring an HTTP call to Agent 04 from Agent 03 would create a hard dependency and latency
- Shared utility enables fallback classification when Agent 04 is unavailable
- Rule-based logic is deterministic and has no side effects — safe to run in-process

**Consequences:**  
- All agents must have `src/shared/` on their PYTHONPATH
- Changes to taxonomy require redeployment of all consuming agents
- DB-driven rules only available through Agent 04 HTTP call; in-process always uses seed rules

---

## ADR-04-002 — 7 MVP Asset Classes (Not More, Not Fewer)

**Date:** 2026-02-27  
**Status:** Accepted

**Context:**  
Platform covers a wide range of income securities. Could classify with 3 broad classes or 20+ granular ones.

**Decision:**  
7 classes: DIVIDEND_STOCK, COVERED_CALL_ETF, BOND, EQUITY_REIT, MORTGAGE_REIT, BDC, PREFERRED_STOCK.

**Rationale:**  
- Each class has a structurally distinct valuation method (accounting identity — not a preference)
- 7 classes map cleanly to distinct tax treatments and account placement rules
- Fewer classes would collapse meaningful yield trap signals (e.g., MORTGAGE_REIT NAV erosion vs EQUITY_REIT stability)
- More classes would require enrichment data not available from current providers

**Consequences:**  
- CLOs, interval funds, royalty trusts, CEFs remain UNKNOWN until v1.1 taxonomy expansion
- UNKNOWN class triggers Agent 01 enrichment attempt before fallback to DIVIDEND_STOCK

---

## ADR-04-003 — Tax Efficiency at 0% Composite Weight

**Date:** 2026-02-27  
**Status:** Accepted

**Context:**  
Tax efficiency output could be factored into the income score or kept as a parallel, informational-only output.

**Decision:**  
Tax efficiency is always populated but carries 0% weight in composite income score.

**Rationale:**  
- Tax impact is highly individual (tax bracket, account allocation, harvesting strategy)
- Baking tax drag into the income score would produce scores that differ per user with same security
- Agent 05 (Tax Optimizer) is the correct consumer — it has user-level account context
- Score must reflect security quality, not user-specific tax situation

**Consequences:**  
- All tax-aware decisions deferred to Agent 05
- `tax_efficiency` field always populated even for VETO'd securities
- Florida-specific: no state tax calculations (expandable in Agent 05)

---

## ADR-04-004 — Root .env Centralization

**Date:** 2026-02-27  
**Status:** Accepted

**Context:**  
Each agent had its own `.env` file containing duplicate credentials. Rotating credentials required updating 4+ files.

**Decision:**  
Single root `.env` at `income-platform/` root. Service identity variables (`SERVICE_NAME`, `SERVICE_PORT`, `LOG_LEVEL`, `ENVIRONMENT`) moved to `config.py` defaults.

**Pattern:**
```python
class Config:
    env_file = ("../../.env", ".env")  # root first, local override second
```

**Rationale:**  
- Single credential rotation point
- Service identity belongs in code (version controlled), not environment
- Local `.env` override still available per-service if needed

**Consequences:**  
- All agents must be started from their service directory (`src/agent-name/`) for relative path resolution
- Docker deployments use `ENV` vars directly — no `.env` file at all in production
- `.gitignore` must cover both `/.env` and `src/*/.env`

---

## ADR-04-005 — Python 3.13 as Development Runtime

**Date:** 2026-02-27  
**Status:** Accepted

**Context:**  
Mac development environment had both Python 3.9 (system) and 3.13 (framework install). Initial deployment targeted 3.9.

**Decision:**  
Standardize on Python 3.13 for local development. Use `python3 -m uvicorn` (not bare `uvicorn`) to ensure interpreter consistency across reloader subprocess.

**Rationale:**  
- Python 3.9 `list[X]` / `dict[X]` / `X | None` syntax not supported — causes failures
- Python 3.13 is current stable — better to align now than carry compatibility shims
- Production Docker uses explicit Python version (unaffected by local version)
- `python3 -m uvicorn` ensures PYTHONPATH and interpreter stay consistent in subprocess

**Consequences:**  
- All `Optional[X]`, `List[X]`, `Dict[X]` from `typing` module used (no bare `X | None`)
- Install target: `/Library/Frameworks/Python.framework/Versions/3.13/bin/pip3`
- CI/CD must specify Python 3.13 explicitly

---

## ADR-04-006 — DB-Driven Rules with Seed Fallback

**Date:** 2026-02-27  
**Status:** Accepted

**Context:**  
Classification rules could be hardcoded in source or stored in the database.

**Decision:**  
Rules stored in `platform_shared.asset_class_rules`. Seed rules in `seed_rules.py` used as fallback and for initial migration seeding. Engine loads DB rules at startup, falls back to seed rules if DB unavailable.

**Rationale:**  
- New instrument types (CLOs, royalty trusts) can be added via API without redeploy
- Rules are versioned in DB with `created_at` timestamp
- Seed rules provide known-good baseline for testing and disaster recovery
- Priority + confidence_weight fields enable fine-grained tuning without code changes

**Consequences:**  
- `POST /rules` endpoint must be protected in production (auth — Agent 12 roadmap)
- Rule changes take effect on next cache miss (24hr max lag for cached securities)
- Seed rules are immutable reference — DB rules override but don't replace them
