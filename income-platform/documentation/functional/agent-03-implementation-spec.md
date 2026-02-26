# Agent 03 — Income Scorer: Implementation Specification

**Platform:** Income Fortress Platform  
**Agent:** 03 — Income Scorer  
**Version:** 1.0.0  
**Date:** 2026-02-25

---

## Technical Design

### Stack
- **Runtime:** Python 3.11, FastAPI
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **Database:** PostgreSQL (DigitalOcean Managed)
- **Cache:** Valkey (Redis-compatible)
- **Data:** yfinance, FMP API, Polygon.io
- **ML (v2):** sentence-transformers, XGBoost
- **Monte Carlo:** NumPy vectorized (10K simulations, <3s target)
- **Containerization:** Docker, DigitalOcean App Platform
- **Messaging:** Internal message bus (async publish)

---

## Phase Plan

### Phase 1 — Foundation
SQLAlchemy models, Alembic migrations, DataProvider abstraction layer, shared Asset Class Detector (rule-based), Preference Table schema, project skeleton, unit test harness.

### Phase 2 — Quality Gate Router
All 8 class-specific gates + universal fallback. Gate criteria loaded from Preference Table. Full unit test coverage per gate.

### Phase 3 — Monte Carlo NAV Erosion Engine
Vectorized NumPy simulation. Market regime transitions. Cache integration (30-day TTL). Applicable to: covered call ETFs, mREITs, leveraged CEFs.

### Phase 4 — Composite Scorer
4 sub-scorers (income, durability, valuation, technical). Class-specific weight loading. Risk penalty layer (Agent 02 integration). VETO engine.

### Phase 5 — API, Output & Persistence
FastAPI routes. Output builder (including `explanation` field, null by default). Tax metadata builder. LLM explanation generator (`generate_explanation()`, invoked on user-facing requests only). Score persistence (versioned, with explanation columns). Message bus publish. Learning loop stub.

### Phase 6 — Learning Loop & Backtesting
Shadow portfolio tracking. Quarterly weight adjustment engine. Historical validation against known yield traps and dividend cuts.

---

## Key Implementation Details

### Quality Gate Router

```python
class GateRouter:
    GATE_MAP = {
        "dividend_stock": DividendStockGate,
        "otm_covered_etf": CoveredCallETFGate,
        "bond_etf": BondGate,
        "reit": REITGate,
        "mreit": MREITGate,
        "bdc": BDCGate,
        "cef": CEFGate,
        "preferred_stock": PreferredGate,
    }
    
    def evaluate(self, ticker: str, asset_class: str, 
                 features: Dict) -> GateResult:
        gate_class = self.GATE_MAP.get(asset_class, UniversalFallbackGate)
        gate = gate_class(self.preference_table)
        return gate.evaluate(ticker, features)
```

Each gate implements:
```python
class BaseQualityGate(ABC):
    @abstractmethod
    def get_criteria(self) -> List[GateCriterion]: ...
    
    def evaluate(self, ticker: str, features: Dict) -> GateResult:
        results = [c.check(features) for c in self.get_criteria()]
        passed = all(r.passed for r in results)
        return GateResult(passed=passed, criteria_results=results,
                          gate_name=self.__class__.__name__)
```

### Weight Loading

```python
class WeightLoader:
    def load(self, asset_class: str) -> WeightSet:
        # Full replacement sets — never delta adjustments
        rows = self.db.query(PreferenceTable).filter(
            PreferenceTable.scope == "scoring_weights",
            PreferenceTable.asset_class == asset_class
        ).all()
        
        weights = {r.parameter_key: r.parameter_value for r in rows}
        assert abs(sum(weights.values()) - 1.0) < 0.001, \
            f"Weights for {asset_class} do not sum to 1.0"
        return WeightSet(**weights)
```

### VETO Engine

