# Agent 03 — Income Scorer: Reference Architecture

**Platform:** Income Fortress Platform  
**Monorepo Path:** `/Agentic/income-platform/agents/agent-03-income-scorer/`  
**Version:** 1.0.0  
**Date:** 2026-02-25  
**Status:** DESIGN — Pre-Implementation

---

## Overview

Agent 03 (Income Scorer) is the analytical core of the Income Fortress Platform. It produces the **Income Fortress Score (0–100)** — a composite measure of income sustainability and capital safety — for any supported income-generating security across 7 asset classes.

The score drives all downstream investment decisions. It is philosophically pure: it measures only capital safety and income quality. Tax efficiency, benchmark comparison, and class-level evaluation are handled by downstream agents (Agent 04, Agent 05).

---

## Core Principles

| Principle | Implementation |
|---|---|
| Capital safety first | VETO logic fires post-composite; score forced to 0 on safety failure, sub-scores preserved for audit |
| Income quality over yield | Sustainability metrics weighted above raw yield in all asset classes |
| No auto-execution | Agent 03 produces scores and recommendations only; proposals require user approval |
| Philosophically pure score | Tax efficiency is a parallel output field, never a composite component |
| Extensible multi-class | Full replacement weight sets per class; new classes added via Preference Table only |

---

## Position in Platform

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Income Fortress Platform                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  UPSTREAM INPUTS                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐   │
│  │  Agent 01   │  │  Agent 02   │  │  Shared: Asset Class     │   │
│  │  Market     │  │  Newsletter │  │  Detector (rule-based    │   │
│  │  Data Svc   │  │  Ingestion  │  │  v1, ML v2)              │   │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬──────────────┘   │
│         │                │                      │                  │
│         └────────────────┴──────────────────────┘                  │
│                                    │                               │
│                                    ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   AGENT 03: Income Scorer                   │   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Quality     │  │  Composite   │  │  Monte Carlo     │  │   │
│  │  │ Gate Router │→ │  Scorer      │← │  NAV Erosion     │  │   │
│  │  └─────────────┘  └──────┬───────┘  └──────────────────┘  │   │
│  │                          │                                  │   │
│  │                   ┌──────▼───────┐                         │   │
│  │                   │ VETO Engine  │                         │   │
│  │                   └──────┬───────┘                         │   │
│  │                          │                                  │   │
│  │              ┌───────────▼──────────┐                      │   │
│  │              │  Score Output Builder│                      │   │
│  │              │  (+ tax_efficiency   │                      │   │
│  │              │   metadata)          │                      │   │
│  │              └──────────────────────┘                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    │                               │
│         ┌──────────────────────────┼────────────────┐             │
│         ▼                          ▼                ▼             │
│  ┌─────────────┐  ┌─────────────────────┐  ┌──────────────┐      │
│  │  Agent 04   │  │  Agent 05           │  │  PostgreSQL  │      │
│  │  Asset Class│  │  Tax Optimizer      │  │  Scores      │      │
│  │  Evaluator  │  │  (consumes tax      │  │  Table       │      │
│  │             │  │   efficiency field) │  │              │      │
│  └─────────────┘  └─────────────────────┘  └──────────────┘      │
│                                                                     │
│  FURTHER DOWNSTREAM                                                 │
│  Position Sizer → Portfolio Builder → Alert System                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Internal Component Architecture

