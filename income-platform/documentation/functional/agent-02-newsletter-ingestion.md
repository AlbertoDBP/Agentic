# Functional Specification — Agent 02: Newsletter Ingestion (The Dividend Detective)

**Version:** 1.0  
**Status:** ✅ Complete  
**Last Updated:** 2026-02-25  
**Service Port:** 8002

---

## Purpose & Scope

Agent 02 is the platform's intelligence acquisition layer. It reads Seeking Alpha analyst articles, understands what analysts think about income investments, and makes that knowledge available in a structured, weighted, time-aware form to the rest of the platform — primarily Agent 12 (Proposal Agent) and Agent 03 (Income Scorer).

The core insight it provides: **what do knowledgeable income analysts actually think about this ticker, how much should we trust that view, and how fresh is it?**

---

## Responsibilities

**Ingestion:** Fetch new articles from registered SA analysts via APIDojo. Convert HTML to Markdown at ingest time. Deduplicate via SHA-256 content hash and SA article ID before processing.

**Extraction:** Extract structured income signals from each article via Claude Haiku. Signals include: ticker, recommendation, sentiment score, yield estimate, payout ratio, dividend CAGR, safety grade, bull/bear thesis, key risks, asset class, sector, source reliability.

**Embedding:** Generate 1536-dimension OpenAI embeddings for article bodies (semantic search) and recommendation theses (thesis similarity).

**Staleness Management:** Apply S-curve decay to recommendation weights weekly. Fresh recommendations carry full weight; aging ones decay toward zero. Expired recommendations are deactivated.

**Accuracy Backtesting:** Compare original recommendations against actual price and dividend outcomes at T+30 and T+90 days using FMP market data. Track cut detection for dividends. Update per-analyst accuracy and sector-specific alpha scores.

**Philosophy Synthesis:** Build an AI-readable profile of each analyst's investment style. Under 20 articles: LLM summary via Claude Sonnet. At 20+ articles: K-Means K=5 clustering on article embeddings produces a structured philosophy centroid.

**Consensus Building:** Compute weighted consensus scores across all active analysts for a given ticker. Weights combine analyst accuracy × recommendation decay × optional user preference.

**API:** Expose all stored intelligence via a clean REST API. The `/signal/{ticker}` endpoint is the primary contract surface for Agent 12.

---

## Interfaces

### Inputs

| Source | Data | Frequency |
|---|---|---|
| APIDojo SA API | Article list + full content HTML | Tue/Fri 7AM ET |
| FMP API | Historical price + dividend data | Mon 6AM ET (backtest) |
| POST /analysts | New analyst registration | On-demand |
| POST /flows/harvester/trigger | Manual harvest trigger | On-demand |

### Outputs

| Consumer | Endpoint | Data |
|---|---|---|
| Agent 12 | GET /signal/{ticker} | AnalystSignalResponse |
| Agent 03 | GET /recommendations/{ticker} | RecommendationResponse list |
| Dashboard | GET /analysts | Analyst registry |
| Dashboard | GET /consensus/{ticker} | Weighted consensus score |

---

## Dependencies

| Dependency | Purpose | Fallback |
|---|---|---|
| APIDojo SA API | Article ingestion | Log + skip (no articles fetched) |
| Anthropic Claude Haiku | Signal extraction | Skip article (no extraction) |
| OpenAI text-embedding-3-small | Content + thesis embedding | Store article without embedding |
| FMP API | Backtest price/dividend data | Skip backtest for that rec |
| Anthropic Claude Sonnet | Philosophy summary (<20 articles) | Keep prior philosophy |
| PostgreSQL + pgvector | Primary storage | Service unavailable |
| Valkey | Consensus + signal caching | Compute fresh on every request |

---

## Success Criteria

**Harvester Flow**
- Articles ingested within 4 hours of publication (Tue/Fri schedule)
- Zero duplicate articles stored (both SA ID and content hash checks)
- ≥ 85% of articles with content > 500 chars produce at least 1 extracted ticker
- Per-analyst and per-article failures isolated — one failure never aborts the flow

**Intelligence Flow**
- All active recommendations have decay_weight updated within 24 hours of Monday 6AM
- Recommendations published > 365 days ago deactivated (is_active=False)
- Analyst accuracy updated within 24 hours of backtest run
- Philosophy updated for every analyst with ≥ 1 article

**API**
- GET /signal/{ticker} responds in < 500ms (cache hit) or < 2s (cache miss)
- GET /consensus/{ticker} responds in < 500ms (cache hit) or < 1s (cache miss)
- 99% uptime during market hours

---

## Non-Functional Requirements

**Rate Limiting:** SA API capped at 10 calls/minute (configurable). FMP API called only during Intelligence Flow — not on hot request path.

**Caching:** Consensus cached 30 minutes, signal cached 60 minutes in Valkey. Cache invalidated when Intelligence Flow updates underlying data.

**Deduplication:** Two-pass — SA article ID (fast, no content needed) then SHA-256 content hash (catches reposts). Neither check requires external API calls.

**Recommendation Supersession:** When an analyst publishes a new recommendation for a ticker they already have an active rec on, the prior rec is marked `is_active=False, superseded_by=new_id`. Only the most recent active rec per analyst+ticker is considered for signals and consensus.

**Error Isolation:** All external API calls wrapped in try/catch with per-item continuation. A failed Claude extraction doesn't prevent article storage. A failed FMP lookup doesn't abort the backtest for other tickers.

**Security:** API keys stored in environment variables. Service binds to 127.0.0.1 internally — exposed only through Nginx reverse proxy. Non-root Docker user.
