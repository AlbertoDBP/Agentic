# ADR-001: Post-Scoring LLM Explanation Layer

**Platform:** Income Fortress Platform  
**Agent Scope:** Agent 03 (Income Scorer) + Chat Layer  
**Date:** 2026-02-25  
**Status:** ACCEPTED  
**Deciders:** Alberto  

---

## Context

The Income Scorer produces a deterministic composite score (0–100) with up to 12 sub-components, VETO status, risk flags, Monte Carlo results, and tax metadata. While this structured JSON output is precise and auditable, it is difficult for retail investors to interpret directly.

A score of 78.4 with `durability: 68`, `income: 92`, `monte_carlo.erosion_probability_24m: 0.12`, and `risk_flags: []` requires financial literacy to parse correctly. The platform needs a way to surface scoring results in plain English — in chat responses, email/SMS notifications, and dashboard tooltips — without compromising the integrity of the deterministic scoring engine.

---

## Decision

**After** the deterministic scoring pipeline completes and returns its structured result, pass the full output JSON to an LLM with a constrained prompt that generates a plain-English explanation for the end user.

The LLM operates strictly as a **translator** — it reads the already-computed numbers and converts them to natural language. It never modifies, overrides, or re-derives any score, sub-score, VETO decision, or recommendation.

---

## Detailed Design

### Flow

```
[1] User query or scoring trigger
        ↓
[2] Agent 03: Deterministic scoring pipeline runs to completion
        ↓
[3] Structured score JSON returned (composite, sub_scores, veto, MC, tax, recommendation)
        ↓
[4] LLM Prompt Generator:
    - Injects full score JSON as facts
    - Applies fixed system prompt (conservative advisor persona)
    - Adds user context (FL residency, account type if available)
        ↓
[5] LLM generates plain-English explanation (1–3 paragraphs or bullets)
    - temperature: 0.3–0.5 (low creativity)
    - max_tokens: 300
        ↓
[6] Explanation stored in scores.explanation_text (audit trail)
        ↓
[7] Explanation surfaced in: chat response / email-SMS summary / dashboard tooltip
```

### System Prompt (Fixed)

```
You are a clear, conservative income-investment advisor.
Explain the score for {ticker} in plain English for a retail investor.
Use ONLY the facts provided below. Do NOT speculate, do NOT add new information,
do NOT override the score, veto, or any sub-score.
Be concise, transparent, and highlight the most important drivers (positive and negative).
If a veto was triggered, emphasize capital safety first.
```

### Code Skeleton

```python
def generate_explanation(scoring_result: Dict, user_context: str = "") -> str:
    prompt = f"""
You are a clear, conservative income-investment advisor.
Explain the score for {scoring_result['ticker']} in plain English for a retail investor.
Use ONLY the facts below. Do NOT speculate, add new information, or override the score/veto.
Be concise, transparent, and highlight the most important drivers (positive and negative).
If a veto was triggered, emphasize capital safety first.

Facts:
{json.dumps(scoring_result, indent=2)}

User context: {user_context}
"""
    explanation = call_llm(
        prompt,
        max_tokens=300,
        temperature=0.4
    )
    return explanation
```

### Invocation Policy

The LLM explanation is **not called on every background scoring cycle**. It is invoked only when:
- A user explicitly requests a score explanation via chat
- A VETO is triggered (explanation auto-generated for notification)
- A score is surfaced in the React dashboard detail view
- An email/SMS alert is dispatched

This keeps inference costs low and latency isolated to user-facing interactions.

### Output Persistence

The generated explanation is stored alongside the deterministic score:

```sql
ALTER TABLE scores ADD COLUMN explanation_text TEXT;
ALTER TABLE scores ADD COLUMN explanation_prompt TEXT;  -- full prompt for audit
ALTER TABLE scores ADD COLUMN explanation_model TEXT;   -- model used
ALTER TABLE scores ADD COLUMN explanation_generated_at TIMESTAMP;
```

