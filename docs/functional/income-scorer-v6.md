# Functional Specification: Income Scorer V6

**Component:** Income Scorer V6  
**Version:** 6.0.0  
**Status:** ✅ Complete  
**Last Updated:** February 2, 2026

---

## Purpose & Scope

The Income Scorer V6 is the core scoring engine of the Income Fortress Platform, responsible for evaluating income-generating assets and providing actionable investment recommendations.

**What it does:**
- Evaluates stocks, REITs, BDCs, mREITs, covered call ETFs, and bonds
- Combines Income Fortress methodology with SAIS for high-yield assets
- Calculates NAV erosion for covered call ETFs
- Tracks tax efficiency (ROC, qualified dividends, ordinary income)
- Integrates with Circuit Breaker for real-time risk monitoring
- Provides entry/exit price analysis
- Incorporates analyst consensus

**What it doesn't do:**
- Execute trades (proposal-based workflow only)
- Store long-term position data (that's Portfolio Manager's job)
- Make buy/sell decisions without user approval
- Provide financial advice (analysis tool only)

---

## Responsibilities

### Core Responsibilities
1. **Asset Classification** - Identify asset type and sector
2. **Quality Gate Enforcement** - Filter out unsuitable investments
3. **Hybrid Scoring** - Route to appropriate methodology (Income Fortress vs SAIS)
4. **Component Scoring** - Calculate individual score components (coverage, leverage, yield, etc.)
5. **Composite Score Calculation** - Weighted combination of components
6. **Price Analysis** - Determine optimal entry/exit prices
7. **Risk Integration** - Incorporate circuit breaker alerts
8. **Decision Generation** - Recommend action (aggressive_buy, accumulate, watch, avoid, sell)

### Specific Calculations
- **NAV Erosion (ETFs):** `(NAV_t + Cumulative_Dist) / NAV_0 ^ (365/days) - 1 - Benchmark_Return`
- **Tax Efficiency:** `ROC*100 + Qualified*75 + Ordinary*0 + Section1256Bonus`
- **SAIS Coverage:** 5-zone non-linear scoring (danger/critical/acceptable/good/excellent)
- **SAIS Leverage:** 5-zone inverse scoring (lower leverage = higher score)
- **SAIS Yield:** Sweet spot detection with trap avoidance

---

## Interfaces

### Input Interface

**Primary Method:**
```python
def score_asset(
    symbol: str,
    context: Optional[Dict] = None,
    analysis_purpose: str = "buy",
    check_circuit_breaker: bool = None
) -> AssetScore
```

**Parameters:**
- `symbol` (str, required) - Ticker symbol (e.g., "ARCC", "O", "SPYI")
- `context` (dict, optional) - Execution context
  - `tenant_id` (str) - For preference loading
  - `portfolio_id` (str) - For portfolio-specific analysis
  - `risk_tolerance` (str) - "conservative", "moderate", "aggressive"
  - `holding_exists` (bool) - Whether user already owns this asset
  - `holding_info` (dict) - Cost basis, quantity for exit analysis
- `analysis_purpose` (str, optional) - "buy" or "sell"
- `check_circuit_breaker` (bool, optional) - Override for CB check (None = auto-detect)

**Example Usage:**
```python
# Simple scoring
result = income_scorer_v6.score_asset("ARCC")

# With context
result = income_scorer_v6.score_asset(
    "ARCC",
    context={
        'tenant_id': '001',
        'risk_tolerance': 'moderate',
        'portfolio_id': 'port_123'
    }
)

# For selling decision
result = income_scorer_v6.score_asset(
    "O",
    context={
        'tenant_id': '001',
        'holding_exists': True,
        'holding_info': {'cost_basis': 50.00, 'quantity': 100}
    },
    analysis_purpose="sell"
)
```

### Output Interface

**Returns:** `AssetScore` dataclass

