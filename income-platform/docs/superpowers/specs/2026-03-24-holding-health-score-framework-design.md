# Holding Health Score Framework — Design Spec

**Date:** 2026-03-24
**Status:** Implemented — Phase 1
**Replaces:** Income Scorer V6 scoring philosophy (wrapper approach — V6 internals unchanged)

---

## 0. Definitions

| Term | Definition |
|------|-----------|
| **HHS** | Holding Health Score — chronic health of a single position (0–100) |
| **IES** | Income Entry Score — entry/exit timing score, on demand only (0–100) |
| **NAA Yield** | Net After-All Yield — (Gross Div − Fee Drag − Tax Drag) / Total Invested |
| **UNSAFE** | Flag triggered when Durability pillar score ≤ `unsafe_threshold` |
| **Quality Gate** | Binary pass/fail check run by Agent-03 before any scoring occurs |
| **CB** | Circuit Breaker — monitors acute risk events (CAUTION / CRITICAL / EMERGENCY) |

---

## 1. Core Philosophy

Capital preservation first. Income second. Growth and efficiency third.

Every score is deterministic, transparent, and class-aware. Scores answer distinct questions at distinct layers — they are never collapsed into a single number that conflates health, timing, and portfolio context.

**What changed from V6:**
- Technical/Timing removed from Holding Health Score entirely
- Valuation removed from Holding Health Score entirely
- Tax efficiency removed as a standalone scored component — it adjusts net yield within the Income pillar
- Hard veto replaced by a learnable UNSAFE threshold on the Durability pillar
- Portfolio Health split into two explicit, side-by-side outputs

---

## 2. Architecture

The Scoring Framework Layer wraps Agent-03 and Income Scorer V6 without modifying their internals. Existing scoring engines (SAIS, Income Fortress, Covered Call ETF Enhanced) become sub-metric providers. The wrapper remaps their outputs into the new pillar structure.

```
┌─────────────────────────────────────────────────────┐
│              Scoring Framework Layer                │
│                                                     │
│  ┌──────────────────┐    ┌───────────────────────┐  │
│  │  Holding Health  │    │  Income Entry Score   │  │
│  │  Score (HHS)     │    │  (IES) — on demand    │  │
│  │  Income          │    │  Valuation            │  │
│  │  Durability      │    │  Technical            │  │
│  │  UNSAFE flag     │    └───────────────────────┘  │
│  └──────────────────┘                               │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Portfolio Health                           │    │
│  │  [Aggregate HHS] | [Independent Panel]      │    │
│  └─────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────┘
                     │ reads sub-metric outputs
        ┌────────────┴────────────┐
        │   Existing Engines      │
        │  Agent-03  │  V6 SAIS  │
        │  (unchanged internals)  │
        └─────────────────────────┘
```

### 2.1 Wrapper output mapping from existing engines

Agent-03 produces three pillars. The wrapper maps them as follows:

| Agent-03 Output | Maps to HHS | Notes |
|----------------|-------------|-------|
| Valuation & Yield — yield sub-components | Income pillar | Only yield-related sub-components consumed |
| Valuation & Yield — valuation sub-components (P/E, NAV premium) | **Discarded** | Valuation moves to IES |
| Financial Durability | Durability pillar | Full sub-score consumed |
| Technical Entry (20 pts) | **Discarded** | Technical moves to IES |
| Chowder Number | Income pillar (informational) | Informational signal, 0% weight |
| NAV Erosion Penalty (ETFs) | Durability pillar | Applied as Durability sub-metric |

V6 SAIS sub-metrics map as follows:

| V6 SAIS Output | Maps to HHS |
|---------------|-------------|
| Coverage score | Durability pillar |
| Leverage score | Durability pillar |
| Yield score | Income pillar |
| Tax efficiency score | Discarded — replaced by net yield adjustment in Income pillar |

---

## 3. Holding Health Score (HHS)

Answers: **"Is this holding doing its job safely?"**

### 3.1 Quality Gate (prerequisite)

Agent-03's quality gate runs before any HHS computation. HHS is **not produced** for gate-failed or data-insufficient holdings.

| Gate Result | HHS Output | Downstream behavior |
|-------------|-----------|---------------------|
| PASS | HHS computed normally | Normal flow |
| FAIL | No HHS. Returns `QualityGateFail` with failure reasons. | Excluded from aggregate; Agent-12 no-proposal; user sees failure reasons (e.g., "Dividend history < 10 years") |
| INSUFFICIENT_DATA | No HHS. Returns `InsufficientData` status. | Excluded from aggregate with separate count; Agent-12 no-proposal; user sees "Data insufficient — manual review required". Holding remains excluded until data resolves. |

