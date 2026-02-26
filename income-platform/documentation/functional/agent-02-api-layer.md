# Implementation Specification — Agent 02: API Layer

**Version:** 1.0  
**Status:** ✅ Complete  
**Last Updated:** 2026-02-25  
**Implements:** [Agent 02 Functional Spec](../functional/agent-02-newsletter-ingestion.md)

---

## Technical Design

The API layer is four FastAPI routers registered on `app/main.py`. All routes are read-only except `POST /analysts` and the flow trigger endpoints. Redis/Valkey caching is applied at the endpoint level on the two most-called routes: `/consensus` and `/signal`.

### Signal Strength Computation

`/signal/{ticker}` computes signal quality from three inputs:

```python
def _compute_signal_strength(n_analysts, top_decay_weight, top_analyst_accuracy):
    if n_analysts == 0:
        return "insufficient"
    accuracy = top_analyst_accuracy or 0.5
    if n_analysts >= 2 and top_decay_weight >= 0.7 and accuracy >= 0.65:
        return "strong"
    elif top_decay_weight >= 0.4:
        return "moderate"
    else:
        return "weak"
```

`proposal_readiness=True` requires `signal_strength in (strong, moderate)` AND `analyst_accuracy >= settings.default_min_accuracy_threshold (0.5)`.

### Best Recommendation Selection

When multiple analysts cover the same ticker, the "best" recommendation is selected by combined score: `decay_weight × analyst_accuracy`. This rewards freshness and track record equally.

### Consensus Formula

```python
# In processors/consensus.py
score = Σ(sentiment_score × analyst_accuracy × decay_weight) /
        Σ(analyst_accuracy × decay_weight)
```

Analysts with `accuracy < MIN_ACCURACY (0.5)` are excluded from consensus computation entirely.

---

## API Contracts

### GET /signal/{ticker} — Agent 12 Contract

**Path params:** `ticker` (case-insensitive, normalized to uppercase)  
**Query params:** `force_refresh=false`  
**Cache:** Valkey, TTL 3600s (1 hour), key `signal:{ticker}`  
**Response:** `AnalystSignalResponse`

```python
class AnalystSignalResponse(BaseModel):
    ticker: str
    asset_class: Optional[AssetClass]
    sector: Optional[str]
    signal_strength: str          # strong | moderate | weak | insufficient
    proposal_readiness: bool
    analyst: AnalystSignalAnalyst
    recommendation: AnalystSignalRecommendation
    consensus: ConsensusResponse
    platform_alignment: Optional[str]   # written back by Agent 12
    generated_at: datetime
```

**Error responses:**
- `404` — No active recommendations for ticker
- `500` — Database error

### GET /consensus/{ticker}

**Cache:** Valkey, TTL 1800s (30 min), key `consensus:{ticker}`  
**Response:** `ConsensusResponse`

```python
class ConsensusResponse(BaseModel):
    ticker: str
    score: Optional[float]              # -1.0 to 1.0
    confidence: str                     # high (>=3 analysts) | low | insufficient_data
    n_analysts: int
    n_recommendations: int
    dominant_recommendation: Optional[RecommendationLabel]
    computed_at: datetime
```

### POST /analysts — Add Analyst

**Request:** `{"sa_publishing_id": "96726", "display_name": "Rida Morwa"}`  
**Response:** `AnalystResponse` (201 Created)  
**Error:** `409 Conflict` if SA ID already registered

---

## Key Files

| File | Responsibility |
|---|---|
| `app/api/signal.py` | Signal endpoint + signal_strength/proposal_readiness logic |
| `app/api/consensus.py` | Consensus endpoint + Valkey caching |
| `app/api/recommendations.py` | Recommendations by ticker, ordered by decay_weight |
| `app/api/analysts.py` | Analyst CRUD + recommendations by analyst |
| `app/api/flows.py` | Flow trigger endpoints + flow_run_log |
| `app/api/health.py` | Health + DB/cache status |
| `app/models/schemas.py` | All Pydantic request/response schemas |
| `app/processors/consensus.py` | Consensus formula (used by both API + Intelligence Flow) |

---

## Testing & Acceptance

### Unit Tests (`tests/test_phase4_api.py`)

16 tests covering:
- `TestAnalystsAPI` — list, add, duplicate 409, get, 404
- `TestRecommendationsAPI` — 200, ticker normalization, 404
- `TestConsensusAPI` — 200, dominant_recommendation mapping, 404
- `TestSignalAPI` — 200, all required Agent 12 contract fields present, proposal_readiness=False on weak signal, 404, signal_strength logic unit tests, proposal_readiness unit tests, sentiment→label mapping

### Integration Tests (`tests/test_phase5_integration.py`)

Run against live service. Key signal/consensus/recommendation tests:
- Unknown ticker returns 404 on all three endpoints
- Lowercase ticker normalized to uppercase (same response as uppercase)
- Seeded analysts appear in GET /analysts

### Acceptance Criteria

- [ ] GET /signal/{ticker} returns all required Agent 12 contract fields
- [ ] proposal_readiness correctly reflects signal quality thresholds
- [ ] Consensus score cached in Valkey — second call hits cache (verify via logs)
- [ ] GET /analysts returns seeded test analysts (SA IDs 96726 + 104956)
- [ ] POST /analysts with duplicate SA ID returns 409

### Performance SLAs

| Endpoint | Cache Hit | Cache Miss |
|---|---|---|
| GET /signal/{ticker} | < 50ms | < 2s |
| GET /consensus/{ticker} | < 50ms | < 1s |
| GET /recommendations/{ticker} | n/a | < 500ms |

---

## Known Edge Cases

**No sentiment_score on recommendation:** Filtered out of consensus computation. Signal can still be generated from decay_weight and accuracy.

**All analysts below MIN_ACCURACY:** Consensus returns `insufficient_data`. Signal still generated but `proposal_readiness=False`.

**Valkey unavailable:** Both consensus and signal endpoints compute fresh on every request. Latency degrades to cache-miss SLA. No functional impact.

**Ticker with only expired (is_active=False) recommendations:** Returns 404. Client should trigger a fresh harvest to refresh signals.