```python
@dataclass
class AssetScore:
    symbol: str                          # "ARCC"
    asset_type: AssetType                # AssetType.BDC
    sector: str                          # "BDC"
    quality_gate: QualityGateCheck       # passed=True, failures=[]
    overall_score: float                 # 73.5
    component_scores: Dict[str, float]   # {'coverage': 85, 'leverage': 70, ...}
    entry_price_analysis: Dict           # {'current_zone': 'good', 'action': 'BUY_NOW', ...}
    exit_price_analysis: Optional[Dict]  # Present if analysis_purpose='sell'
    analyst_consensus: AnalystConsensus  # {'consensus_score': 82, ...}
    decision: str                        # "accumulate"
    circuit_breaker: Optional[CircuitBreakerResult]
    current_yield: float                 # 0.095 (9.5%)
    coverage_ratio: Optional[float]      # 1.25
    leverage_ratio: Optional[float]      # 1.05
    payout_ratio: Optional[float]        # 0.85
    scored_at: str                       # ISO timestamp
    model_version: str                   # "v6.0.0-final"
    scorer_methodology: str              # "sais_enhanced_bdc"
```

### Dependencies

**Required Services:**
- Feature Store V2 - For extracting asset features
- Preference Manager - For tenant-specific configuration
- Circuit Breaker Monitor - For position health checks (optional)
- Analyst Consensus Tracker - For analyst data (optional)

**Database Access:**
- `platform_shared.securities` - Asset metadata
- `platform_shared.features_historical` - Feature data
- `platform_shared.stock_scores` - Score caching
- `tenant_*.preferences` - User preferences

**External APIs:**
- yfinance - Market data (via Feature Store)
- None directly (all via Feature Store abstraction)

---

## Scoring Methodologies

### 1. Income Fortress (Dividend Stocks)

**Applicability:** Dividend-paying stocks not in high-yield sectors

**Components:**
- **Valuation (40%):** P/E, P/B, PEG, dividend yield relative to sector
- **Durability (40%):** Dividend history, payout ratio, FCF coverage, balance sheet
- **Technical (20%):** Price relative to moving averages, RSI, support/resistance

**Formula:**
```python
overall_score = valuation_score * 0.40 + durability_score * 0.40 + technical_score * 0.20
```

### 2. SAIS Enhanced (REITs, BDCs, mREITs, High-Yield Stocks)

**Applicability:** Coverage-based high-yield assets

**Components:**
- **Coverage (45%):** Distribution coverage ratio (NII/distributions or FFO/distributions)
- **Leverage (30%):** Debt-to-equity or debt-to-assets ratio
- **Yield (25%):** Dividend yield with sweet spot and trap detection

**Formula:**
```python
coverage_score = sais_coverage_score_enhanced(coverage, sector_min)
leverage_score = sais_leverage_score_enhanced(leverage, sector_max)
yield_score = sais_yield_score_enhanced(yield_pct, risk_profile)

overall_score = coverage_score * 0.45 + leverage_score * 0.30 + yield_score * 0.25

# NAV penalty for mREITs
if nav_change_12m < -0.08:
    overall_score += -12
```

**SAIS Curves (5-Zone Granular Scoring):**

*Coverage Zones:*
- Danger (<0.8x): 0-20 points
- Critical (0.8-1.0x): 20-50 points
- Acceptable (1.0-sector_min): 50-75 points
- Good (sector_min-1.3x): 75-95 points
- Excellent (>1.3x): 95-100 points

*Leverage Zones:*
- Danger (>1.25x max): 0-40 points
- Elevated (1.0-1.25x): 40-60 points
- Acceptable (0.8-1.0x): 60-80 points
- Good (0.5-0.8x): 80-95 points
- Excellent (<0.5x): 95-100 points

*Yield Zones (Profile-Dependent):*
- Aggressive: 9.0-10.5% sweet spot, >12.2% trap
- Moderate: 8.5-10.0% sweet spot, >11.5% trap
- Conservative: 8.0-9.5% sweet spot, >11.0% trap

