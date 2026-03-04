# Agent 05 — Tax Optimization Service
## Implementation Specification

**Version:** 1.0.0
**Status:** Develop Pending
**Port:** 8005
**Last Updated:** 2026-03-04
**Functional Spec:** `documentation/functional/agent-05-tax-optimization-functional-spec.md`

---

## 1. File Structure

```
src/tax-optimization-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py            # Settings via pydantic-settings
│   ├── models.py            # All Pydantic request/response schemas
│   ├── database.py          # Read-only DB — user_preferences only
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # POST /analyze, GET /health
│   └── tax/
│       ├── __init__.py
│       ├── profiler.py      # TaxProfiler
│       ├── calculator.py    # AfterTaxCalculator
│       ├── optimizer.py     # PlacementOptimizer
│       └── harvester.py     # HarvestingScanner
├── scripts/
│   └── migrate.py           # No-op in v1.1
├── tests/
│   ├── __init__.py
│   ├── test_calculator.py
│   ├── test_optimizer.py
│   └── test_harvester.py
├── Dockerfile
└── requirements.txt
```

---

## 2. Requirements

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.8.0
pydantic-settings==2.4.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.9
httpx==0.27.2
pytest==8.3.3
pytest-cov==5.0.0
pytest-mock==3.14.0
```

No numpy, no ML libraries. Pure Python math — lightest requirements of any agent.

---

## 3. Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8005
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
```

Build context: `src/tax-optimization-service` (self-contained — no shared/ dependency).

---

## 4. docker-compose.yml Entry

```yaml
agent-05-tax-optimization:
  build:
    context: src/tax-optimization-service
    dockerfile: Dockerfile
  container_name: agent-05-tax-optimization
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - REDIS_URL=${REDIS_URL}
    - ASSET_CLASSIFICATION_SERVICE_URL=http://agent-04-asset-classification:8004
    - SERVICE_PORT=8005
    - LOG_LEVEL=${LOG_LEVEL:-INFO}
    - PYTHONUNBUFFERED=1
  ports:
    - "8005:8005"
  restart: unless-stopped
  depends_on:
    agent-04-asset-classification:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
```

---

## 5. Module Responsibilities

### app/config.py
```python
class Settings(BaseSettings):
    database_url: str
    redis_url: str
    asset_classification_service_url: str = "http://agent-04-asset-classification:8004"
    service_port: int = 8005
    log_level: str = "INFO"
    # Tax defaults
    default_ordinary_rate: float = 0.22
    default_qualified_rate: float = 0.15
    default_state_rate: float = 0.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### app/database.py
- Read-only async connection to PostgreSQL
- Single query: `SELECT tax_profile FROM user_preferences WHERE user_id = $1`
- Returns `TaxProfile | None`
- No writes, no schema changes

### app/tax/profiler.py — TaxProfiler
- Input: holding with optional `tax_efficiency` block
- If `tax_efficiency` present in payload → use it, set `tax_profile_source: "payload"`
- If absent → call Agent 04 via `httpx.AsyncClient`
- If Agent 04 unavailable → use `ORDINARY_INCOME` defaults, set `tax_profile_source: "conservative_default"`
- Returns enriched holding with `tax_profile_source` field populated

### app/tax/calculator.py — AfterTaxCalculator
- Input: enriched holding + resolved `TaxProfile`
- Output: `AfterTaxYieldRow` with yields for all 4 account types
- Pure math, no I/O, fully unit-testable
- Formula:
  ```
  taxable_yield = gross_yield * (1 - applicable_rate)
  deferred_yield = gross_yield  (tax deferred — TradIRA/401k)
  free_yield = gross_yield      (tax free — Roth)
  roc_yield = gross_yield       (return of capital — no tax until sale)
  ```

### app/tax/optimizer.py — PlacementOptimizer
- Input: list of `AfterTaxYieldRow` + current account for each holding
- Output: ranked `PlacementRecommendation` list
- Logic: for each holding, compare current account yield vs optimal account yield
  → if delta > threshold (0.5% annual), generate recommendation
  → priority: HIGH (>2%), MEDIUM (1-2%), LOW (<1%)
- Also computes `portfolio_tax_score`, `annual_tax_drag_current`, `annual_tax_drag_optimized`

### app/tax/harvester.py — HarvestingScanner
- Input: holdings with `cost_basis` and `current_price`
- Skip holdings where either field is absent
- Output: `HarvestingCandidate` list for holdings with unrealized loss
- `estimated_tax_savings = abs(unrealized_loss) * ordinary_rate`
- `wash_sale_warning`: True if same ticker purchased within 30 days (v1.1: always False — placeholder)

### scripts/migrate.py
```python
"""Agent 05: No migrations required in v1.1 — no new DB tables."""
import sys
print("Agent 05: No migrations required in v1.1")
sys.exit(0)
```

---

## 6. Pydantic Models (app/models.py)

```python
# Key models — implement all in models.py

