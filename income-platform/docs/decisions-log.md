# Architecture Decision Records (ADRs)

This document tracks significant architectural and design decisions for the Income Fortress Platform.

**Format:** Each ADR includes Context, Decision, Rationale, Consequences, and Status.

---

## ADR-001: Hybrid Scoring Methodology (Income Fortress + SAIS)

**Date:** January 15, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
The platform needed a unified scoring approach that works across diverse income asset types (dividend stocks, REITs, BDCs, mREITs, covered call ETFs). Traditional Income Fortress methodology works well for dividend stocks but struggles with coverage-based assets.

### Decision
Implement hybrid scoring that routes to different methodologies based on asset type:
- **Income Fortress** for dividend stocks not in high-yield sectors
- **SAIS Enhanced** for REITs, BDCs, mREITs, and high-yield sector stocks
- **Covered Call Enhanced** for premium income ETFs

### Rationale
1. **Asset-Appropriate Scoring:** REITs/BDCs require coverage ratio analysis (NII/distributions)
2. **Proven Methodologies:** Income Fortress has 3+ years of performance data
3. **Flexibility:** Can add new methodologies without breaking existing logic
4. **User Familiarity:** Preserves Income Fortress brand for dividend stocks

### Consequences
**Positive:**
- More accurate scoring across all asset types
- Leverages existing Income Fortress knowledge
- Allows methodology-specific enhancements

**Negative:**
- Increased complexity in scorer logic
- Need to maintain two methodologies
- Potential for methodology confusion

**Mitigation:**
- Clear documentation of routing logic
- `scorer_methodology` field in output shows which was used
- Preference system allows forcing specific methodology

---

## ADR-002: NAV Erosion Calculation for Covered Call ETFs

**Date:** January 18, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Covered call ETFs can have attractive yields (10-12%+) but suffer from NAV erosion over time as they sacrifice upside. Need objective measure to detect value destruction masked by high distributions.

### Decision
Implement benchmark-relative NAV erosion calculation:
```python
Adjusted Erosion = (NAV_t + Cumulative_Dist) / NAV_0 ^ (365/days) - 1 
                 - (Benchmark_t / Benchmark_0) ^ (365/days) - 1
```
- Use 3-year history (1-year fallback)
- Weight at 20% in covered call ETF scoring
- Threshold: -10% max acceptable erosion

### Rationale
1. **Catches Hidden Value Loss:** Distributions can mask declining NAV
2. **Benchmark-Relative:** Compares to what investor could have earned in index
3. **Total Return Focus:** Includes distributions in calculation
4. **Time-Normalized:** Annualized for consistent comparison

### Consequences
**Positive:**
- Identifies ETFs destroying value despite high yield
- Protects users from yield traps
- Comparable across different time periods

**Negative:**
- Requires 3 years of data (limits coverage of new ETFs)
- Uses Adj Close as NAV proxy (~0.5% error margin)
- Benchmark selection can affect score

**Mitigation:**
- 1-year fallback for newer ETFs
- Document NAV proxy limitation
- Map ETFs to appropriate benchmarks (SPY, QQQ, IWM)

---

## ADR-003: ROC Tax Efficiency Tracking

**Date:** January 20, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Tax efficiency is critical for income investors but often overlooked. Return of Capital (ROC) distributions are tax-deferred (reduce cost basis) vs qualified dividends (0-20% tax) vs ordinary income (up to 37% tax).

### Decision
Implement comprehensive tax efficiency scoring:
- Track ROC %, qualified %, ordinary % for each asset
- Weight: ROC=100 pts, Qualified=75 pts, Ordinary=0 pts
- Section 1256 bonus: +10% for index option ETFs
- Manual mapping for known ETFs, updated quarterly

### Rationale
1. **After-Tax Returns Matter:** 37% tax on ordinary income significantly impacts returns
2. **ROC is Undervalued:** Many investors don't understand ROC benefits
3. **Section 1256 Advantage:** 60/40 long-term/short-term treatment on index options
4. **Competitive Differentiation:** Few platforms track this systematically

### Consequences
**Positive:**
- Helps users maximize after-tax income
- Highlights tax-advantaged ETFs like SPYI (92% ROC)
- Educates users on tax treatment

**Negative:**
- Manual mapping required (no reliable API)
- Quarterly maintenance burden
- Tax breakdown can change year-to-year

**Mitigation:**
- Document manual update process
- Set quarterly reminders
- Future: Automate 19a-1 notice scraping

---

## ADR-004: Granular SAIS Curves (5-Zone Scoring)

**Date:** January 22, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Original SAIS scoring used 3 zones (danger/acceptable/excellent). Hybrid prototype showed 5-zone curves provide much better precision in danger/warning areas where most scoring decisions occur.

### Decision
Implement 5-zone granular curves for SAIS components:

**Coverage Zones:**
- Danger (<0.8x): 0-20 pts
- Critical (0.8-1.0x): 20-50 pts
- Acceptable (1.0-sector_min): 50-75 pts
- Good (sector_min-1.3x): 75-95 pts
- Excellent (>1.3x): 95-100 pts

**Leverage Zones:**
- Danger (>1.25x max): 0-40 pts
- Elevated (1.0-1.25x): 40-60 pts
- Acceptable (0.8-1.0x): 60-80 pts
- Good (0.5-0.8x): 80-95 pts
- Excellent (<0.5x): 95-100 pts

### Rationale
1. **Better Precision:** 50-75 (acceptable) vs 75-95 (good) distinction meaningful
2. **Proven in Production:** Hybrid prototype achieved higher prediction accuracy
3. **Danger Detection:** 0-20 vs 20-50 separates severe from critical issues
4. **Sector Calibration:** sector_min allows per-sector tuning

### Consequences
**Positive:**
- More nuanced scoring
- Better separation of marginal assets
- Easier to tune thresholds

**Negative:**
- Slightly more complex to explain
- More parameters to maintain

**Mitigation:**
- Comprehensive documentation
- Visual diagrams of curves
- Default thresholds based on prototype testing

---

## ADR-005: Profile-Driven Circuit Breaker Auto-Enable

**Date:** January 25, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Circuit breaker monitoring is critical for high-yield assets (REITs, BDCs, mREITs) that can deteriorate quickly, but not all users understand when to enable it.

### Decision
Auto-enable circuit breaker based on asset profile:
```python
if asset_type in [REIT, BDC, MREIT] or sector in high_yield_sectors:
    check_circuit_breaker = True
else:
    check_circuit_breaker = preference.get('circuit_breaker_in_scoring', False)
```

### Rationale
1. **Smart Defaults:** Protects users who don't know to enable
2. **Risk-Based:** High-yield assets need more monitoring
3. **Override Available:** Users can disable via preferences
4. **Reduces Configuration:** No manual per-asset decisions

### Consequences
**Positive:**
- Better protection for risky assets
- Reduced user configuration burden
- Catches deteriorating positions early

**Negative:**
- Slight performance overhead (CB check)
- May trigger false positives

**Mitigation:**
- Efficient CB check implementation (<200ms)
- Profile-based thresholds reduce false positives
- Users can disable if desired

---

## ADR-006: Preference-Based Configuration System

**Date:** January 28, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Multi-tenant SaaS platform needs per-tenant configuration without code changes. Different users have different risk tolerances and preferences.

### Decision
Implement preference system with:
- Tenant-specific preference table (`tenant_*.preferences`)
- Per-agent, per-parameter configuration
- JSONB value storage for flexibility
- 5-minute TTL cache
- Defaults with override capability

### Rationale
1. **Multi-Tenant Requirement:** Essential for SaaS model
2. **No-Code Configuration:** Users can adjust without deployments
3. **Flexible Schema:** JSONB allows any preference type
4. **Performance:** 5-min cache prevents excessive DB queries

### Consequences
**Positive:**
- Highly customizable per tenant
- No code deployments for config changes
- Easy to add new preferences

**Negative:**
- Cache invalidation complexity
- Potential for configuration drift
- Need UI for preference management

**Mitigation:**
- Event-driven cache invalidation (future)
- Preference validation on write
- Admin UI in roadmap

---

## ADR-007: Docker Compose vs Kubernetes for Phase 1

**Date:** January 30, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Need container orchestration for production deployment. Options: Docker Compose (simple) vs Kubernetes (complex but scalable).

### Decision
Use Docker Compose for Phase 1 (15 tenants), migrate to Kubernetes at 200+ tenants.

### Rationale
1. **Simplicity:** Docker Compose much easier to deploy and manage
2. **Sufficient for Scale:** Single droplet handles 15-50 tenants easily
3. **Cost:** No orchestration overhead
4. **Faster Time to Market:** Can deploy in hours vs days/weeks

### Consequences
**Positive:**
- Rapid deployment
- Easy troubleshooting
- Lower operational complexity
- Reduced infrastructure cost

**Negative:**
- Limited to single-node deployment
- Manual scaling
- No built-in service discovery

**Migration Path:**
- Phase 1 (15 tenants): Docker Compose on single droplet
- Phase 2 (50 tenants): Separate worker droplet
- Phase 3 (200 tenants): Migrate to Kubernetes

---

## ADR-008: Celery Queue Specialization (6 Queues)

**Date:** January 31, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Different tasks have different priority and resource requirements. Need efficient task routing and prioritization.

### Decision
Implement 6 specialized queues with priority-based routing:
- **alerts** (priority 10): Highest - urgent notifications
- **monitoring** (priority 9): Circuit breaker checks
- **scoring** (priority 8): Asset scoring requests
- **proposals** (priority 7): Proposal generation
- **analysis** (priority 6): Market data, features
- **portfolio** (priority 5): Portfolio operations
- **background** (priority 1): Cleanup, maintenance

