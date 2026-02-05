# Architecture Decision Records (ADRs)

This document captures significant architectural decisions made during the design and implementation of the NAV Erosion Analysis system.

## ADR Format

Each ADR includes:
- **Context**: The issue motivating this decision
- **Decision**: The change being proposed or made
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Consequences**: What becomes easier or harder

---

## ADR-001: Use Monte Carlo Simulation Over Analytical Models

**Date:** 2026-01-15  
**Status:** ✅ Accepted  
**Decision Makers:** Platform Architecture Team

### Context

We need to predict NAV erosion in covered call ETFs. Two approaches considered:

1. **Analytical Models**: Black-Scholes-based closed-form solutions
2. **Monte Carlo Simulation**: Path-based stochastic simulation

Analytical models are faster but make strong assumptions (log-normal returns, constant volatility). Covered call ETFs exhibit regime-dependent behavior that violates these assumptions.

### Decision

**Use Monte Carlo simulation with regime modeling.**

Key reasons:
- Flexibility to model market regimes (bull/bear/sideways/volatile)
- No assumptions about return distributions
- Can capture premium-volatility correlation empirically
- Easier to validate against historical data
- Computational cost acceptable with vectorization (~500ms)

### Consequences

**Positive:**
- ✅ Realistic modeling of regime transitions
- ✅ Empirical validation against JEPI actual data
- ✅ Flexibility to add features (user scenarios, etc.)
- ✅ Transparent to users (understandable)

**Negative:**
- ⚠️ Slower than analytical (500ms vs <10ms)
- ⚠️ Requires historical data for calibration
- ⚠️ Results have statistical noise (mitigated with 10K+ sims)

**Mitigation:**
- Vectorized NumPy implementation (10x speedup)
- 30-day result caching (95% cost reduction)
- Clear documentation of assumptions

---

## ADR-002: Separate Microservice vs Embedded in Agent 3

**Date:** 2026-01-18  
**Status:** ✅ Accepted  
**Decision Makers:** Platform Architecture Team, DevOps

### Context

NAV erosion analysis could be:
1. **Embedded in Agent 3**: Part of scoring logic
2. **Separate Microservice**: Standalone HTTP service

Agent 3 is already complex with multiple scoring components. NAV erosion analysis is computationally intensive and domain-specific.

### Decision

**Implement as separate microservice with REST API.**

### Rationale

**Domain Separation:**
- NAV erosion is specialized (options, regimes, Monte Carlo)
- Different expertise required (quantitative vs platform)
- Reusable by other agents if needed

**Performance:**
- Computationally intensive (500ms per analysis)
- Can scale independently from Agent 3
- Doesn't block Agent 3 scoring pipeline

**Development:**
- Team can work independently
- Separate testing and deployment
- Easier to replace or upgrade

### Consequences

**Positive:**
- ✅ Clear separation of concerns
- ✅ Independent scaling (can add instances)
- ✅ Faster Agent 3 (cached results <10ms)
- ✅ Easier testing and validation

**Negative:**
- ⚠️ Network latency (mitigated by caching)
- ⚠️ Additional deployment complexity
- ⚠️ Service dependency management

**Integration Points:**
- Agent 1 → NAV Service: Historical data
- Agent 3 → NAV Service: Analysis requests
- NAV Service → PostgreSQL: Cache storage

---

## ADR-003: Vectorized NumPy Implementation

**Date:** 2026-01-20  
**Status:** ✅ Accepted  
**Decision Makers:** Development Team

### Context

Monte Carlo simulation requires 10,000-50,000 path simulations. Two implementation approaches:

1. **Loop-based**: Simple Python loops, ~5s for 10K sims
2. **Vectorized**: NumPy array operations, ~500ms for 10K sims

Performance target is <1s for quick analysis to support daily batch scoring of 100+ securities.

### Decision

**Use vectorized NumPy implementation with pre-allocated arrays.**

### Technical Approach

```python
# Vectorized approach
nav_paths = np.zeros((n_simulations, months + 1))
underlying_returns = np.random.normal(mean, std, size=(n_simulations, months))

# Process all simulations simultaneously
for t in range(months):
    nav_t = nav_paths[:, t]
    strikes = nav_t * (1 + moneyness_target)
    prices_after = nav_t * (1 + underlying_returns[:, t])
    nav_paths[:, t+1] = np.where(prices_after > strikes, strikes, prices_after)
```