```
Agent 03: Income Scorer
│
├── api/
│   └── routes.py                    # FastAPI endpoints
│
├── scoring/
│   ├── quality_gate/
│   │   ├── gate_router.py           # Routes to class-specific gate
│   │   ├── gates/
│   │   │   ├── dividend_stock_gate.py
│   │   │   ├── covered_call_etf_gate.py
│   │   │   ├── bond_gate.py
│   │   │   ├── reit_gate.py
│   │   │   ├── mreit_gate.py
│   │   │   ├── bdc_gate.py
│   │   │   ├── cef_gate.py
│   │   │   └── preferred_gate.py
│   │   └── universal_fallback_gate.py
│   │
│   ├── composite/
│   │   ├── scorer.py                # Main composite scoring engine
│   │   ├── sub_scorers/
│   │   │   ├── income_scorer.py     # Income/yield sub-score
│   │   │   ├── durability_scorer.py # Sustainability sub-score
│   │   │   ├── valuation_scorer.py  # Valuation sub-score
│   │   │   └── technical_scorer.py  # Technical sub-score (class-specific)
│   │   └── weight_loader.py         # Loads replacement weights from Preference Table
│   │
│   ├── veto/
│   │   └── veto_engine.py           # VETO logic — fires post-composite, forces score to 0
│   │
│   ├── monte_carlo/
│   │   ├── nav_erosion_engine.py    # Monte Carlo simulation (covered call ETFs)
│   │   ├── mreit_erosion_engine.py  # Adapted for mREIT book value erosion
│   │   └── cache_manager.py        # 30-day TTL cache for simulation results
│   │
│   └── output/
│       ├── score_builder.py         # Assembles final output JSON
│       └── tax_metadata_builder.py  # Populates tax_efficiency field (0% weight)
│
├── data/
│   ├── provider_router.py           # DataProvider abstraction layer
│   ├── yfinance_provider.py         # Primary data source
│   ├── fmp_provider.py              # FMP for gaps (AFFO, NII, CEF metrics)
│   └── polygon_provider.py          # Polygon for price/options data
│
├── learning/
│   └── adaptive_weights.py          # Quarterly learning loop + shadow portfolio
│
└── models/
    └── db_models.py                  # SQLAlchemy models for scores persistence
```

---

## Data Flow

```
Request (ticker + asset_class hint)
        │
        ▼
[1] Asset Class Detection
    Shared utility → detect_asset_class(ticker)
    Returns: (class_name, confidence)
    Fallback: rule-based on yfinance quoteType + sector
        │
        ▼
[2] Data Collection
    DataProvider.fetch(ticker, class_name)
    yfinance primary → FMP for gaps → Polygon for options/price
    Returns: class-appropriate feature dict
        │
        ▼
[3] Quality Gate Router
    GateRouter.evaluate(ticker, class_name, features)
    Runs class-specific gate criteria
    Returns: GateResult(passed: bool, failures: list)
    If failed → return early with gate_failure response
        │ (only if gate passed)
        ▼
[4] Monte Carlo (conditional)
    If class in [covered_call_etf, mreit, cef_leveraged]:
        Check cache (30-day TTL)
        If cache miss → run simulation
    Returns: NAVErosionResult(probability, risk_tier, penalty_points)
        │
        ▼
[5] Sub-Score Computation
    Load weight set for class from Preference Table
    income_score    = IncomeScoer.compute(features, weights)
    durability_score = DurabilityScorer.compute(features, weights, nav_result)
    valuation_score  = ValuationScorer.compute(features, weights)
    technical_score  = TechnicalScorer.compute(features, weights, class_name)
        │
        ▼
[6] Risk Penalty Layer
    Check Agent 02 signals (negative sentiment → penalty applied)
    Apply risk flags: yield_trap (-30), div_cut_risk (-25), distress (-20)
    Cap total penalty at -50
        │
        ▼
[7] Composite Assembly
    composite = Σ(sub_score × class_weight) - risk_penalty
    composite = max(0, min(100, composite))
        │
        ▼
[8] VETO Engine
    Check: NAV erosion > threshold
    Check: Coverage ratio < 1.0× for 2+ consecutive quarters
    Check: composite_safety_component < 70
    If any → veto_triggered = true, composite_score = 0
        │
        ▼
[9] Output Assembly
    Build final JSON:
      composite_score, veto_triggered, sub_scores,
      tax_efficiency (parallel metadata, 0% weight),
      recommendation, confidence, class_context
        │
        ▼
[10] Persistence
    Insert into scores table (versioned)
    Update portfolio_holdings.income_score
    Publish to message bus → Agent 04, Agent 05
```

---

## Score Output Structure

