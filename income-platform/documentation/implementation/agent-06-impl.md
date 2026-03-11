# Implementation Specification — Agent 06: Scenario Simulation Service v1.0.0

**Version:** 1.0.0
**Date:** 2026-03-11
**Status:** Built — 33/33 tests passing — Ready for deployment

---

## File Structure

```
src/scenario-simulation-service/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py                      — ScenarioResult ORM (schema=platform_shared)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── scenarios.py               — 4 endpoints
│   └── simulation/
│       ├── __init__.py
│       ├── scenario_library.py        — 5 predefined scenarios × 7 asset classes
│       ├── stress_engine.py           — shock application + vulnerability ranking
│       ├── income_projector.py        — Monte Carlo P10/P50/P90
│       └── portfolio_reader.py        — asyncpg reads from platform_shared
├── scripts/
│   └── migrate.py                     — idempotent DDL for scenario_results
├── requirements.txt
├── Dockerfile
└── tests/
    ├── __init__.py
    ├── test_stress_engine.py          — 12 tests
    ├── test_income_projector.py       — 8 tests
    ├── test_scenario_library.py       — 6 tests
    └── test_api.py                    — 7 tests
```

---

## Module Details

### `app/simulation/scenario_library.py`

```python
SCENARIO_LIBRARY = {
    "RATE_HIKE_200BPS": {
        "EQUITY_REIT":      {"price_pct": -15, "income_pct": -5},
        "MORTGAGE_REIT":    {"price_pct": -20, "income_pct": -12},
        "BDC":              {"price_pct": -10, "income_pct": -8},
        "COVERED_CALL_ETF": {"price_pct": -8,  "income_pct": -3},
        "DIVIDEND_STOCK":   {"price_pct": -5,  "income_pct": -2},
        "BOND":             {"price_pct": -12, "income_pct":  0},
        "PREFERRED_STOCK":  {"price_pct": -8,  "income_pct":  0},
    },
    "MARKET_CORRECTION_20": { ... },
    "RECESSION_MILD": { ... },      # BOND price_pct = +3 (flight to safety)
    "INFLATION_SPIKE": { ... },     # EQUITY_REIT income_pct = +5 (pricing power)
    "CREDIT_STRESS": { ... },       # MORTGAGE_REIT price_pct = -30, income_pct = -20
}
```

Functions:
- `get_scenario(name)` → dict — raises `ValueError` if not found
- `list_scenarios()` → list[dict] — name + description + shock table
- `build_custom_scenario(shocks)` → dict — validates and returns shock table

### `app/simulation/portfolio_reader.py`

asyncpg direct reads. Never raises — returns `[]` or `{}` on any error.

```python
async def get_positions(portfolio_id: str, as_of_date: Optional[date] = None) -> list[dict]:
    # SELECT symbol, quantity, current_value, annual_income,
    #        yield_on_value, portfolio_weight_pct, avg_cost_basis
    # FROM platform_shared.positions
    # WHERE portfolio_id = $1 AND status = 'OPEN'

async def get_asset_classes(symbols: list[str]) -> dict[str, str]:
    # SELECT symbol, asset_class FROM platform_shared.asset_classifications
    # WHERE symbol = ANY($1)
    # Missing symbols → default "DIVIDEND_STOCK"
```

### `app/simulation/stress_engine.py`

```python
@dataclass
class PositionImpact:
    symbol: str
    asset_class: str
    current_value: float
    stressed_value: float
    current_income: float
    stressed_income: float
    value_change_pct: float
    income_change_pct: float
    vulnerability_rank: int = 0

@dataclass
class StressResult:
    portfolio_id: str
    scenario_name: str
    portfolio_value_before: float
    portfolio_value_after: float
    value_change_pct: float
    annual_income_before: float
    annual_income_after: float
    income_change_pct: float
    position_impacts: list[PositionImpact]
    computed_at: datetime

class StressEngine:
    def run(self, positions, asset_classes, scenario_shocks,
            portfolio_id, scenario_name) -> StressResult
```

Vulnerability rank: sorted by `abs(value_change_pct)` descending → rank 1 = most impacted.
Zero-division safe: returns 0.0 for pct fields when value/income is 0.

### `app/simulation/income_projector.py`

```python
class IncomeProjector:
    N_SIMULATIONS = 1000
    DEFAULT_YIELD_VOLATILITY = 0.05

    def project(self, positions: list[dict], horizon_months: int = 12) -> IncomeProjection
```

Monte Carlo per position: `base_income × exp(N(0, σ) − σ²/2)` where
`σ = DEFAULT_YIELD_VOLATILITY × √(horizon_months / 12)`.

Portfolio totals: sum simulated incomes across positions per simulation → percentiles.

### `app/models.py`

```python
class ScenarioResult(Base):
    __tablename__ = "scenario_results"
    __table_args__ = (
        Index("ix_scenario_results_portfolio", "portfolio_id", "created_at"),
        {"schema": "platform_shared"},
    )

    id: UUID PK
    portfolio_id: UUID not null
    scenario_name: String(50) not null
    scenario_type: String(20) not null      # PREDEFINED | CUSTOM
    scenario_params: JSON nullable
    result_summary: JSON not null
    vulnerability_ranking: JSON nullable
    projected_income_p10: Numeric(12,2)
    projected_income_p50: Numeric(12,2)
    projected_income_p90: Numeric(12,2)
    label: String(200) nullable
    created_at: TIMESTAMPTZ default now()
```

---