### Consequences

**Positive:**
- ✅ 10x performance improvement (5s → 500ms)
- ✅ Memory efficient (pre-allocated arrays)
- ✅ Meets <1s target with 2x margin
- ✅ Scales to 50K simulations in ~2.5s

**Negative:**
- ⚠️ Code complexity (harder to debug than loops)
- ⚠️ Less flexible for dynamic simulation logic
- ⚠️ NumPy dependency (already in stack)

**Validation:**
- Test ensures vectorized matches loop-based results
- Performance benchmarks in test suite
- Memory profiling confirms efficiency

---

## ADR-004: 30-Day Cache TTL with Manual Invalidation

**Date:** 2026-01-22  
**Status:** ✅ Accepted  
**Decision Makers:** Platform Architecture Team

### Context

NAV erosion analysis is expensive (500ms) but results are stable for weeks/months since historical data changes slowly. Need caching strategy balancing:

- **Performance**: Fast response for cached results
- **Accuracy**: Results reflect current data
- **Cost**: Minimize redundant computation

### Decision

**Cache results for 30 days with manual invalidation endpoint.**

### Rationale

**30-Day TTL:**
- Historical data updated monthly
- Simulation parameters derived from 12-month history
- Small monthly data changes have minimal impact on results
- Balances freshness and performance

**Manual Invalidation:**
- Immediate refresh when data updated
- Endpoint: `DELETE /cache/{ticker}`
- Triggered by data pipeline
- User-initiated refresh option

### Consequences

**Positive:**
- ✅ 95% reduction in compute cost
- ✅ <10ms response time for cache hits
- ✅ Predictable expiration (no stale data >30 days)
- ✅ Manual control when needed

**Negative:**
- ⚠️ Cache storage (~5MB per 100 tickers)
- ⚠️ Potential for slightly stale data (<30 days)
- ⚠️ Cache management complexity

**Monitoring:**
- Track cache hit rate (target >80%)
- Alert if cache hit rate drops
- Log manual invalidations

---

## ADR-005: Graduated Penalty System (0-30 Points)

**Date:** 2026-01-25  
**Status:** ✅ Accepted  
**Decision Makers:** Product Team, Platform Architecture Team

### Context

Need to integrate NAV erosion risk into Agent 3's Sustainability score. Options:

1. **Binary Flag**: Pass/fail based on threshold
2. **Linear Penalty**: Direct mapping of probability to points
3. **Graduated Penalty**: Tiered system with multiple thresholds

User research shows need for nuanced risk representation. Binary flags lose information; linear penalties can be too harsh.

### Decision

**Implement 3-tier graduated penalty system capped at 30 points.**

### Penalty Structure

**Tier 1: Moderate Erosion Risk (>5% annually)**
- Prob 30-50%: 5 points
- Prob 50-70%: 10 points
- Prob >70%: 15 points

**Tier 2: Severe Erosion Risk (>10% annually)**
- Prob 15-30%: 8 points
- Prob >30%: 15 points

**Tier 3: Expected Erosion (Median NAV change)**
- Median -2% to -5%: 5 points
- Median <-5%: 10 points

**Total Cap:** 30 points maximum (prevents single factor dominance)

### Rationale

**Graduated Approach:**
- Reflects probability distributions naturally
- Clear risk tiers for users (low/medium/high/severe)
- Preserves score nuance

**30-Point Cap:**
- Sustainability component is 40% of total score
- 30 points = 12-point impact on total (40% × 30)
- Significant but not disqualifying
- Allows other factors to matter

### Consequences

**Positive:**
- ✅ Nuanced risk representation
- ✅ Clear user communication (5 risk tiers)
- ✅ Prevents false dichotomy (pass/fail)
- ✅ Aligned with probability distributions

**Negative:**
- ⚠️ Calibration complexity (3 tiers × multiple thresholds)
- ⚠️ Requires ongoing validation
- ⚠️ User education needed

**Validation:**
- Backtested against 7 known covered call ETFs
- JEPI correctly classified as "moderate" risk
- QYLD correctly classified as "high" risk
- User acceptance testing completed

---

## ADR-006: Market Regime Modeling (4 Regimes)

