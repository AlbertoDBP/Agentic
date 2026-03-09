# Agent 05 — Tax Optimization Service: Implementation Specification

**Version:** 1.0.0
**Date:** 2026-03-09
**Status:** Complete — Deployed Locally, Pending Production
**Functional Spec:** `documentation/functional/agent-05-tax-optimization-functional-spec.md`

---

## 1. Technical Design

### 1.1 Architecture

```
Request
  │
  ▼
app/api/routes.py          ← FastAPI route handlers (8 endpoints)
  │
  ├── /tax/profile/*  ──► app/tax/profiler.py
  │                          └── Agent 04 callout (httpx, 3s timeout)
  │                          └── _PROFILE_MAP (in-memory lookup)
  │
  ├── /tax/calculate/* ──► app/tax/calculator.py
  │                          └── profiler.py (asset class resolution)
  │                          └── IRS bracket tables (in-memory constants)
  │                          └── State rate table (in-memory constants)
  │
  ├── /tax/optimize   ──► app/tax/optimizer.py
  │                          └── profiler.py + calculator.py per holding
  │
  └── /tax/harvest    ──► app/tax/harvester.py
                             └── calculator._state_rate() for loss tax value
```

### 1.2 Module Responsibilities

| Module | Responsibility | External Calls |
|---|---|---|
| `profiler.py` | Asset class → tax treatment mapping | Agent 04 (optional) |
| `calculator.py` | Federal + state + NIIT computation | None |
| `optimizer.py` | Account placement recommendations | profiler + calculator |
| `harvester.py` | Loss harvesting opportunity scoring | calculator._state_rate |
| `routes.py` | HTTP request/response handling | None |
| `database.py` | user_preferences read-only access | PostgreSQL (optional) |

---

## 2. API / Interface Details

### 2.1 GET `/tax/profile/{symbol}`

```
Query params:
  asset_class: AssetClass (optional)
  filing_status: FilingStatus = SINGLE
  state_code: str (2-char, optional)
  account_type: AccountType = TAXABLE
  annual_income: float (optional)

Response: TaxProfileResponse
  symbol: str
  asset_class: AssetClass
  asset_class_fallback: bool        ← True when Agent 04 unavailable
  primary_tax_treatment: TaxTreatment
  secondary_treatments: list[TaxTreatment]
  qualified_dividend_eligible: bool
  section_199a_eligible: bool
  section_1256_eligible: bool
  k1_required: bool
  notes: list[str]
```

### 2.2 POST `/tax/calculate`

```
Body: TaxCalculationRequest
  symbol: str
  annual_income: float
  filing_status: FilingStatus
  state_code: str (optional)
  account_type: AccountType
  distribution_amount: float        ← annual gross distribution per share
  asset_class: AssetClass (optional)

Response: TaxCalculationResponse
  gross_distribution: float
  federal_tax_owed: float
  state_tax_owed: float
  niit_owed: float
  total_tax_owed: float
  net_distribution: float
  effective_tax_rate: float         ← 0.0–1.0
  after_tax_yield_uplift: float     ← vs treating as pure ordinary income
  bracket_detail: list[TaxBracketDetail]
  notes: list[str]
```

### 2.3 POST `/tax/optimize`

```
Body: OptimizationRequest
  holdings: list[HoldingInput]
    symbol, asset_class (optional), account_type, current_value, annual_yield
  annual_income: float
  filing_status: FilingStatus
  state_code: str (optional)

Response: OptimizationResponse
  total_portfolio_value: float
  current_annual_tax_burden: float
  optimized_annual_tax_burden: float
  estimated_annual_savings: float
  placement_recommendations: list[PlacementRecommendation]
    symbol, current_account, recommended_account, reason,
    estimated_annual_tax_savings
  summary: str
  notes: list[str]
```

### 2.4 POST `/tax/harvest`