---

## Consequences

### Positive

- **Explainability:** Raw sub-scores become intuitive narratives — "Despite a strong income score of 92, durability came in at 68 due to leverage of 8.2× exceeding the 7.6× threshold."
- **User trust:** Retail investors understand *why* a decision was made, not just *what* it was.
- **VETO clarity:** When veto fires, the explanation leads with capital safety — reinforcing the platform's core principle in the user's language.
- **Multi-class consistency:** Same explanation style whether the ticker is a BDC, bond ETF, or covered call ETF — because the input structure is always the same standardized JSON.
- **Audit trail:** Every explanation stored with its full prompt and model version — fully reproducible and reviewable.
- **Zero score integrity risk:** LLM receives output only after all computation is complete. It cannot influence any numeric result.

### Negative / Risks

- **LLM hallucination risk (mitigated):** Low temperature (0.3–0.5), fact-only prompt, and output length limits reduce but do not eliminate hallucination. Mitigation: prompt hardening + audit storage + human review option for high-stakes alerts.
- **Latency added to user-facing queries:** One additional LLM inference per displayed result (~200–500ms). Acceptable for chat/dashboard; not acceptable for background batch scoring (which is why invocation is gated).
- **Model dependency:** Adds a dependency on an LLM provider (Claude Haiku recommended for cost/speed balance). Provider outage degrades explanation feature but does not affect scoring.
- **Prompt drift over time:** As scoring output structure evolves, the system prompt may need updating. Mitigation: system prompt versioned alongside score_version.

---

## Safeguards

| Safeguard | Implementation |
|---|---|
| Fact-only constraint | System prompt explicitly forbids speculation and new information |
| Low temperature | 0.3–0.5 — minimizes creative deviation |
| Output length limit | max_tokens: 300 — keeps explanation focused |
| Post-computation only | LLM invoked after scoring pipeline returns; cannot influence computation |
| Audit trail | Full prompt + output stored in scores table |
| Human review option | High-stakes alerts (VETO triggers) flagged for optional manual review before dispatch |
| Model versioning | `explanation_model` field tracks which model generated each explanation |

---

## Alternatives Considered

**Alternative A: Static template strings**  
Pre-written templates filled with score values (e.g., "Score: {score}. Income: {income}. Durability: {durability}."). Rejected — readable but not explanatory. Cannot highlight contradictions, context, or relative importance dynamically.

**Alternative B: LLM integrated into scoring pipeline**  
Use LLM to assist with scoring decisions (not just explanation). Rejected — violates the deterministic scoring principle. Score integrity depends on formulas, thresholds, and Preference Table logic — not LLM inference. This ADR explicitly keeps LLM outside the computation boundary.

**Alternative C: No explanation layer**  
Return JSON only. Rejected — platform targets retail investors who cannot be expected to parse 12 sub-scores. Explainability is a core UX requirement.

---

## Implementation Impact

| Component | Change Required |
|---|---|
| Agent 03 — Score Output Builder | Add `explanation_text` field to output JSON (optional, populated on request) |
| Chat Layer | Call `generate_explanation()` before returning score response to user |
| Scores Table | Add 4 explanation columns (text, prompt, model, generated_at) |
| Email/SMS Formatter | Use explanation_text as notification body for VETO alerts |
| React Dashboard | Surface explanation_text in score detail tooltip/drawer |
| Preference Table | Add `explanation_model`, `explanation_enabled`, `explanation_temperature` per user |

---

## Related Decisions

- Agent 03 VETO logic (reference-architecture.md) — VETO fires before LLM is invoked; explanation cannot soften veto
- Tax efficiency as parallel metadata (ADR context) — tax_efficiency included in LLM facts, enabling FL-specific context in explanations
- Agent 02 newsletter signals — Analyst signal penalties included in facts; LLM can reference them in explanation