### 3. Covered Call ETF Enhanced

**Applicability:** Covered call / premium income ETFs

**Components:**
- **Distribution Yield (25%):** Higher yield = higher score (6-12%+ range)
- **Volatility Drag (25%):** Upside capture ratio vs underlying index
- **NAV Erosion (20%):** Benchmark-relative NAV performance including distributions
- **Tax Efficiency (20%):** ROC % + qualified dividends % + Section 1256 bonus
- **Track Record (10%):** Distribution consistency, fund age

**Formula:**
```python
# NAV Erosion Calculation
ann_factor = 365 / days
etf_return = ((nav_t + cumulative_dist) / nav_0) ** ann_factor - 1
benchmark_return = (benchmark_t / benchmark_0) ** ann_factor - 1
erosion_rate = etf_return - benchmark_return

if erosion_rate >= 0:
    nav_score = 100
else:
    nav_score = max(0, 100 * (1 + erosion_rate / threshold))

# Tax Efficiency
tax_score = roc_pct * 100 + qualified_pct * 75 + ordinary_pct * 0
if section_1256:
    tax_score *= 1.10  # 10% bonus

overall_score = (
    yield_score * 0.25 +
    drag_score * 0.25 +
    nav_score * 0.20 +
    tax_score * 0.20 +
    track_score * 0.10
)
```

---

## Decision Logic

The scorer generates actionable recommendations based on overall score and price analysis:

```python
def _make_decision(overall_score, entry_analysis, circuit_breaker):
    # Circuit breaker override
    if circuit_breaker and circuit_breaker.triggered:
        if circuit_breaker.highest_level == 'EMERGENCY':
            return "sell_urgent"
        elif circuit_breaker.highest_level == 'CRITICAL':
            return "sell_caution"
    
    price_action = entry_analysis.get('action')  # 'BUY_NOW', 'WAIT', etc.
    price_zone = entry_analysis.get('current_zone')  # 'excellent', 'good', 'fair', 'expensive'
    
    # Score ≥ 85: Excellent quality
    if overall_score >= 85:
        if price_action == 'BUY_NOW' or price_zone in ['excellent', 'good']:
            return "aggressive_buy"
        else:
            return "watch_for_dip"  # Great quality, wrong price
    
    # Score 70-84: Good quality
    elif overall_score >= 70:
        if price_action == 'BUY_NOW' or price_zone in ['excellent', 'good']:
            return "accumulate"
        else:
            return "watch_for_dip"
    
    # Score 60-69: Acceptable quality
    elif overall_score >= 60:
        if price_zone == 'excellent':
            return "accumulate_small"  # Marginal quality, great price
        else:
            return "watch"
    
    # Score < 60: Poor quality
    else:
        return "avoid"
```

**Decision Meanings:**
- `aggressive_buy` - High quality at good price, consider large position
- `accumulate` - Good quality, build position over time
- `accumulate_small` - Acceptable quality or good price, small position
- `watch_for_dip` - High quality but expensive, wait for better entry
- `watch` - Monitor, needs improvement before buying
- `avoid` - Poor quality, do not invest
- `sell_caution` - Circuit breaker CRITICAL, consider selling
- `sell_urgent` - Circuit breaker EMERGENCY, sell immediately

---

## Quality Gates

Before scoring, assets must pass quality gates:

**Universal Quality Gates:**
1. **Data Availability:** Minimum required features present
2. **Price Validity:** Current price > $0
3. **Volume:** Sufficient liquidity (avg volume > 10,000 shares/day)

**Asset-Specific Quality Gates:**

*Dividend Stocks:*
- Has paid dividends in last 12 months
- Payout ratio < 1.5 (sustainable)

*REITs/BDCs:*
- Credit rating ≥ B- (or unrated)
- Distribution coverage ≥ 0.5x (minimum viability)
- Debt-to-equity < 3x sector max