```
Body: HarvestingRequest
  candidates: list[HarvestingCandidate]
    symbol, current_value, cost_basis, holding_period_days, account_type
  annual_income: float
  filing_status: FilingStatus
  state_code: str (optional)
  wash_sale_check: bool = True

Response: HarvestingResponse
  total_harvestable_losses: float
  total_estimated_tax_savings: float
  opportunities: list[HarvestingOpportunity]
    symbol, unrealized_loss, tax_savings_estimated, holding_period_days,
    long_term, wash_sale_risk, action, rationale
  wash_sale_warnings: list[str]
  notes: list[str]
```

---

## 3. File Structure

```
src/tax-optimization-service/
├── app/
│   ├── __init__.py
│   ├── models.py              # All Pydantic schemas and enums
│   ├── config.py              # Settings via pydantic-settings
│   ├── database.py            # Async SQLAlchemy, read-only session
│   ├── main.py                # FastAPI app, CORS, startup/shutdown hooks
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # All 8 route handlers
│   └── tax/
│       ├── __init__.py
│       ├── profiler.py        # Tax treatment profiles + Agent 04 callout
│       ├── calculator.py      # IRS brackets, state rates, NIIT
│       ├── optimizer.py       # Account placement engine
│       └── harvester.py       # Loss harvesting scanner
├── scripts/
│   └── migrate.py             # No-op — documents read-only intent
├── tests/
│   ├── __init__.py
│   └── test_tax_optimization.py   # 24 test cases
├── Dockerfile                 # python:3.11-slim, port 8005
├── requirements.txt           # Pinned for Python 3.13 arm64 (local dev)
├── pytest.ini                 # asyncio_mode = auto
└── docker-compose-stanza.yml  # Append to root docker-compose.yml
```

---

## 4. Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `postgresql://...@db:5432/income_platform` | Yes (prod) | Shared platform DB |
| `ASSET_CLASSIFICATION_URL` | `http://asset-classification-service:8004` | No | Agent 04 base URL |
| `LOG_LEVEL` | `INFO` | No | Logging verbosity |
| `DEBUG` | `false` | No | FastAPI debug mode |

---

## 5. Dependencies & Versions

### Production (Python 3.11 Docker)
```
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
pydantic-core==2.27.1
pydantic-settings==2.7.0
sqlalchemy==2.0.36
asyncpg==0.30.0
httpx==0.28.1
python-dotenv==1.0.1
```

### Local Dev (Python 3.13 arm64 Mac)
Same versions — all have pre-built `cp313-cp313-macosx_11_0_arm64` wheels.
Install with `--only-binary :all:` for `pydantic` and `asyncpg`.

---

## 6. Docker Configuration

```dockerfile
FROM python:3.11-slim
WORKDIR /app
EXPOSE 8005
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1"]
```

**docker-compose service** depends on:
- `db` (condition: service_healthy)
- Optional: `asset-classification-service` (soft dependency, no condition)

---

## 7. Tax Data Maintenance

The following constants in `calculator.py` require annual review each January:

| Constant | Description | Last Updated |
|---|---|---|
| `_ORDINARY_BRACKETS` | Federal ordinary income brackets by filing status | 2024 |
| `_QUALIFIED_BRACKETS` | Qualified dividend / LTCG brackets by filing status | 2024 |
| `_NIIT_THRESHOLD` | NIIT income thresholds by filing status | 2024 |
| `_STATE_RATES` | Top marginal state income tax rates (51 jurisdictions) | 2024 |

---

## 8. Testing & Acceptance

### 8.1 Unit Tests (24 cases in `tests/test_tax_optimization.py`)

| Class | Tests | Coverage |
|---|---|---|
| `TestTaxProfiler` | 7 | All asset classes, Agent 04 fallback paths, profile map completeness |
| `TestTaxCalculator` | 6 | Sheltered=zero tax, ordinary rate, qualified < ordinary, ROC=zero, NIIT on/off, state tax |
| `TestTaxOptimizer` | 3 | REIT → shelter, MLP → taxable only, savings non-negative |
| `TestTaxHarvester` | 5 | Gain skipped, qualified loss, wash-sale flag, sheltered=no benefit, small loss=monitor |
| `TestAPIRoutes` | 8 | All endpoints, health, 422 validation on empty inputs |