class AccountType(str, Enum):
    TAXABLE = "TAXABLE"
    TRAD_IRA = "TRAD_IRA"
    ROTH = "ROTH"
    K401 = "401K"

class IncomeType(str, Enum):
    ORDINARY = "ORDINARY"
    QUALIFIED = "QUALIFIED"
    ROC = "ROC"
    SHORT_TERM = "SHORT_TERM"

class TaxEfficiency(BaseModel):
    income_type: IncomeType
    tax_drag_pct: float
    preferred_account: AccountType

class Holding(BaseModel):
    ticker: str
    account_type: AccountType
    current_value: float
    annual_income: float
    current_price: Optional[float] = None
    cost_basis: Optional[float] = None
    tax_efficiency: Optional[TaxEfficiency] = None

class TaxProfile(BaseModel):
    ordinary_rate: float = 0.22
    qualified_rate: float = 0.15
    state_rate: float = 0.0

class AnalyzeRequest(BaseModel):
    user_id: Optional[str] = None
    holdings: List[Holding]
    tax_profile: Optional[TaxProfile] = None

class PlacementRecommendation(BaseModel):
    ticker: str
    current_account: AccountType
    recommended_account: AccountType
    annual_savings_estimate: float
    priority: str  # HIGH | MEDIUM | LOW
    rationale: str

class HarvestingCandidate(BaseModel):
    ticker: str
    current_price: float
    cost_basis: float
    unrealized_loss: float
    estimated_tax_savings: float
    wash_sale_warning: bool

class AfterTaxYieldRow(BaseModel):
    ticker: str
    gross_yield_pct: float
    income_type: IncomeType
    tax_profile_source: str  # payload | agent04 | user_preferences | conservative_default
    after_tax_yield_taxable: float
    after_tax_yield_trad_ira: float
    after_tax_yield_roth: float
    current_account: AccountType
    optimal_account: AccountType

class AnalyzeResponse(BaseModel):
    portfolio_tax_score: int
    annual_tax_drag_current: float
    annual_tax_drag_optimized: float
    annual_savings_potential: float
    after_tax_yield_table: List[AfterTaxYieldRow]
    placement_recommendations: List[PlacementRecommendation]
    harvesting_candidates: List[HarvestingCandidate]
    service: str = "agent-05-tax-optimization"
    version: str = "1.0.0"
    timestamp: str
```

---

## 7. Test Cases

### test_calculator.py
```python
# JEPI ORDINARY in TAXABLE: gross 7.0% → net 5.46% at 22%
def test_ordinary_taxable_drag():
    row = calculate(ticker="JEPI", gross_yield=0.07, income_type=ORDINARY,
                    account=TAXABLE, profile=TaxProfile(ordinary_rate=0.22))
    assert row.after_tax_yield_taxable == pytest.approx(0.0546, rel=1e-3)

# SCHD QUALIFIED in TAXABLE: gross 3.5% → net 2.975% at 15%
def test_qualified_taxable_drag():
    ...

# Any holding in ROTH: gross == net
def test_roth_no_drag():
    ...

# ROC in TAXABLE: gross == net (deferred)
def test_roc_no_immediate_drag():
    ...
```

### test_optimizer.py
```python
# ORDINARY in TAXABLE → HIGH priority ROTH recommendation
# QUALIFIED in ROTH → recommend move to TAXABLE
# ROC anywhere → no recommendation (no drag)
# Delta below threshold → no recommendation generated
```

### test_harvester.py
```python
# Unrealized loss → appears as candidate
# Unrealized gain → excluded
# Missing cost_basis → gracefully excluded
# Missing current_price → gracefully excluded
```

---

## 8. Implementation Order (Claude Code)

1. `app/models.py` — all Pydantic schemas first
2. `app/config.py` — settings
3. `app/database.py` — user_preferences read
4. `app/tax/profiler.py` — Agent 04 call + fallback
5. `app/tax/calculator.py` — pure math
6. `app/tax/optimizer.py` — placement logic
7. `app/tax/harvester.py` — harvesting logic
8. `app/api/routes.py` — wire everything together
9. `app/main.py` — FastAPI app + /health
10. `scripts/migrate.py` — no-op
11. `tests/` — unit tests
12. `Dockerfile` + add to `docker-compose.yml`

---

## 9. Test Tickers for Validation

| Ticker | Income Type | Suggested Account |
|---|---|---|
| JEPI | ORDINARY | ROTH (covered call ETF — ordinary income) |
| SCHD | QUALIFIED | TAXABLE (qualified dividends — tax-favored already) |
| VNQ | ORDINARY/ROC mix | ROTH (REIT — mostly ordinary) |
| BND | ORDINARY | TRAD_IRA (bond interest — fully ordinary) |
| O | ORDINARY/ROC | ROTH or TRAD_IRA |