`QualityGateFail` and `InsufficientData` surface as separate counts in the Portfolio Health panel — the user can distinguish structurally unsuitable holdings from temporarily unscored ones.

Gate logic and thresholds are unchanged from Agent-03 (Section 8).

### 3.2 Pillars

Two pillars only. No timing. No price-sensitive metrics.

`HHS = (Income_score × income_weight) + (Durability_score × durability_weight)`

Both pillar scores are normalized to 0–100 before weighting. HHS output range: 0–100.

Income and Durability weights must always sum to 100%. The learning loop adjusts the Income weight; the Durability weight is derived as its complement (100% − Income weight).

**Normalization of Agent-03 partial output:** Agent-03 scores on a 100-point total (Pillar 1 Valuation & Yield: 40 pts, Pillar 2 Financial Durability: 40 pts, Pillar 3 Technical Entry: 20 pts). Since the wrapper discards Technical Entry and Valuation sub-components, raw scores must be re-normalized before use:

- Durability pillar from Agent-03: `normalized = (raw_durability / 40) × 100`
- Income pillar (yield sub-components only from Agent-03 Pillar 1): `normalized = (raw_yield_subcomponents / max_yield_subcomponent_pts) × 100`, where max points are defined per asset class in the Agent-03 scoring engine config
- V6 SAIS sub-metrics are already 0–100 per sub-metric — no re-normalization needed

| Pillar | What it measures |
|--------|-----------------|
| **Income** | Yield quality and attractiveness, net of tax and fee drag |
| **Durability** | Long-term ability to sustain payouts without eroding capital |

### 3.3 Sub-metric mapping by class

Sub-metric calculations are unchanged from existing V6/Agent-03 implementations. The wrapper reads their outputs and remaps — no recalculation.

| Asset Class | Income sub-metrics | Durability sub-metrics |
|-------------|-------------------|----------------------|
| Dividend Stocks | Net yield, Chowder Number (informational) | FCF payout ratio, 10-yr dividend history, debt coverage |
| Covered Call ETFs | Distribution yield (NAA-adjusted) | NAV erosion (cumulative), Upside capture ratio (inverse risk), Track record, Fund age/AUM |
| mREITs | Spread yield (net) | Coverage ratio, Leverage (≤7.6×), CPR, NAV change |
| BDCs | NII yield | NII coverage (>1.15×), Non-accruals, Leverage |
| Bonds / Bond ETFs | YTM (tax-adjusted) | Duration, Credit rating |
| Preferreds | Dividend yield | Cumulative status, Call protection |
| REITs (equity) | AFFO yield | AFFO payout, Occupancy, Debt/EBITDA |

Note: Upside capture ratio is classified under Durability for Covered Call ETFs. It measures the degree to which the fund limits upside participation — a structural risk characteristic, not an income quality indicator.

**Zero-yield holdings:** If a holding produces no income (yield ≤ 0%), the Income pillar scores 0/100. No automatic UNSAFE flag is triggered, but HHS will naturally be very low. A "No income detected — review for portfolio fit" alert is surfaced. This is not expected in a correctly configured income portfolio.

### 3.4 Pillar weights by class

Stored in Preference Table. Manually configurable. Learning loop integration deferred to Phase 3 (see Section 7).

| Asset Class | Income | Durability |
|-------------|--------|-----------|
| Dividend Stocks | 45% | 55% |
| Covered Call ETFs | 40% | 60% |
| mREITs | 35% | 65% |
| BDCs | 35% | 65% |
| Bonds / Bond ETFs | 35% | 65% |
| Preferreds | 40% | 60% |
| REITs (equity) | 40% | 60% |

### 3.5 Tax treatment within Income pillar

Tax efficiency is not a standalone scored component. It adjusts the net yield used in the Income pillar calculation:

- **Net yield** = gross yield adjusted for portfolio type (taxable / tax-advantaged) and income character (ROC, qualified, ordinary)
- ROC-heavy instruments (many covered call ETFs) carry near-zero current tax drag → higher net yield
- Municipal holdings carry tax advantages in taxable portfolios → reflected in net yield
- Tax character data sourced from Tax Optimizer Agent (existing)

**Fallback — Tax Optimizer Agent unavailable:** Income pillar uses gross yield. NAA Yield uses pre-tax values. Both are flagged with `PRE_TAX` indicator. A warning is surfaced to the user: "Tax data unavailable — yields shown pre-tax."

### 3.6 UNSAFE flag

