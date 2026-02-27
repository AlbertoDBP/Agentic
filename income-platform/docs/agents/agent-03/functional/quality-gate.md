# Functional Specification: Quality Gate Engine

**Component:** `app/scoring/quality_gate.py`  
**Version:** 1.0.0  
**Date:** 2026-02-26  
**Status:** Production

---

## Purpose & Scope

The Quality Gate Engine is the first phase of Agent 03's two-phase evaluation pipeline. It performs binary pass/fail evaluation for income-generating assets based on capital preservation criteria. A FAIL result is an absolute VETO — the ticker never reaches the scoring engine regardless of yield attractiveness.

---

## Responsibilities

- Evaluate tickers against asset-class-specific quality criteria
- Return deterministic PASS/FAIL/INSUFFICIENT_DATA results
- Track which individual checks passed/failed with specific fail reasons
- Score data quality (0–100%) based on available fields
- Cache results with 24-hour TTL via `valid_until` timestamp
- Persist results to `platform_shared.quality_gate_results`

---

## Supported Asset Classes

### DIVIDEND_STOCK
| Check | Threshold | Required |
|---|---|---|
| Credit Rating | ≥ BBB- (investment grade) | No — skipped if missing |
| Consecutive Positive FCF Years | ≥ 3 years | No — skipped if missing |
| Dividend History | ≥ 10 years | No — skipped if missing |

### COVERED_CALL_ETF
| Check | Threshold | Required |
|---|---|---|
| AUM | ≥ $500M | No — skipped if missing |
| Track Record | ≥ 3 years | No — skipped if missing |
| Distribution History | ≥ 12 months | No — skipped if missing |

### BOND
| Check | Threshold | Required |
|---|---|---|
| Credit Rating | ≥ BBB- (investment grade) | No — skipped if missing |
| Duration | ≤ 15 years | No — skipped if missing |

---

## Interfaces

### Input Models

```python
@dataclass
class DividendStockGateInput:
    ticker: str
    credit_rating: Optional[str] = None
    consecutive_positive_fcf_years: Optional[int] = None
    dividend_history_years: Optional[int] = None

@dataclass
class CoveredCallETFGateInput:
    ticker: str
    aum_millions: Optional[float] = None
    track_record_years: Optional[float] = None
    distribution_history_months: Optional[int] = None

@dataclass
class BondGateInput:
    ticker: str
    credit_rating: Optional[str] = None
    duration_years: Optional[float] = None
    issuer_type: Optional[str] = None
    yield_to_maturity: Optional[float] = None
```

### Output Model

```python
@dataclass
class GateResult:
    ticker: str
    asset_class: AssetClass
    passed: bool
    status: GateStatus          # PASS | FAIL | INSUFFICIENT_DATA
    fail_reasons: list[str]     # empty if passed
    warnings: list[str]         # non-blocking notes
    checks: dict                # per-check pass/fail detail
    data_quality_score: float   # 0.0–100.0
    evaluated_at: datetime
    valid_until: datetime       # evaluated_at + 24h
```

### API Endpoints

```
POST /quality-gate/evaluate
    Body: QualityGateRequest
    Returns: QualityGateResponse

POST /quality-gate/batch
    Body: BatchQualityGateRequest (max 50 tickers)
    Returns: BatchQualityGateResponse
```

---

## Dependencies

- `app/config.py` — configurable thresholds
- `platform_shared.quality_gate_results` — persistence (via `app/api/quality_gate.py`)
- No external API calls — all data provided by caller

---

## Missing Data Handling

- Individual checks are **skipped** (not failed) when data is absent
- A result of `INSUFFICIENT_DATA` is returned only when **all** required fields are missing
- `data_quality_score` decreases proportionally for each missing field
- Each missing field adds a warning to `result.warnings`

---

## Success Criteria

- FAIL results are never passed to the scoring engine
- Credit rating comparison is case-insensitive and whitespace-tolerant
- `valid_until` is always exactly 24 hours from `evaluated_at`
- `data_quality_score` is 100.0 when all fields present, decreasing by field count
- Batch endpoint returns counts: `total`, `passed`, `failed`, `insufficient_data`

---

## Non-Functional Requirements

- **Latency:** < 5ms per evaluation (pure CPU, no I/O)
- **Determinism:** Same input always produces same output
- **Throughput:** Batch endpoint handles 50 tickers synchronously
- **Test coverage:** 42 unit tests, 100% path coverage for gate logic