*mREITs:*
- Book value decline < 50% in 5 years
- Distribution coverage ≥ 0.5x

*Covered Call ETFs:*
- Fund age > 6 months
- AUM > $50M
- Distribution consistency (paid 80%+ of expected distributions)

**Quality Gate Failure:**
If quality gate fails, return `AssetScore` with:
- `quality_gate.passed = False`
- `quality_gate.failures = [list of failures]`
- `overall_score = 0`
- `decision = "reject_quality_gate"`

---

## Non-Functional Requirements

### Performance
- **Latency:** <3 seconds per symbol (p95)
- **Feature Extraction Success Rate:** >99%
- **Cache Hit Rate:** >80% for frequently-scored symbols
- **Concurrent Scoring:** Support 10+ simultaneous requests

### Reliability
- **Error Handling:** Graceful degradation if Feature Store fails
- **Fallback:** Return partial score if some components fail
- **Retry Logic:** Automatic retry for transient failures (3 attempts)
- **Logging:** All scoring requests logged for audit

### Scalability
- **Throughput:** 1,000+ scores per hour per worker
- **Caching:** Score results cached for 30 minutes
- **Batch Scoring:** Support batch requests (10-100 symbols)

### Security
- **Input Validation:** Sanitize all symbol inputs
- **Tenant Isolation:** Preferences isolated by tenant_id
- **Rate Limiting:** Enforced at API layer (5 req/min per IP)

---

## Configuration

### Preference-Based Configuration

**Available Preferences (tenant_*.preferences):**

```python
{
    'engine_mode': 'auto',  # 'auto', 'income_fortress', 'hybrid_sais', 'force_sais'
    'adaptive_scoring': False,  # Enable learning loop modifiers
    'circuit_breaker_in_scoring': True,  # Auto-enable for SAIS assets
    'nav_erosion_threshold': -0.10,  # Max acceptable erosion (-10%)
    'income_weight_covered_call': 0.25,  # Yield weight for ETFs
    'nav_erosion_weight': 0.20,  # NAV erosion weight
    'tax_efficiency_weight': 0.20  # Tax efficiency weight
}
```

**Usage:**
```python
prefs = preference_manager.get_preferences(tenant_id, 'scoring')
threshold = prefs.get('nav_erosion_threshold', -0.10)
```

### Sector-Specific Thresholds

```python
SECTOR_THRESHOLDS = {
    AssetType.BDC: {
        'coverage_min': 1.15,
        'leverage_max': 1.2,
        'leverage_metric': 'debt_to_equity',
        'yield_min': 0.09,
        'yield_max': 0.12
    },
    AssetType.REIT: {
        'coverage_min': 1.20,
        'leverage_max': 0.60,
        'leverage_metric': 'debt_to_assets',
        'yield_min': 0.04,
        'yield_max': 0.08
    },
    AssetType.MREIT: {
        'coverage_min': 1.05,
        'leverage_max': 8.0,
        'leverage_metric': 'debt_to_equity',
        'yield_min': 0.10,
        'yield_max': 0.14
    }
}
```

---

## Success Criteria

### Functional Success Criteria
1. ✅ Can score all supported asset types (stocks, REITs, BDCs, mREITs, ETFs)
2. ✅ Quality gate correctly filters unsuitable assets
3. ✅ NAV erosion calculation matches reference formula
4. ✅ Tax efficiency correctly classifies ROC vs qualified vs ordinary
5. ✅ Circuit breaker penalties apply correctly
6. ✅ Decision logic produces expected recommendations
7. ✅ Preference overrides work as expected

### Performance Success Criteria
1. ✅ 95% of scores complete in <3 seconds
2. ✅ 99%+ feature extraction success rate
3. ✅ Cache hit rate >80% for frequently-scored symbols
4. ✅ No memory leaks over 24-hour operation

