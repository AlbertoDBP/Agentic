# Agent 03 — Income Scorer: Functional Specification

**Platform:** Income Fortress Platform  
**Agent:** 03 — Income Scorer  
**Version:** 1.0.0  
**Date:** 2026-02-25

---

## Purpose & Scope

Agent 03 produces the **Income Fortress Score (0–100)** for any supported income-generating security. It is the central analytical engine of the platform — every investment proposal, alert, and portfolio decision flows from this score.

The score measures two things exclusively: **capital safety** and **income sustainability**. It does not measure tax efficiency (Agent 05), benchmark relative performance (Agent 04), or entry timing beyond the technical sub-score contribution.

---

## Responsibilities

Agent 03 is solely responsible for:

1. Detecting or confirming the asset class of a security (via shared detector)
2. Routing securities through the appropriate class-specific quality gate
3. Collecting class-appropriate fundamental and technical data
4. Running Monte Carlo NAV erosion analysis for applicable asset classes
5. Computing a 4-component composite score with class-specific weights
6. Applying VETO logic and forcing score to 0 on safety failures
7. Applying risk penalties from Agent 02 newsletter signals
8. Building the standardized score output JSON including parallel tax metadata
9. Persisting versioned scores and publishing scored events to the message bus
10. Maintaining the quarterly learning loop and shadow portfolio

---

## Supported Asset Classes (MVP)

All 7 classes supported from day one, with MVP priority on:

**Priority 1 (MVP core):** Dividend Stocks, OTM Covered Call ETFs, Bonds/Bond ETFs  
**Priority 2 (full scope):** REITs, mREITs, BDCs, CEFs, Preferred Stocks

---

## Interfaces

### Input

```
POST /api/v1/score
{
  "ticker": string,           // Required
  "asset_class_hint": string, // Optional — skip detection if provided
  "force_fresh_mc": bool,     // Optional — bypass Monte Carlo cache
  "context": {
    "portfolio_id": uuid,     // Optional — for portfolio-aware scoring
    "user_id": uuid           // Optional — for preference loading
  }
}
```

### Output

```
{
  "ticker": string,
  "asset_class": string,
  "composite_score": int,          // 0–100, or 0 if VETO
  "veto_triggered": bool,
  "veto_reason": string | null,
  "sub_scores": {
    "income": float,
    "durability": float,
    "valuation": float,
    "technical": float
  },
  "class_weights_used": object,
  "risk_penalties": {
    "total_penalty": float,
    "flags": []
  },
  "monte_carlo": object | null,
  "quality_gate": object,
  "tax_efficiency": object,        // Parallel metadata, 0% weight
  "recommendation": string,        // Strong Buy / Buy / Watch / Avoid / VETO
  "decision_threshold_used": string,
  "class_context": string,
  "confidence": float,
  "scored_at": timestamp,
  "score_version": string,
  "data_sources_used": string[]
}
```

### Async (Message Bus)

Publishes `scored_event` on score completion:
```
{
  "event": "security.scored",
  "ticker": string,
  "composite_score": int,
  "veto_triggered": bool,
  "asset_class": string,
  "scored_at": timestamp
}
```
Consumed by: Agent 04, Agent 05, Alert System, Portfolio Builder.

---

## Dependencies

| Dependency | Role | Required |
|---|---|---|
| Agent 01 — Market Data Service | Price history, technical indicators, options chain | Required |
| Agent 02 — Newsletter Ingestion | Analyst signals, sentiment scores for risk penalty layer | Optional (graceful degradation) |
| Shared: Asset Class Detector | Ticker classification | Required |
| yfinance | Primary data: price, dividends, fundamentals | Required |
| FMP (Financial Modeling Prep) | AFFO, NII, CEF discount, non-accrual data | Required for REITs, BDCs, CEFs |
| Polygon.io | Options chain depth, price precision | Required for Covered Call ETFs |
| PostgreSQL | Score persistence, shadow portfolio, weight history | Required |
| Valkey/Redis | Monte Carlo result cache (30-day TTL) | Required |
| Preference Table | Class weight sets, gate thresholds, user settings | Required |

---

## Success Criteria

**Functional:**
- All 7 asset classes score correctly with class-appropriate gate and weights
- VETO fires on every defined trigger condition without exception
- Tax efficiency field populated but never affects composite score
- Agent 02 negative signals apply penalty; positive signals are neutral
- Monte Carlo cache hits correctly within 30-day TTL
- Quarterly learning loop adjusts weights within ±5% bounds per cycle

**Performance:**
- Score latency <500ms p95 (cached Monte Carlo)
- Score latency <3s p95 (fresh Monte Carlo)
- Batch throughput: 100 scores/minute

**Quality:**
- Test coverage ≥85%
- Historical validation: yield trap detection rate >80% on backtested data

---

## Non-Functional Requirements

**Reliability:** Graceful degradation if Agent 02 is unavailable (skip penalty layer, note in output). Fallback to yfinance if FMP/Polygon unavailable (note data gaps in output).

**Extensibility:** New asset classes added via Preference Table only — no code changes required for weight sets or gate thresholds.

**Auditability:** Every score versioned with full snapshot of weights used, data sources, and gate results. Score history retained 24 months.

**Security:** No user financial data stored in score records. Portfolio association via UUID only.