Replaces the hard veto from V6.

- Triggered when Durability pillar score ≤ `unsafe_threshold`
- Default threshold: **20** (configurable per risk profile: conservative / moderate / aggressive)
- Adjustable via settings; learning loop integration deferred to Phase 3
- UNSAFE flag surfaces prominently alongside HHS — the score itself is not forced to zero
- A Durability score of 8 communicates different severity than 18; both are flagged UNSAFE

| Durability Score | Signal |
|-----------------|--------|
| > threshold | Normal — score speaks for itself |
| ≤ threshold | **UNSAFE** — prominent flag alongside HHS |

### 3.7 Universal decision thresholds

| HHS | Signal |
|-----|--------|
| 85–100 | Strong — healthy holding |
| 70–84 | Good — monitor normally |
| 50–69 | Watch — weakening, review recommended |
| < 50 | Concern — consider replacement |
| UNSAFE flag | Immediate review regardless of score |

### 3.8 Scoring cadence

HHS is computed:
- **On demand** — triggered by portfolio refresh, user query, or CB event
- **Scheduled daily batch** — at market close, for all active holdings

**Unavailable engine fallback:** If Agent-03 or V6 is unavailable, the holding retains its last known HHS with a `STALE` indicator. If the score is stale > 24 hours, the holding is excluded from the Portfolio Health aggregate with a warning count surfaced.

---

## 4. Income Entry Score (IES)

Answers: **"Is now a good time to act on this position?"**

IES is only invoked when a management decision is being evaluated: add, reduce, replace, or initiate a position. Never computed during routine health monitoring.

`IES = (Valuation_score × 0.60) + (Technical_score × 0.40)`

Output range: 0–100.

### 4.1 Prerequisite gate

IES is only calculated if:
- HHS > 50
- No UNSAFE flag active

**Gate-blocked response** (returned to all callers including Agent-12):

```json
{
  "ies_calculated": false,
  "reason": "UNSAFE_FLAG | HHS_BELOW_THRESHOLD",
  "hhs_score": 42.0,
  "action": "NO_ACTION",
  "message": "IES not available — holding does not meet health prerequisite."
}
```

IES never overrides HHS. A strong IES on an UNSAFE holding is always no-action.

### 4.2 Structure

| Component | Weight | Sub-metrics |
|-----------|--------|-------------|
| **Valuation** | 60% | P/E vs 5-yr avg, discount/premium to NAV, yield vs benchmark |
| **Technical** | 40% | RSI, distance to 200-DMA, % below 52-week high |

Class-adjusted technicals (from V6): RSI for stocks/REITs, duration for bonds, VIX regime for covered call ETFs.

### 4.3 Decision thresholds

| IES | Action |
|-----|--------|
| ≥ 85 | Full position |
| 70–84 | Partial position + limit orders |
| < 70 | Wait or DCA |

### 4.4 Trigger sources

- Agent-12 (Proposal Agent) — generating buy/add proposals
- User query — "should I buy more X?"
- Rebalancing agent — proposing position adjustments

---

## 5. Circuit Breaker Integration

The circuit breaker monitors acute events (sudden NAV drop, distribution cut, leverage spike, coverage breach). It is distinct from HHS, which tracks chronic health over time.

| CB Level | Integration | Lifecycle |
|----------|-------------|----------|
| **CAUTION** | −5 point modifier applied to Durability pillar score at next HHS computation. Persists until CB clears the signal. | Cleared when CB determines the condition has resolved |
| **CRITICAL** | Separate `⚠ CRITICAL` flag surfaces alongside HHS — bypasses scoring cadence, immediate | Cleared when CB resolves |
| **EMERGENCY** | `🚨 EMERGENCY: REVIEW NOW` flag — immediately triggers Agent-12 sell proposal | Cleared when CB resolves or position is closed |

UNSAFE flag and CB CRITICAL/EMERGENCY can coexist on the same holding:
- **UNSAFE** = chronic deterioration (gradual, trackable via Durability over scoring cycles)
- **CB CRITICAL/EMERGENCY** = acute event (faster than scoring cadence)

**Circuit breaker data flow:**

```
Circuit Breaker Monitor
  → CAUTION     → −5pt modifier to Durability pillar (next HHS run)
  → CRITICAL    → Immediate flag on Portfolio Health Output A
  → EMERGENCY   → Immediate flag + Agent-12 sell proposal trigger
```

---

## 6. Portfolio Health

Two outputs displayed side by side. Never collapsed into a single number.

### 6.1 Output A: Aggregate HHS

