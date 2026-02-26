# Decisions Log — Agent 02 + Agent 12

---

## ADR-001: HTML → Markdown at Ingest Time

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** Convert article HTML to Markdown at ingestion time. Store Markdown in `full_text`. Never store raw HTML.

**Rationale:** LLM extraction (Claude Haiku) performs better on clean Markdown than raw HTML. Storage is more efficient. Downstream consumers (Agent 03, philosophy synthesis) never need to handle HTML. Runtime truncation to ~6000 tokens is applied on the already-clean Markdown.

**Alternatives Considered:** Store raw HTML + convert at extraction time. Rejected — would require double-conversion overhead on every extraction call and every re-extraction run.

---

## ADR-002: APIDojo Endpoint Confirmed as /articles/v2/list

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** Use `/articles/v2/list` with `author` + `page` params (not `/news/v2/list` with `id` + `number`).

**Rationale:** Confirmed from V1 bulk ingestion code. The `/articles/v2/list` endpoint returns the correct nested response shape `{data: [{id, attributes: {title, publishOn}}]}` and supports pagination via `page` parameter. The news endpoint returned a different (flatter) shape unsuitable for author-scoped article ingestion.

**Impact:** `seeking_alpha.py` uses `_normalize_article()` to flatten the nested `attributes` structure into a clean dict for use throughout the pipeline.

---

## ADR-003: S-Curve Decay Formula

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** Use sigmoid-based S-curve decay: `1 / (1 + exp(k * (days_elapsed - halflife_days)))` where `k = 10 / aging_days`.

**Rationale:** S-curve provides three desirable properties: (1) fresh recommendations retain near-full weight, (2) aging happens gradually around the halflife, (3) old recommendations decay toward (not to) zero. Linear decay would penalize fresh recommendations unfairly; hard cutoffs would create cliff effects.

**Parameters:** Default `aging_days=365`, `halflife_days=180`, `min_weight=0.1`. Configurable per-analyst via `analysts.config` JSONB.

---

## ADR-004: Recommendation Supersession Model

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** When analyst publishes a new recommendation for a ticker they already cover, prior recs are marked `is_active=False, superseded_by=new_rec.id`. Historical recs are never deleted.

**Rationale:** Preserves complete recommendation history for accuracy backtesting and analytics. The supersession chain allows traversal of an analyst's position history on any ticker. Consensus and signal endpoints query `is_active=True` only, so superseded recs don't pollute current signals.

---

## ADR-005: Philosophy Synthesis — LLM vs K-Means Threshold

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** Use Claude Sonnet LLM summary for analysts with < 20 articles. Switch to K-Means K=5 clustering on article embeddings for analysts with ≥ 20 articles.

**Rationale:** LLM summary is higher quality but can't extract reliable statistical patterns from small samples. K-Means clustering at ≥ 20 articles reveals genuine thematic clusters (sectors, strategies, risk tolerance) that LLM synthesis would miss. The centroid vector enables semantic similarity matching between analyst philosophies.

---

## ADR-006: Dual-Lens Proposal — Never Silent Blocking

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** Agent 12 always generates proposals regardless of alignment state. Even on VETO, Path B (analyst-as-stated with explicit acknowledgment) remains available.

**Rationale:** User autonomy is a platform core principle. The platform's role is to inform and protect, not to override. Users who understand the risks and choose to proceed with an analyst-recommended position against platform advice must be able to do so — but only with full transparency and documented acknowledgment. Silent blocking would undermine user trust and violate the capital preservation philosophy (which is about informed decisions, not forced ones).

---

## ADR-007: Agent 12 Writeback to Agent 02

**Date:** 2026-02-25  
**Status:** Accepted

**Decision:** After generating a proposal, Agent 12 writes `platform_alignment` and `platform_scored_at` back to `analyst_recommendations` in Agent 02's database.

**Rationale:** Enables Agent 02's Intelligence Flow backtest processor to access the platform alignment outcome when evaluating recommendation accuracy. This closes the feedback loop: analyst recommendation → proposal → user decision → accuracy attribution. Without this writeback, the accuracy log would be missing the platform's view of the recommendation quality at time of proposal.