## Endpoint Contracts

### POST `/scenarios/stress-test`

```json
Request:
{
  "portfolio_id": "uuid",
  "scenario_type": "RATE_HIKE_200BPS",
  "scenario_params": null,
  "as_of_date": null,
  "save": false,
  "label": null
}

Response:
{
  "portfolio_id": "uuid",
  "scenario_name": "RATE_HIKE_200BPS",
  "portfolio_value_before": 250000.00,
  "portfolio_value_after": 212500.00,
  "value_change_pct": -15.0,
  "annual_income_before": 18650.00,
  "annual_income_after": 17420.00,
  "income_change_pct": -6.6,
  "position_impacts": [
    {
      "symbol": "JEPI",
      "asset_class": "COVERED_CALL_ETF",
      "current_value": 50000,
      "stressed_value": 46000,
      "current_income": 4200,
      "stressed_income": 4074,
      "value_change_pct": -8.0,
      "income_change_pct": -3.0,
      "vulnerability_rank": 3
    }
  ],
  "saved": false,
  "result_id": null,
  "computed_at": "2026-03-11T17:00:00Z"
}
```

### POST `/scenarios/income-projection`

```json
Request:  { "portfolio_id": "uuid", "horizon_months": 12 }
Response: {
  "portfolio_id": "uuid",
  "horizon_months": 12,
  "projected_income_p10": 16800.00,
  "projected_income_p50": 18650.00,
  "projected_income_p90": 20100.00,
  "by_position": [
    {"symbol": "JEPI", "base_income": 4200, "p10": 3800, "p50": 4200, "p90": 4650}
  ],
  "computed_at": "2026-03-11T17:00:00Z"
}
```

### POST `/scenarios/vulnerability`

```json
Request:  {
  "portfolio_id": "uuid",
  "scenario_types": ["RATE_HIKE_200BPS", "RECESSION_MILD"]
}
Response: {
  "portfolio_id": "uuid",
  "rankings": [
    {
      "symbol": "O",
      "worst_scenario": "RECESSION_MILD",
      "max_value_loss_pct": -18.0,
      "rank": 1
    }
  ]
}
```

---

## DB Migration

`scripts/migrate.py` — run from service root:

```python
# sys.path.insert(0, "..")
# Creates platform_shared.scenario_results (IF NOT EXISTS)
# Idempotent — safe to re-run
```

---

## Docker Compose Entry

```yaml
agent-06-scenario-simulation:
  build:
    context: src/scenario-simulation-service
    dockerfile: Dockerfile
  container_name: agent-06-scenario-simulation
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - SERVICE_PORT=8006
    - LOG_LEVEL=${LOG_LEVEL:-INFO}
  ports:
    - "8006:8006"
  restart: unless-stopped
```

---

## Testing

### Test Results
**33/33 tests passing**

| File | Tests | Coverage |
|------|-------|---------|
| `test_stress_engine.py` | 12 | All 7 asset classes, zero-division, vulnerability ranking |
| `test_income_projector.py` | 8 | P10<P50<P90, horizon scaling, empty positions |
| `test_scenario_library.py` | 6 | All 5 scenarios, custom validation, ValueError |
| `test_api.py` | 7 | All endpoints, 422 handling |

### Acceptance Criteria (Testable)

- [ ] `GET /scenarios/library` returns 5 predefined scenarios
- [ ] `POST /scenarios/stress-test` with JEPI (COVERED_CALL_ETF) applies -8% price shock for RATE_HIKE_200BPS
- [ ] `POST /scenarios/stress-test` with BOND position in RECESSION_MILD returns positive `value_change_pct`
- [ ] `POST /scenarios/stress-test` with empty portfolio returns 422
- [ ] `POST /scenarios/stress-test` with `save: true` persists to `scenario_results` and returns non-null `result_id`
- [ ] `POST /scenarios/income-projection` returns P10 < P50 < P90
- [ ] CUSTOM scenario applies user-defined shocks correctly
- [ ] 33/33 unit tests pass

---

## Deployment

```bash
# On server — after git pull
cd /opt/Agentic/income-platform

# Run migration first
docker compose run --rm agent-06-scenario-simulation \
  python scripts/migrate.py

# Grant permissions
docker exec agent-06-scenario-simulation python3 -c "
import asyncio, asyncpg, os
async def fix():
    url = os.environ['DATABASE_URL'].split('?')[0]
    conn = await asyncpg.connect(url, ssl='require')
    await conn.execute('''
        GRANT SELECT, INSERT, UPDATE ON
            platform_shared.scenario_results
        TO doadmin
    ''')
    print('Done')
    await conn.close()
asyncio.run(fix())
"

# Build and start
docker compose build --no-cache agent-06-scenario-simulation
docker compose up -d agent-06-scenario-simulation
```

### Smoke Test

```bash
# Health
curl https://legatoinvest.com/api/scenario-simulation/health

# Library
curl https://legatoinvest.com/api/scenario-simulation/scenarios/library
```

---

## Implementation Notes

- asyncpg opens new connection per call in `portfolio_reader.py` — acceptable for v1;
  connection pooling can be added in v2 if latency becomes an issue
- Monte Carlo uses `np.random.default_rng()` — not seeded in production for true randomness;
  tests use explicit seed for determinism
- ADR-P12: ElasticNet GLM deferred to v2 when `features_historical` has 24+ months depth
- ADR-P11 (Chowder thresholds) and ADR-P12 (GLM) both trigger review before Agent 12 design