```python
class VETOEngine:
    def check(self, composite_result: CompositeResult, 
              features: Dict, mc_result: Optional[NAVErosionResult],
              coverage_history: List[float]) -> VETOResult:
        
        triggers = []
        
        # NAV erosion probability
        if mc_result and mc_result.erosion_probability_24m > 0.25:
            triggers.append(f"NAV erosion probability {mc_result.erosion_probability_24m:.1%} > 25% threshold")
        
        # Coverage ratio sustained failure
        recent_coverage = coverage_history[-2:] if len(coverage_history) >= 2 else []
        if all(c < 1.0 for c in recent_coverage) and len(recent_coverage) == 2:
            triggers.append(f"Distribution coverage <1.0x for 2 consecutive quarters")
        
        # Capital safety component
        if composite_result.durability_score < 70:
            triggers.append(f"Durability sub-score {composite_result.durability_score} < 70 threshold")
        
        veto_triggered = len(triggers) > 0
        return VETOResult(
            triggered=veto_triggered,
            reason=" | ".join(triggers) if veto_triggered else None,
            forced_score=0 if veto_triggered else composite_result.composite_score
        )
```

### Monte Carlo Engine (core)

```python
def run_simulation(self, params: SimulationParams, 
                   n_simulations: int = 10_000) -> NAVErosionResult:
    # Vectorized: shape (n_simulations, n_months)
    monthly_returns = np.random.normal(
        params.expected_monthly_return,
        params.monthly_volatility,
        (n_simulations, params.horizon_months)
    )
    
    # Apply option cap (covered call: cap upside at strike)
    if params.has_call_overlay:
        monthly_returns = np.minimum(monthly_returns, params.call_strike_monthly)
    
    # Distribution drag
    monthly_returns -= params.monthly_distribution_rate
    
    # Cumulative NAV paths
    nav_paths = np.cumprod(1 + monthly_returns, axis=1)
    
    # Erosion probability at each horizon
    final_nav_24m = nav_paths[:, 23]
    erosion_prob_24m = float(np.mean(final_nav_24m < (1 - params.erosion_threshold)))
    
    return NAVErosionResult(
        erosion_probability_24m=erosion_prob_24m,
        risk_tier=self._classify_risk(erosion_prob_24m),
        penalty_points=self._calculate_penalty(erosion_prob_24m)
    )
```

### Risk Penalty Layer (Agent 02 integration)

```python
class RiskPenaltyLayer:
    PENALTY_MAP = {
        RiskFlag.YIELD_TRAP: 30,
        RiskFlag.DIVIDEND_CUT_RISK: 25,
        RiskFlag.FINANCIAL_DISTRESS: 20,
        RiskFlag.ANALYST_NEGATIVE_CONSENSUS: 15,
        RiskFlag.LEVERAGE_WARNING: 10,
    }
    MAX_TOTAL_PENALTY = 50
    
    def apply(self, raw_score: float, 
              agent02_signals: Optional[List[Signal]]) -> PenaltyResult:
        
        flags = self._detect_internal_flags(raw_score)
        
        # Agent 02: only negative signals trigger penalty
        # Positive signals are neutral — do not boost score
        if agent02_signals:
            for signal in agent02_signals:
                if signal.sentiment < 0.3:  # Negative threshold
                    flags.append(RiskFlag.ANALYST_NEGATIVE_CONSENSUS)
        
        total_penalty = min(
            sum(self.PENALTY_MAP.get(f, 10) for f in flags),
            self.MAX_TOTAL_PENALTY
        )
        
        return PenaltyResult(
            adjusted_score=max(0, raw_score - total_penalty),
            flags=flags,
            total_penalty=total_penalty
        )
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/score` | Score a single ticker |
| POST | `/api/v1/score/batch` | Score a list of tickers |
| GET | `/api/v1/score/{ticker}/latest` | Get latest score for ticker |
| GET | `/api/v1/score/{ticker}/history` | Get score history (paginated) |
| GET | `/api/v1/score/{ticker}/monte-carlo` | Get Monte Carlo result (cached) |
| GET | `/api/v1/weights/{asset_class}` | Get current weight set for class |
| PUT | `/api/v1/weights/{asset_class}` | Update weight set (admin) |
| GET | `/api/v1/health` | Service health check |

---

## Database Migrations (Alembic)

```
001_create_securities_table
002_create_scores_table
003_create_score_history_table
004_create_nav_erosion_cache_table
005_create_preference_table_scoring
006_create_shadow_portfolio_table
007_create_weight_adjustments_table
008_seed_default_weight_sets
009_seed_quality_gate_thresholds
010_add_explanation_columns_to_scores
```