3 workers:
- Worker 1: scoring + analysis
- Worker 2: portfolio + proposals
- Worker 3: monitoring + alerts

### Rationale
1. **Priority Routing:** Critical tasks processed first
2. **Resource Isolation:** Heavy tasks don't block urgent tasks
3. **Scalability:** Can scale specific workers independently
4. **Monitoring:** Per-queue metrics

### Consequences
**Positive:**
- Better task prioritization
- Predictable alert delivery
- Independent scaling

**Negative:**
- More complex configuration
- Potential for queue imbalance

**Mitigation:**
- Monitor queue depths
- Adjust worker assignments as needed
- Auto-scaling in Kubernetes phase

---

## ADR-009: Structured JSON Logging

**Date:** February 1, 2026  
**Status:** ✅ Accepted  
**Deciders:** Alberto DBP, Claude

### Context
Need production-grade logging for debugging, auditing, and compliance. Logs should be machine-parseable.

### Decision
Implement structured JSON logging with:
- ISO timestamp
- Log level
- Logger name (module)
- Request ID (for tracing)
- Message
- Context (arbitrary key-value pairs)

### Rationale
1. **Machine Parseable:** Can index in Elasticsearch/Loki
2. **Request Tracing:** Request ID tracks across services
3. **Compliance:** Structured audit trail
4. **Performance Metrics:** Embedded in logs

### Consequences
**Positive:**
- Easy to query and analyze
- Supports log aggregation
- Compliance-ready

**Negative:**
- Larger log files
- Less human-readable

**Mitigation:**
- Log rotation (10MB, 10 backups)
- Local tool for pretty-printing: `cat log.json | jq`

---

## ADR-010: Manual Tax Breakdown Mapping (Short-Term)

**Date:** February 2, 2026  
**Status:** ✅ Accepted (Interim)  
**Deciders:** Alberto DBP, Claude

### Context
Need tax breakdown (ROC %) for covered call ETFs but no reliable API exists. ETF providers publish 19a-1 notices but format varies.

### Decision
**Phase 1:** Manual mapping in code, updated quarterly
**Phase 2-3:** Automate 19a-1 notice scraping

Current approach:
```python
KNOWN_TAX_BREAKDOWNS = {
    'SPYI': {'roc_percentage': 0.92, 'qualified': 0.05, 'ordinary': 0.03},
    'JEPI': {'roc_percentage': 0.15, 'qualified': 0.10, 'ordinary': 0.75},
    # ... more ETFs
}
```

### Rationale
1. **Pragmatic:** Gets us to market faster
2. **Quarterly Updates:** Tax breakdown doesn't change monthly
3. **High-Value ETFs:** Cover top 20 ETFs manually (~80% of volume)
4. **Automation Later:** Once usage validates value

### Consequences
**Positive:**
- Simple implementation
- No scraping complexity
- Easy to verify accuracy

**Negative:**
- Manual maintenance (30 min/quarter)
- Limited coverage (20 ETFs initially)
- Updates lag by up to 3 months

**Mitigation:**
- Quarterly calendar reminders
- Document update process
- Default to conservative estimates for unknown ETFs

**Upgrade Path:**
- Phase 3: Web scraping of 19a-1 notices
- Phase 4: Partner with data provider (if volume justifies)

---

## Decision Log Summary

| ADR | Decision | Status | Impact |
|-----|----------|--------|--------|
| 001 | Hybrid Scoring Methodology | ✅ Accepted | High - Core architecture |
| 002 | NAV Erosion Calculation | ✅ Accepted | High - ETF scoring accuracy |
| 003 | ROC Tax Efficiency Tracking | ✅ Accepted | Medium - Tax optimization |
| 004 | Granular SAIS Curves | ✅ Accepted | High - Scoring precision |
| 005 | Profile-Driven Circuit Breaker | ✅ Accepted | Medium - User protection |
| 006 | Preference-Based Configuration | ✅ Accepted | High - Multi-tenancy |
| 007 | Docker Compose vs Kubernetes | ✅ Accepted | High - Deployment strategy |
| 008 | Celery Queue Specialization | ✅ Accepted | Medium - Task prioritization |
| 009 | Structured JSON Logging | ✅ Accepted | Medium - Observability |
| 010 | Manual Tax Breakdown Mapping | ✅ Accepted (Interim) | Low - Temporary solution |

---

## Future ADRs (To Be Created)

- ADR-011: Adaptive Learning Integration
- ADR-012: Bond Scoring Methodology
- ADR-013: Kubernetes Migration Strategy
- ADR-014: Multi-Region Deployment
- ADR-015: Machine Learning Model Management

---

**Document Maintained By:** Alberto DBP  
**Last Updated:** February 2, 2026  
**Review Frequency:** Quarterly or with major decisions