### Quality Success Criteria
1. ✅ Backtesting shows >70% accuracy on 3-month forward returns
2. ✅ Circuit breaker triggers correctly identify deteriorating positions
3. ✅ NAV erosion scores correlate with actual ETF performance
4. ✅ Tax efficiency scores match actual 1099 classifications

---

## Integration Points

### Upstream Dependencies
- **Feature Store V2** - Provides all feature data
- **Preference Manager** - Provides tenant configuration
- **Circuit Breaker Monitor** - Provides risk alerts (optional)
- **Analyst Consensus Tracker** - Provides analyst data (optional)

### Downstream Consumers
- **Proposal Generator** - Uses scores to generate buy/sell proposals
- **Portfolio Analyzer** - Uses scores for portfolio health assessment
- **User Query Agent** - Uses scores to answer user questions
- **Learning Loop Optimizer** - Uses scores for prediction logging

### Event Triggers
- **Score Cached** - Emit event when score cached (for invalidation)
- **Quality Gate Failed** - Log to learning loop for analysis
- **Circuit Breaker Triggered** - Alert delivery system notified

---

## Examples

### Example 1: BDC Scoring (SAIS Methodology)

**Input:**
```python
score = income_scorer_v6.score_asset(
    "ARCC",
    context={'tenant_id': '001', 'risk_tolerance': 'moderate'}
)
```

**Processing:**
1. Identify asset type: BDC
2. Load features: coverage=1.25, leverage=1.05, yield=9.5%
3. Quality gate: PASS
4. Route to SAIS methodology
5. Calculate components:
   - Coverage: 85/100 (1.25x in "good" zone)
   - Leverage: 70/100 (1.05x in "acceptable" zone)
   - Yield: 95/100 (9.5% in sweet spot)
6. Overall: 0.45*85 + 0.30*70 + 0.25*95 = 83.0
7. Circuit breaker: CAUTION (-10 penalty) = 73.0
8. Entry price: "good" zone
9. Decision: "accumulate"

**Output:**
```python
AssetScore(
    symbol="ARCC",
    asset_type=AssetType.BDC,
    overall_score=73.0,
    component_scores={'coverage': 85, 'leverage': 70, 'yield': 95},
    decision="accumulate",
    current_yield=0.095
)
```

### Example 2: Covered Call ETF (Enhanced Methodology)

**Input:**
```python
score = income_scorer_v6.score_asset("SPYI")
```

**Processing:**
1. Identify asset type: Covered Call ETF
2. Load features including NAV erosion and tax breakdown
3. Calculate NAV erosion: -2% (better than benchmark -5%) = 70/100
4. Calculate tax efficiency: 92% ROC + Section 1256 = 100/100
5. Overall: yield(90)*0.25 + drag(75)*0.25 + nav(70)*0.20 + tax(100)*0.20 + track(85)*0.10 = 83.75
6. Decision: "accumulate"

**Output:**
```python
AssetScore(
    symbol="SPYI",
    asset_type=AssetType.COVERED_CALL_ETF,
    overall_score=83.75,
    component_scores={
        'distribution_yield': 90,
        'volatility_drag': 75,
        'nav_erosion': 70,
        'tax_efficiency': 100,
        'track_record': 85
    },
    decision="accumulate"
)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 6.0.0 | 2026-02-02 | Initial production release with all Phase 1 enhancements |
| 5.0.0 | - | Previous version (deprecated) |

---

## Related Documents

- [Implementation Specification](../implementation/income-scorer-v6-impl.md)
- [NAV Erosion Calculation](../implementation/nav-erosion-calculation.md)
- [ROC Tax Efficiency](../implementation/roc-tax-efficiency.md)
- [SAIS Curves Enhancement](../implementation/sais-curves-enhancement.md)
- [Testing Specification](../testing/income-scorer-v6-tests.md)

---

**Document Owner:** Alberto DBP  
**Last Reviewed:** February 2, 2026  
**Next Review:** May 1, 2026