```json
{
  "ticker": "SPYI",
  "asset_class": "otm_covered_etf",
  "composite_score": 78,
  "veto_triggered": false,
  "veto_reason": null,
  "sub_scores": {
    "income": 85,
    "durability": 72,
    "valuation": 68,
    "technical": 81
  },
  "class_weights_used": {
    "income": 0.30,
    "durability": 0.50,
    "valuation": 0.00,
    "technical": 0.20
  },
  "risk_penalties": {
    "total_penalty": 0,
    "flags": []
  },
  "monte_carlo": {
    "ran": true,
    "nav_erosion_probability_24m": 0.12,
    "risk_tier": "low",
    "penalty_applied": 0,
    "cache_hit": true
  },
  "quality_gate": {
    "passed": true,
    "gate_used": "covered_call_etf_gate",
    "criteria_results": []
  },
  "tax_efficiency": {
    "raw_roc_percentage": 68,
    "qualified_dividend_percentage": 12,
    "ordinary_income_percentage": 20,
    "estimated_after_tax_yield": 9.1,
    "tax_characterization": "High deferral potential (ROC-dominant)",
    "user_context_note": "FL no state tax — full federal benefit applies"
  },
  "recommendation": "Buy",
  "decision_threshold_used": "universal_70_85",
  "class_context": "OTM Covered Call ETF — NAV erosion risk low, premium income sustainable",
  "confidence": 0.78,
  "explanation": null,
  "explanation_note": "Populated on user-facing requests only — not generated during batch scoring",
  "scored_at": "2026-02-25T14:30:00Z",
  "score_version": "1.0.0",
  "data_sources_used": ["yfinance", "fmp"]
}
```

---

## Quality Gate — Class-Specific Criteria

| Asset Class | Gate Criteria | Failure = Reject |
|---|---|---|
| Dividend Stocks | Credit ≥ BBB-, 10yr div history, FCF payout <70% | Hard reject |
| OTM Covered Call ETFs | NAV erosion <-10% adj, distribution coverage >1.0×, leverage <1.5× | Hard reject |
| Bonds / Bond ETFs | Credit ≥ BBB-, duration <7yrs, default prob <2% | Hard reject |
| REITs | AFFO payout <75%, Debt/EBITDA <6×, occupancy >90% | Hard reject |
| mREITs | Spread coverage >1.1×, leverage <7.6×, BV erosion < -10%/yr | Hard reject |
| BDCs | NII coverage >1.15×, Debt/Equity <1.14×, non-accrual <5% | Hard reject |
| CEFs | UNII >0, leverage <35%, discount volatility <5% | Hard reject |
| Preferred Stocks | Issuer credit ≥ BBB, call protection >5yrs, cumulative status verified | Hard reject |
| Universal Fallback | Payout/coverage <75%, no distribution cuts in 5yrs | Soft reject (flagged) |

---

## Composite Weight Sets by Asset Class

| Asset Class | Income % | Durability % | Valuation % | Technical % |
|---|---|---|---|---|
| Dividend Stocks | 30 | 40 | 20 | 10 |
| OTM Covered Call ETFs | 30 | 50 | 0 | 20 |
| Bonds / Bond ETFs | 25 | 55 | 0 | 20 |
| REITs | 35 | 40 | 15 | 10 |
| mREITs | 30 | 45 | 0 | 25 |
| BDCs | 35 | 45 | 10 | 10 |
| CEFs | 30 | 45 | 15 | 10 |
| Preferred Stocks | 30 | 50 | 10 | 10 |

*All weights sum to 100%. Stored as full replacement sets in Preference Table. User-adjustable via chat.*

---

## VETO Trigger Conditions

| Condition | Threshold | Source |
|---|---|---|
| NAV erosion probability (24m) | >25% | Monte Carlo engine |
| Distribution coverage ratio | <1.0× for 2+ consecutive quarters | FMP / yfinance |
| Capital safety sub-component | <70 points | Internal composite |
| Book value erosion (mREIT) | >-10% annually | yfinance / FMP |
| Leverage breach (BDC/mREIT) | Debt/Equity >1.25× | FMP |
| Non-accrual loans (BDC) | >7% | FMP |

When any VETO condition fires: `composite_score = 0`, `veto_triggered = true`, `veto_reason` populated. Tax efficiency field still computed and returned.

---

## Decision Matrix

