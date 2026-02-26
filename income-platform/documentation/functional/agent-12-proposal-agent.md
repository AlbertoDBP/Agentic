# Functional Specification — Agent 12: Proposal Agent

**Version:** 1.0  
**Status:** 📐 Spec Complete — Implementation Pending  
**Last Updated:** 2026-02-25

---

## Purpose & Scope

Agent 12 is the platform's decision interface layer. It synthesizes the analyst view (from Agent 02) with the platform's independent assessment (from Agents 03, 04, 05) into a structured proposal that users can act on with full context.

The core design principle: **the platform never silently overrides an analyst.** The user always sees both perspectives — the analyst's thesis and the platform's independent score — side by side. The user makes the final decision.

---

## Responsibilities

**Signal Acquisition:** Call Agent 02's `/signal/{ticker}` endpoint to get the current analyst view including best recommendation, weighted consensus, and analyst philosophy profile.

**Platform Assessment:** Concurrently call Agents 03/04/05 to get the platform's independent income score, entry zone, and tax placement recommendation.

**Alignment Computation:** Compare analyst sentiment against platform score to compute a `platform_alignment` value: Aligned | Partial | Divergent | Vetoed.

**Proposal Generation:** Build a `ProposalObject` containing both lenses side by side — analyst view (Lens 1) and platform view (Lens 2) — with execution parameters and alignment state.

**VETO Enforcement:** When Agent 03 returns VETO flags (e.g., NAV erosion detected, yield trap signals), Path A execution is blocked. Path B (analyst-as-stated override) requires hard VETO acknowledgment.

**User Action Handling:** Process Execute Path A, Execute Path B (override), and Reject actions. Log override rationales. Feed override outcomes back to Agent 02's accuracy log as enriched outcomes.

**Re-evaluation:** Weekly sweep of open proposals where price moved >10% or platform score changed ≥1 grade. Mark stale proposals and notify user.

**Writeback:** After proposal generation, write `platform_alignment` and `platform_scored_at` back to Agent 02's `analyst_recommendations` table.

---

## Alignment Logic

```python
def compute_alignment(analyst_sentiment, platform_score, veto_flags, safety_gate):
    if veto_flags:
        return "Vetoed"
    # platform_score: 0-100 → normalize to -1.0 to 1.0
    platform_sentiment = (platform_score - 50) / 50
    divergence = abs(analyst_sentiment - platform_sentiment)
    if divergence <= 0.25:
        return "Aligned"
    elif divergence <= 0.50:
        return "Partial"
    else:
        return "Divergent"
```

| State | Divergence | Path A | Path B | Override Required |
|---|---|---|---|---|
| Aligned | ≤ 0.25 | ✅ Available | ✅ Available | No |
| Partial | ≤ 0.50 | ✅ Available | ✅ Available | Light note |
| Divergent | > 0.50 | ✅ Available | ✅ Available | Divergence summary acknowledgment |
| Vetoed | n/a | ❌ Blocked | ✅ Available | Hard VETO acknowledgment |

---

## ProposalObject Schema

```
platform_shared.proposals

ticker                  varchar
analyst_signal_id       int → analyst_recommendations.id
analyst_id              int → analysts.id
platform_score          numeric (0–100 from Agent 03)
platform_alignment      varchar (Aligned|Partial|Divergent|Vetoed)
veto_flags              jsonb (VETO reason codes from Agent 03)
divergence_notes        text (auto-generated explanation)

-- Lens 1: Analyst
analyst_recommendation  varchar
analyst_sentiment       numeric
analyst_thesis_summary  text
analyst_yield_estimate  numeric
analyst_safety_grade    varchar

-- Lens 2: Platform
platform_yield_estimate numeric
platform_safety_result  jsonb
platform_income_grade   varchar

-- Execution Parameters
entry_price_low         numeric  (from Agent 04)
entry_price_high        numeric  (from Agent 04)
position_size_pct       numeric  (from Agent 04)
recommended_account     varchar  (from Agent 05)
sizing_rationale        text

-- State
status                  varchar (pending|executed_aligned|executed_override|rejected|expired)
trigger_mode            varchar (signal_driven|on_demand|re_evaluation)
override_rationale      text
user_acknowledged_veto  boolean
decided_at              timestamptz
expires_at              timestamptz  (default +14 days)
created_at              timestamptz
updated_at              timestamptz
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /proposals | List proposals (filter: status, ticker, analyst) |
| GET | /proposals/{id} | Full proposal detail |
| POST | /proposals/generate | On-demand proposal for ticker |
| POST | /proposals/{id}/execute | Execute Path A (platform-aligned) |
| POST | /proposals/{id}/override | Execute Path B (analyst-as-stated) |
| POST | /proposals/{id}/reject | Reject proposal |
| GET | /proposals/{id}/re-evaluate | Force re-evaluation |
| GET | /health | Service health |

---

## Trigger Modes

**Signal-Driven (Automatic):** Agent 02 Harvester completes with `proposal_readiness=true` → emits event/queue message → Agent 12 auto-generates proposal. No user action required to trigger.

**On-Demand (User-Initiated):** User requests proposal for ticker from dashboard or Research page → POST /proposals/generate → Agent 12 fetches signal + runs assessment → returns proposal.

**Scheduled Re-evaluation:** Weekly sweep of open (pending) proposals. Re-evaluates when: price moved >10% since proposal generated, OR platform score changed ≥1 grade. Updates proposal with fresh data, notifies user if alignment state changed.

---

## Dependencies

| Dependency | Data | Failure Mode |
|---|---|---|
| Agent 02 GET /signal/{ticker} | AnalystSignalResponse | Proposal cannot be generated — surface error |
| Agent 03 POST /score/ticker/{ticker} | IncomeScore + VETO flags | Mark proposal incomplete, no platform score |
| Agent 04 POST /entry-price/{ticker} | Entry zones + position size | Use market price fallback, flag missing |
| Agent 05 POST /tax-placement/{ticker} | Account type recommendation | Omit tax guidance from proposal |

Agents 03/04/05 are called concurrently after Agent 02 signal to minimize latency.

---

## Non-Functional Requirements

**Latency:** On-demand proposal generation < 8 seconds end-to-end (Agents 03/04/05 called concurrently).

**Proposal Validity:** Default 14-day expiry (configurable per ticker). Re-evaluation triggered automatically within validity window if thresholds crossed.

**Auditability:** Every proposal, decision, and override rationale permanently stored. No soft deletes. Complete compliance trail from signal → proposal → user decision.

**Override Logging:** Override rationale is mandatory (minimum 20 characters). Override outcomes fed back to Agent 02 accuracy log as enriched outcomes for analyst calibration.

**VETO Immutability:** VETO flags from Agent 03 cannot be dismissed without explicit acknowledgment recorded in the proposal record. VETO acknowledgment text stored verbatim.
