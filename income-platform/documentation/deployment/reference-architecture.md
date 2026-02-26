# Reference Architecture — Agent 02 + Agent 12

**Income Fortress Platform**  
**Date:** 2026-02-25  
**Version:** 1.0

---

## System Overview

Agent 02 and Agent 12 form the platform's **signal acquisition and proposal pipeline**. Agent 02 is the intelligence layer — it reads, understands, and scores analyst opinions. Agent 12 is the decision layer — it synthesizes those opinions with the platform's independent assessment and presents the user with a structured proposal.

The core design principle: **the platform never silently overrides an analyst.** Users always see both perspectives and make the final call.

---

## Agent 02 — Architecture

Agent 02 is a FastAPI microservice with two internal flows and one external API surface.

### Two Flows

**Harvester Flow** (Tue + Fri 7AM ET)
Ingests new articles from registered SA analysts. For each article: fetch via APIDojo → HTML to Markdown → Claude Haiku extraction → OpenAI embedding → persist to PostgreSQL. Rate-limited at 10 calls/minute. Per-analyst and per-article error isolation — one failure never aborts the full run.

**Intelligence Flow** (Mon 6AM ET)
Weekly maintenance across all stored data. Four sequential processors: staleness decay (S-curve reweighting) → accuracy backtest (FMP price/dividend checks at T+30 and T+90) → philosophy synthesis (LLM summary or K-Means clustering) → consensus rebuild.

### API Surface (Port 8002)

```
GET  /health                           Service health + flow status
GET  /analysts                         List registered analysts
POST /analysts                         Add analyst by SA author ID
GET  /analysts/{id}                    Analyst profile + accuracy stats
GET  /analysts/{id}/recommendations    All recs by analyst
GET  /recommendations/{ticker}         All active recs for ticker
GET  /consensus/{ticker}               Weighted consensus (cached 30min)
GET  /signal/{ticker}                  Full signal → Agent 12 contract
POST /flows/harvester/trigger          Manual harvester trigger
POST /flows/intelligence/trigger       Manual intelligence trigger
GET  /flows/status                     Last run status
```

### Data Architecture

All tables in `platform_shared` schema (shared with Agent 01):

```
analysts               → analyst registry, accuracy, philosophy
analyst_articles       → ingested articles with embeddings
analyst_recommendations → extracted signals with decay weights
analyst_accuracy_log   → backtest outcomes
credit_overrides       → manual safety grade overrides
flow_run_log           → flow execution history
```

pgvector IVFFlat indexes on content_embedding columns enable semantic article and thesis search.

---

## Agent 12 — Architecture

Agent 12 is the decision interface layer. It receives signals from Agent 02 and independent assessments from Agents 03, 04, 05 — then synthesizes them into a structured proposal for the user.

### Three Trigger Modes

**Signal-Driven (Automatic):** Agent 02 Harvester completes → `proposal_readiness=true` → event/queue → Agent 12 generates proposal.

**On-Demand (User-Initiated):** User requests proposal for ticker from dashboard → API → Agent 12.

**Scheduled Re-evaluation:** Weekly — re-evaluate open proposals where price moved >10% or platform score changed ≥1 grade.

### Dual-Lens Proposal Model

Every proposal presents two complete pictures side by side:

**Lens 1 — Analyst View:** Analyst recommendation, yield estimate, safety grade, bull/bear thesis, source reliability, entry suggestion.

**Lens 2 — Platform View:** Independent income score (Agent 03), entry zone (Agent 04), tax placement (Agent 05), VETO flags.

### Platform Alignment States

```
Aligned    → Both perspectives agree (divergence ≤ 0.25)
Partial    → Mild disagreement (divergence ≤ 0.50)
Divergent  → Significant disagreement (divergence > 0.50)
Vetoed     → Platform VETO flags present
```

Proposals are **always generated** regardless of alignment state. Path A (platform-recommended execution) and Path B (analyst-as-stated override) are always available — except Path A is unavailable on VETO.

### User Action Flows

```
Aligned/Partial:   Execute Path A  |  Execute Path B (with note)  |  Reject
Divergent:         Execute Path A  |  Execute Path B (requires divergence acknowledgment)  |  Reject
Vetoed:            [Path A unavailable]  |  Execute Path B (requires hard VETO acknowledgment)  |  Reject
```

---

## Integration Contract: Agent 02 → Agent 12

Agent 12 calls `GET /signal/{ticker}` on Agent 02. The response contract:

```json
{
  "ticker": "O",
  "asset_class": "REIT",
  "sector": "Real Estate",
  "signal_strength": "strong",
  "proposal_readiness": true,
  "analyst": {
    "id": 1,
    "display_name": "Analyst Name",
    "accuracy_overall": 0.72,
    "sector_alpha": {"REIT": 0.81},
    "philosophy_summary": "Focuses on high-yield sustainability...",
    "philosophy_source": "llm"
  },
  "recommendation": {
    "id": 42,
    "label": "Buy",
    "sentiment_score": 0.75,
    "yield_at_publish": 0.052,
    "payout_ratio": 0.75,
    "safety_grade": "A",
    "source_reliability": "EarningsCall",
    "bull_case": "29 year dividend streak...",
    "bear_case": "Rising rate headwind...",
    "published_at": "2025-01-10T12:00:00Z",
    "decay_weight": 0.85
  },
  "consensus": {
    "ticker": "O",
    "score": 0.72,
    "confidence": "low",
    "n_analysts": 1,
    "n_recommendations": 1,
    "dominant_recommendation": "Buy"
  },
  "generated_at": "2026-02-25T10:00:00Z"
}
```

Agent 12 writes `platform_alignment` and `platform_scored_at` back to `analyst_recommendations` after proposal generation.

---

## Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.109 |
| ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL 16 + pgvector |
| Cache | Valkey / Redis 7.2 |
| Orchestration | Prefect 2.16 |
| LLM Extraction | Claude Haiku |
| LLM Philosophy | Claude Sonnet |
| Embeddings | OpenAI text-embedding-3-small (1536d) |
| Market Truth | Financial Modeling Prep API |
| SA Ingestion | APIDojo / RapidAPI |
| Containerization | Docker (multi-stage) |
| Reverse Proxy | Nginx |
| Infrastructure | DigitalOcean |