| Score | Decision | Action Guidance |
|---|---|---|
| 85–100 | Strong Buy | 50–75% target allocation |
| 70–84 | Buy | 25% initial, DCA to target |
| 50–69 | Watch | Monitor, do not enter |
| <50 | Avoid | Flag for review or removal |
| 0 (VETO) | VETO — Unsafe | Reject regardless of yield |

*Thresholds are universal across all asset classes. Class context surfaced in output field, not embedded in thresholds.*

---

## Technical Sub-Score Factors by Class

| Asset Class | Factor 1 | Factor 2 | Factor 3 |
|---|---|---|---|
| Dividend Stocks | Weekly RSI <35 (+15pts) | Price within 5% of 52wk support (+15pts) | 200-DMA proximity (+10pts) |
| OTM Covered ETFs | VIX >20 / premium richness (+15pts) | Options bid-ask <0.5% (+15pts) | Upside capture ratio >50% (+10pts) |
| Bonds | Yield curve slope >0 (+15pts) | Spread compression vs. avg (+15pts) | Duration vs. target (+10pts) |
| REITs | NAV discount >5% (+15pts) | Rate sensitivity trend (+15pts) | Occupancy trend (+10pts) |
| mREITs | Yield curve steepness (+15pts) | CPR <15% (+15pts) | Discount to BV (+10pts) |
| BDCs | Non-accrual declining trend (+15pts) | NAV per share growth (+15pts) | Discount to NAV (+10pts) |
| CEFs | Z-score <-1.5 / deep discount (+15pts) | UNII trend positive (+15pts) | Coverage ratio trend (+10pts) |
| Preferred Stocks | Trading near par or discount (+15pts) | Call date distance (+15pts) | Credit spread vs. sector (+10pts) |

*All technical sub-scores normalized to 20% maximum contribution to composite.*

---

## Shared Utility: Asset Class Detector

**Location:** `/Agentic/income-platform/shared/asset_class_detector/`  
**Consumed by:** Agent 03, Agent 04, Agent 05, future agents

**v1 — Rule-Based (MVP):**
```
quoteType = 'ETF' + 'covered call' in name → otm_covered_etf
quoteType = 'ETF' + 'bond'/'fixed income' in category → bond_etf
sector = 'Real Estate' + quoteType = 'EQUITY' → reit
industry = 'REIT—Mortgage' → mreit
industry = 'Asset Management' + BDC flag → bdc
quoteType = 'ETF' + 'closed-end' → cef
quoteType = 'EQUITY' + preferred flag → preferred_stock
default → dividend_stock
```

**v2 — ML (Post-MVP):** sentence-transformers/all-MiniLM-L6-v2 + linear classification head, trained on labeled ticker dataset generated during v1 operation.

---

## Data Provider Abstraction

```python
class DataProvider(ABC):
    @abstractmethod
    def fetch_price_history(self, ticker: str, period: str) -> pd.DataFrame: ...
    
    @abstractmethod  
    def fetch_fundamentals(self, ticker: str, asset_class: str) -> Dict: ...
    
    @abstractmethod
    def fetch_distribution_history(self, ticker: str) -> pd.DataFrame: ...

# Resolution order per data type:
# Price/technicals    → yfinance → Polygon
# AFFO/NII/CEF data   → FMP → yfinance (partial)
# Options chain       → Polygon → yfinance
# Distribution ROC%   → FMP → fund filings (manual fallback)
```

---

## Learning Loop

**Frequency:** Quarterly  
**Shadow Portfolio:** Rejected tickers tracked for 90 days post-rejection  
**Evaluation Metrics:** Yield accuracy, yield trap miss rate, false rejection rate  
**Weight Adjustment:** LR = 0.01 × (actual_performance − predicted_performance)  
**Storage:** Adjusted weights written back to Preference Table  
**Bounds:** No single weight adjustment >5% per cycle; weights always sum to 100%

---

## Non-Functional Requirements

| Requirement | Target |
|---|---|
| Score latency (cached Monte Carlo) | <500ms p95 |
| Score latency (fresh Monte Carlo) | <3s p95 |
| Monte Carlo cache TTL | 30 days |
| Score history retention | 24 months |
| Throughput | 100 scores/minute batch mode |
| Test coverage | ≥85% |
| Uptime | 99.5% |