**Date:** 2026-01-28  
**Status:** ✅ Accepted  
**Decision Makers:** Development Team, Quantitative Analysis

### Context

Covered call ETF performance varies dramatically by market conditions:
- Bull markets: Upside capped, missed gains
- Bear markets: Limited downside protection
- Sideways: Optimal conditions (premium without cap)
- Volatile: High premiums, frequent caps

Static simulation (single regime) underestimates dispersion.

### Decision

**Model 4 market regimes with empirically-calibrated transitions.**

### Regime Definitions

**Bull Market:**
- Mean return: 1.5× historical
- Volatility: 0.8× historical
- Premium yield: 0.8× historical
- Typical duration: 3-9 months

**Bear Market:**
- Mean return: -2.0× historical
- Volatility: 1.5× historical
- Premium yield: 1.4× historical
- Typical duration: 3-9 months

**Sideways Market:**
- Mean return: 0× (no drift)
- Volatility: 0.6× historical
- Premium yield: 0.7× historical
- Typical duration: 3-9 months

**Volatile Market:**
- Mean return: 0.5× historical
- Volatility: 2.0× historical
- Premium yield: 1.8× historical
- Typical duration: 3-9 months

### Transition Probabilities

Calibrated from S&P 500 historical data (2000-2025):

- Bull → Bull: 50% (persistence)
- Bull → Sideways: 30%
- Bull → Volatile: 15%
- Bull → Bear: 5%

(Full transition matrix in implementation)

### Consequences

**Positive:**
- ✅ Realistic dispersion of results
- ✅ Captures regime-dependent behavior
- ✅ Matches historical volatility patterns
- ✅ Explains covered call underperformance in bulls

**Negative:**
- ⚠️ Added complexity (4 regimes × transitions)
- ⚠️ Calibration requires historical data
- ⚠️ Assumes regime independence (simplification)

**Validation:**
- Test shows regime modeling increases dispersion vs static
- Historical JEPI performance explained by regime mix
- P10-P90 range matches market observations

---

## ADR-007: FastAPI for REST Service

**Date:** 2026-01-30  
**Status:** ✅ Accepted  
**Decision Makers:** Development Team

### Context

Need modern Python web framework for REST API. Options:

1. **Flask**: Mature, simple, synchronous
2. **FastAPI**: Modern, async, auto-docs
3. **Django REST**: Full-featured, heavy

Requirements: Async support, automatic validation, OpenAPI docs, lightweight.

### Decision

**Use FastAPI with Pydantic validation.**

### Rationale

**Async Support:**
- Native async/await for I/O operations
- Non-blocking database queries
- Handles concurrent requests efficiently

**Automatic Validation:**
- Pydantic models for request/response
- Type checking at runtime
- Clear error messages

**Auto-Generated Docs:**
- OpenAPI/Swagger at `/docs`
- No manual API documentation
- Interactive testing UI

**Performance:**
- One of fastest Python frameworks
- Uvicorn ASGI server
- Comparable to Go/Node.js

### Consequences

**Positive:**
- ✅ Automatic OpenAPI documentation
- ✅ Type-safe request/response handling
- ✅ Excellent developer experience
- ✅ High performance (async)

**Negative:**
- ⚠️ Newer framework (less mature than Flask)
- ⚠️ Python 3.7+ required
- ⚠️ Learning curve for async patterns

**Alternatives Considered:**
- Flask: Too simple, lacks async
- Django REST: Too heavy for microservice

---

## Future ADRs (Planned)

### Under Consideration

**ADR-008: Dynamic Asset-Class Weighting**
- Status: Design phase complete
- Decision pending: Implementation priority

**ADR-009: Redis Distributed Caching**
- Status: Proposed
- Decision pending: Cost/benefit analysis

**ADR-010: Machine Learning Parameter Prediction**
- Status: Research phase
- Decision pending: Accuracy validation

---

## ADR Review Process

**Timing:** Quarterly or upon significant changes  
**Owners:** Platform Architecture Team  
**Review Includes:**
- Validation of consequences (expected vs actual)
- Performance metrics
- User feedback
- Technology updates

**Next Review:** 2026-05-01 (Q2 2026)

---

*ADR log maintained as part of documentation*  
*Format follows Michael Nygard's ADR template*  
*All decisions subject to review and update*