### 8.2 Run Tests

```bash
cd src/tax-optimization-service
source .venv/bin/activate
pytest tests/ -v
```

### 8.3 Acceptance Criteria (Testable)

| Criteria | Verification |
|---|---|
| JEPI $1k distribution, FL, $100k single → $780 net, 22% effective rate | `GET /tax/calculate/JEPI?...` |
| REIT in TAXABLE → recommends TRAD_IRA or ROTH_IRA | `POST /tax/optimize` |
| MLP recommendation → always TAXABLE | `POST /tax/optimize` with MLP holding |
| $2k long-term loss, TX, $90k → HARVEST_NOW, ~$300 savings | `POST /tax/harvest` |
| ROTH_IRA account → $0 tax on any distribution | `POST /tax/calculate` with ROTH_IRA |
| No asset_class + Agent 04 down → `asset_class_fallback: true` in response | `GET /tax/profile/X` with Agent 04 mocked down |
| DB unavailable → service starts and all rule-based endpoints respond | Start service without DB |

### 8.4 Known Edge Cases

| Edge Case | Handling |
|---|---|
| Agent 04 timeout (>3s) | Falls back to ORDINARY_INCOME, sets fallback flag |
| Agent 04 returns unknown asset class | Defaults to UNKNOWN profile |
| Distribution amount = 0 | Returns all zeros, no division error |
| State code not in table | Returns 0% state rate (conservative) |
| MLP in IRA input | Overrides to TAXABLE with UBTI warning |
| Loss < $100 | MONITOR action, $0 harvesting recommended |
| Holding period < 30 days + loss | REVIEW_WASH_SALE action + warning |
| Sheltered account + loss | HOLD action, $0 savings |

### 8.5 Performance SLAs

| Endpoint | Target p99 |
|---|---|
| `/health` | < 50ms |
| `/tax/asset-classes` | < 50ms |
| `/tax/profile` (with asset_class) | < 100ms |
| `/tax/profile` (Agent 04 callout) | < 3.5s |
| `/tax/calculate` | < 200ms |
| `/tax/optimize` (10 holdings) | < 500ms |
| `/tax/harvest` (10 candidates) | < 300ms |

---

## 9. Deployment

### Local (Mac, Python 3.13)

```bash
cd src/tax-optimization-service
python3 -m venv .venv && source .venv/bin/activate
pip install --only-binary :all: pydantic==2.10.3 pydantic-core==2.27.1 asyncpg==0.30.0
pip install "fastapi==0.115.6" "uvicorn[standard]==0.32.1" pydantic-settings==2.7.0 \
    sqlalchemy==2.0.36 httpx==0.28.1 python-dotenv==1.0.1
uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
```

### Production (DigitalOcean Docker)

```bash
# From monorepo root
docker compose up --build tax-optimization-service

# Verify
curl https://legatoinvest.com/api/agent05/health
```

### Migration

```bash
python scripts/migrate.py
# Output: "Migration complete — no-op"
```

---

## 10. Implementation Notes

- **No Alembic** — platform standard is `scripts/migrate.py` with `sys.path.insert(0, "..")`
- **Async throughout** — all DB and HTTP calls use `async/await`; no blocking I/O
- **`_PROFILE_MAP` is the source of truth** — both `profiler.py` and `routes.py /tax/asset-classes` derive from it, ensuring consistency
- **`after_tax_yield_uplift`** — expresses the tax advantage vs treating the same distribution as pure ordinary income; useful for comparing asset classes at the same yield
- **Section 1256 note** — flagged as `section_1256_eligible: True` for all covered call ETFs as a conservative awareness flag; the actual eligibility depends on the fund's underlying holdings (futures vs. equity options)
- **Python 3.13 local dev** — use `--only-binary :all:` for pydantic-core and asyncpg to avoid Rust compilation