Position-weighted average of individual HHS scores (weighted by % of total portfolio value).

| Signal | Meaning |
|--------|---------|
| Aggregate score | Position-weighted average HHS (gate-failed and stale holdings excluded) |
| UNSAFE holdings | Count + list, always surfaced prominently regardless of aggregate score |
| CB CRITICAL/EMERGENCY | Surfaced immediately, bypasses cadence |
| QualityGateFail count | Count of holdings excluded due to gate failure |
| STALE count | Count of holdings excluded due to engine unavailability > 24h |

### 6.2 Output B: Independent Portfolio Health Panel

A metrics panel — each metric stands independently.

| Metric | Formula | Notes |
|--------|---------|-------|
| **NAA Yield** | (Gross Div − Fee Drag − Tax Drag) / Total Invested | Primary income health metric. Surfaced per holding and as portfolio aggregate |
| **Total Return** | (Current Value − Original Cost + Income − Tax Drag) / Original Cost | Full economic return including unrealized gain/loss |
| **Concentration (HHI)** | Σ (position weight²) | Flags individual holdings > HHI threshold (see below) |
| **Correlation** | Holdings vs. benchmark + peer correlation matrix | |
| **VaR** | Monte Carlo (existing simulation engine) | |
| **Sharpe / Sortino** | Risk-adjusted return metrics | |

**HHI concentration flag threshold** (configurable per risk profile):

| Risk Profile | Single-holding flag threshold |
|-------------|------------------------------|
| Conservative | 8% |
| Moderate | 10% |
| Aggressive | 15% |

**NAA Yield** exposes true economic yield: a 5% REIT yield (ordinary income, taxable account) may net less than a 4% qualified dividend ETF after tax character is applied. NAA is surfaced at both levels:
- Per holding: compare true yield across positions
- Portfolio aggregate: position-weighted NAA across all holdings

Tax drag inputs sourced from Tax Optimizer Agent. If unavailable, values shown with `PRE_TAX` flag (see §3.5 fallback).

### 6.3 Full data flow

```
Individual Holdings
  → Quality Gate (Agent-03) → FAIL: QualityGateFail, excluded from aggregate
  → HHS per holding (Agent-03 / V6 wrapper)
  → Circuit Breaker Monitor
  → Tax Optimizer (per holding tax character)
  → Portfolio Health Layer
      → Output A: Aggregate HHS + UNSAFE list + CB flags + gate-fail/stale counts
      → Output B: NAA Yield, Total Return, HHI, Correlation, VaR, Sharpe/Sortino
```

---

## 7. Learnable Parameters

Phase 1: All parameters are manually configurable via Preference Table. No code changes required to adjust weights or thresholds.

Phase 3: Learning loop integration (quarterly cycle, ±bounds, 24-month audit trail) to be designed as part of the Agent-03 learning loop implementation (already deferred to Phase 3 in Agent-03 roadmap).

**Phase 1 configurable parameters:**

| Parameter | Default | Phase 3 Learning Bounds |
|-----------|---------|------------------------|
| `income_weight_{class}` | per table in §3.4 | ±5 percentage points/quarter |
| `durability_weight_{class}` | per table in §3.4 | derived as complement; not adjusted independently |
| `unsafe_threshold` | 20 (per risk profile) | ±1 point/quarter, floor: 10, ceiling: 35 |
| `hhi_flag_threshold` | per risk profile table in §6.2 | configurable only |

---

## 8. What This Does Not Change

- Agent-03 internals (scoring curves, quality gates, Chowder Number calculation)
- V6 SAIS curves (coverage zones, leverage zones, yield zones)
- V6 NAV erosion formula
- Circuit Breaker Monitor logic
- Tax Optimizer Agent
- Agent-12 Proposal Agent (IES triggers it; it doesn't change)
- Preference Table structure (extended, not replaced)

---

## 9. Summary

| Question | Answered by |
|----------|------------|
| Is this holding structurally viable? | Quality Gate (pass/fail, before HHS) |
| Is this holding chronically unsafe? | UNSAFE flag (Durability ≤ threshold) |
| Is this holding healthy? | HHS (Income + Durability, 0–100) |
| Is there an acute risk right now? | Circuit Breaker (CAUTION / CRITICAL / EMERGENCY) |
| Is now a good time to act? | IES (Valuation + Technical, on demand only) |
| Is my portfolio healthy overall? | Aggregate HHS + Independent Panel (side by side) |
| What am I actually earning? | NAA Yield (per holding + portfolio aggregate) |
| What is my total economic return? | Total Return metric in Portfolio Health Panel |