Migration 010 adds to `scores` table:
- `explanation_text TEXT` — LLM-generated plain-English explanation
- `explanation_prompt TEXT` — full prompt used (audit trail)
- `explanation_model TEXT` — model version used
- `explanation_generated_at TIMESTAMP`

---

## Testing & Acceptance

### Unit Test Requirements

| Module | Tests Required |
|---|---|
| GateRouter | Each class routes to correct gate; unknown class → universal fallback |
| Each QualityGate | Pass/fail on boundary values for each criterion |
| WeightLoader | Weights sum to 1.0; invalid sets raise; missing class uses fallback |
| MonteCarloEngine | Deterministic with fixed seed; erosion prob increases with higher distribution rate |
| VETOEngine | All 3 trigger conditions fire independently; VETO forces score to 0 |
| RiskPenaltyLayer | Negative signals apply penalty; positive signals neutral; cap at 50 |
| ScoreOutputBuilder | Tax efficiency present regardless of VETO; all fields populated; explanation null by default |
| LLMExplanationGenerator | Explanation generated only when requested; VETO response leads with capital safety language; explanation stored with full prompt |
| DataProviderRouter | yfinance fallback on FMP failure; graceful degradation logged |

### Integration Test Scenarios

1. **Full happy path:** Score JEPI (otm_covered_etf) — gate passes, Monte Carlo runs, score returned with tax metadata
2. **VETO path:** Ticker with NAV erosion >25% — VETO fires, score = 0, tax field still populated
3. **Gate rejection:** Ticker fails coverage ratio gate — returns gate_failure, no score computed
4. **Agent 02 unavailable:** Score proceeds, penalty layer skipped, `agent02_unavailable: true` in output
5. **Cache hit:** Second request for same ticker within 30 days — Monte Carlo result from cache
6. **Unknown asset class:** Ticker not matching any rule — routes to universal fallback gate
7. **Batch scoring:** 20 tickers — all complete within 60s, no partial failures

### Acceptance Criteria

- VETO fires in 100% of defined trigger scenarios in test suite
- Tax efficiency field present in output for every response including VETO responses
- Weight sets loaded from Preference Table; hardcoded weights fail CI
- Score history queryable for any scored ticker
- Monte Carlo cache hit rate >90% in integration tests (after first run)
- Agent 02 unavailability does not degrade service (graceful skip)
- All 8 quality gates produce correct pass/fail on boundary test vectors

### Known Edge Cases

- Ticker delisted mid-scoring: return `{error: "data_unavailable", ticker: X}`
- All data providers fail: return `{error: "provider_unavailable"}` with 503
- Weight set in Preference Table doesn't sum to 1.0: raise `InvalidWeightSetError`, use last valid set
- Monte Carlo simulation produces NaN (extreme inputs): clamp to 0/1 bounds, log warning
- Agent 02 signals contain conflicting sentiment (same ticker, different analysts): use minimum sentiment value (most conservative)

### Performance SLAs

| Operation | p50 | p95 | p99 |
|---|---|---|---|
| Single score (cached MC) | 200ms | 500ms | 800ms |
| Single score (fresh MC) | 1s | 3s | 5s |
| Batch 20 tickers | 5s | 15s | 25s |
| Gate evaluation only | 50ms | 150ms | 250ms |

---

## Implementation Notes

**DataProvider abstraction is non-negotiable:** Every data fetch goes through the provider router. Direct yfinance calls in scoring logic are a bug. This enables seamless FMP/Polygon migration and provider fallback.

**Weight sets are immutable snapshots:** When a score is saved, the exact weight set used is snapshotted in the score record. This enables historical auditing and learning loop comparison even after weights are updated.

**Monte Carlo seed management:** Development/test environments use fixed seeds for determinism. Production uses random seeds. Seed value stored in `NAV_EROSION_CACHE` for reproducibility.

**VETO is a post-composite gate, not a pre-composite gate:** The composite is fully computed before VETO checks run. This preserves sub-score visibility even on vetoed securities — useful for understanding *why* a security failed and for learning loop analytics.

**Tax metadata builder runs always:** Even on VETO responses. The `tax_efficiency` field must always be populated. Agent 05 relies on this regardless of VETO status.

**Preference Table is the single source of truth:** Weight sets, gate thresholds, learning loop bounds, user preferences — all live there. No scoring configuration in code. This enables chat-based overrides ("set mREIT durability weight to 50%") without deployments.
