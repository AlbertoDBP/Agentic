# Agent 02 — Newsletter Deep Intelligence Design

**Date:** 2026-03-26
**Status:** Draft — Pending Implementation Plan
**Scope:** Agent 02 (Newsletter Ingestion), Agent 01 (Market Data), Agent 07 (Opportunity Scanner), Agent 12 (Proposal Generator)

---

## 1. Problem Statement

Agent 02 currently extracts ticker-level signals (sentiment, recommendation, yield, safety grade) from Seeking Alpha articles and produces a weighted consensus that feeds Agent 03 as a bearish penalty modifier. This is useful but shallow.

What's missing:

- **How** analysts evaluate assets — what metrics, thresholds, and reasoning structures they use
- **Learning** — a growing per-analyst knowledge model that compounds over time as more articles are ingested
- **Analyst suggestions as investable ideas** — recommendations surfaced as scored opportunities, not just penalty signals
- **Feature gap awareness** — when analysts cite metrics the platform doesn't track, the platform learns to track them

---

## 2. Goals

1. Extract analyst evaluation frameworks (not just conclusions) from every article
2. Build a per-analyst, per-asset-class knowledge model that grows richer over time
3. Surface analyst recommendations as scored investment ideas via a shared table consumed by Agent 07
4. Enable Agent 12 to query the knowledge base for proposal commentary enrichment
5. Detect and resolve gaps between analyst-cited metrics and platform-tracked features
6. Keep Agent 02 as a pure producer — fully decoupled from Agent 07 and Agent 12 runtime workflows

---

## 3. Architecture

### 3.1 Pipeline Overview

```text
Harvester Flow (Tue/Fri 7AM ET)
  ├── Pass 1 [Claude Haiku]   → ticker signals (existing)
  └── Pass 2 [Claude Sonnet]  → framework extraction (NEW)
        ↓
   platform_shared.article_frameworks        (NEW) ← written by Harvester Flow
   platform_shared.analyst_suggestions       (NEW) ← written by Harvester Flow
   platform_shared.feature_gap_log           (NEW) ← written by Harvester Flow

Intelligence Flow (periodic)
  ├── Staleness decay sweep          (existing)
  ├── FMP accuracy backtest T+30/90  (existing)
  ├── Philosophy synthesis           (existing)
  ├── Framework synthesis            (NEW)
  ├── Feature gap resolution         (NEW)
  └── Consensus rebuild              (existing)
        ↓
   platform_shared.analyst_framework_profiles  (NEW) ← written by Intelligence Flow
   platform_shared.feature_registry            (NEW) ← written by Intelligence Flow

Runtime (Agent 02 out of workflow)
  Agent 07 → reads analyst_suggestions directly from platform_shared
  Agent 12 → calls GET /kb/analyst-context on Agent 02 for commentary enrichment
```

### 3.2 Design Principles

- **Agent 02 is a pure producer.** It writes to shared tables and exposes read endpoints. It never calls Agent 07 or Agent 12.
- **Agent 07 is a pure consumer.** It reads `analyst_suggestions` as a pending queue. If the table is empty, no action is taken.
- **Analyst recommendations are investment ideas, not proposals.** They enter the same Agent 07 → Agent 12 scoring pipeline as any user-initiated scan. Agent 07 always has the authoritative score and zone pricing.
- **Learning is cumulative.** Every article enriches the analyst's framework profile. Framework synthesis runs on all historical articles, not just recent ones.
- **Agent 07 enriches suggestions via direct DB join.** When attaching analyst context (name, accuracy, sector alpha) to scored results, Agent 07 joins `analyst_suggestions` with the `analysts` table directly. No runtime call to Agent 02 is made.

---

## 4. Pass 2 — Framework Extraction

### 4.1 Trigger and Failure Handling

Pass 2 runs immediately after Pass 1 for each article that cleared deduplication. It receives:

- The article markdown (same input as Pass 1)
- The Pass 1 signal output (ticker signals, recommendations, overall sentiment)

Passing Pass 1 output as context allows Sonnet to reason about *how* the analyst reached their conclusions, not just what they concluded.

**Pass 2 failure policy:** If Pass 2 fails (timeout, API error, malformed output) for any ticker, the article's Pass 1 signal is preserved in full — existing pipeline behavior is unaffected. However, no `article_framework` row is created for that ticker, and no `analyst_suggestions` row is written. The suggestion is suppressed entirely. Rationale: an unenriched suggestion (no framework context) would degrade Agent 12 commentary quality and cannot be reliably validated. A failed Pass 2 is logged with the article ID and retried on the next Harvester Flow run if the article is still within the dedup window.

### 4.2 Model

**Claude Sonnet** — Haiku lacks the depth to infer implicit methodology signals. Sonnet cost is bounded: Pass 2 only runs on deduplicated articles.

### 4.3 Extraction Schema

Per ticker analyzed in the article, Pass 2 produces an `ArticleFramework`:

```json
{
  "ticker": "ARCC",
  "valuation_metrics_cited": ["FFO_coverage", "NAV_discount", "yield_spread"],
  "thresholds_identified": {
    "NAV_discount": ">15%",
    "FFO_coverage": ">=1.2x",
    "yield_floor": "8.5%"
  },
  "reasoning_structure": "bottom_up",
  "conviction_level": "high",
  "catalysts": ["fed_pause", "portfolio_credit_quality_improving"],
  "price_guidance_type": "implied_yield",
  "price_guidance_value": {
    "type": "yield_floor",
    "value": 0.085,
    "implied_price": 20.50
  },
  "risk_factors_cited": ["rising_default_rates", "rate_sensitivity"],
  "macro_factors": ["credit_cycle_late", "rate_environment_stabilizing"],
  "evaluation_narrative": "Analyst evaluates BDCs primarily through FFO coverage sustainability and NAV discount entry discipline. Bullish when discount exceeds 15% and coverage ratio is above 1.2x with stable credit quality."
}
```

**Field definitions:**

| Field | Type | Description |
| --- | --- | --- |
| `valuation_metrics_cited` | string[] | Canonical metric names extracted from article |
| `thresholds_identified` | JSONB | Specific numeric thresholds the analyst used or implied |
| `reasoning_structure` | enum | `top_down` / `bottom_up` / `catalyst_driven` / `value_driven` |
| `conviction_level` | enum | `high` / `medium` / `low` — inferred from recommendation language strength, qualifier intensity, hedging frequency, and certainty of language (e.g., "I am adding aggressively" vs. "worth watching") |
| `catalysts` | string[] | Forward-looking events that drive the thesis |
| `price_guidance_type` | enum | `explicit_target` / `implied_yield` / `implied_nav` / `none` |
| `price_guidance_value` | JSONB | Analyst's price context — shown alongside Agent 07 zone pricing in proposals |
| `risk_factors_cited` | string[] | Risks the analyst flagged |
| `macro_factors` | string[] | Macro context cited |
| `evaluation_narrative` | text | Sonnet's synthesis of the analyst's reasoning methodology |

**`price_guidance_type` = `none`** signals to Agent 12 that the analyst did not provide price guidance. Agent 07's zone pricing is the sole entry/exit reference in this case. When guidance is present, both are shown side by side in the proposal.

### 4.4 Feature Gap Detection

During Pass 2, any `valuation_metrics_cited` entry that does not match a known name or alias in `feature_registry` is written to `feature_gap_log`. The table has a unique constraint on `(metric_name_raw, asset_class)` — subsequent occurrences increment `occurrence_count` via upsert rather than creating duplicate rows:

```json
{
  "metric_name_raw": "NII payout coverage",
  "canonical_candidate": "NII_coverage",
  "asset_class": "BDC",
  "article_id": 4821,
  "analyst_id": 3,
  "occurrence_count": 1
}
```

The Intelligence Flow's Feature Gap Resolution stage aggregates these and resolves them (see Section 7).

---

## 5. Data Schema

All new tables created in `platform_shared`.

### 5.1 `article_frameworks`

Stores the Pass 2 extraction output per article per ticker.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | serial PK | |
| `article_id` | FK → articles | |
| `analyst_id` | FK → analysts | |
| `ticker` | varchar(20) | |
| `valuation_metrics_cited` | JSONB | string[] |
| `thresholds_identified` | JSONB | {metric: value} |
| `reasoning_structure` | varchar(30) | |
| `conviction_level` | varchar(10) | |
| `catalysts` | JSONB | string[] |
| `price_guidance_type` | varchar(20) | |
| `price_guidance_value` | JSONB | |
| `risk_factors_cited` | JSONB | string[] |
| `macro_factors` | JSONB | string[] |
| `evaluation_narrative` | text | |
| `framework_embedding` | vector(1536) | pgvector — semantic search |
| `extracted_at` | timestamptz | |

### 5.2 `analyst_framework_profiles`

Synthesized per-analyst, per-asset-class mental model. Updated by Intelligence Flow on each run.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | serial PK | |
| `analyst_id` | FK → analysts | |
| `asset_class` | varchar(30) | One row per analyst × asset class |
| `metric_frequency` | JSONB | `{"FFO_coverage": 0.81, "NAV_discount": 0.74}` |
| `typical_thresholds` | JSONB | `{"NAV_discount": {"min": 0.10, "median": 0.15, "max": 0.22}}` |
| `preferred_reasoning_style` | varchar(30) | |
| `conviction_patterns` | JSONB | Language patterns mapped to conviction level |
| `catalyst_sensitivity` | JSONB | Which catalysts this analyst weights |
| `framework_summary` | text | LLM-synthesized narrative |
| `consistency_score` | float | 0–1 — percentage of articles sharing the modal `reasoning_structure` and top-3 `valuation_metrics_cited` for this `(analyst_id, asset_class)` pair |
| `article_count` | int | Articles used for this synthesis |
| `synthesized_at` | timestamptz | |
| `profile_embedding` | vector(1536) | |

Unique constraint: `(analyst_id, asset_class)`. Upserted on each synthesis run.

### 5.3 `analyst_suggestions`

Pending investment ideas sourced from analyst recommendations. Written by Agent 02 Harvester Flow, read by Agent 07. Agent 02 never reads this table at runtime.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | serial PK | |
| `analyst_id` | FK → analysts | |
| `article_framework_id` | FK → article_frameworks | Source framework — never null |
| `ticker` | varchar(20) | |
| `asset_class` | varchar(30) | |
| `recommendation` | varchar(20) | `BUY` / `SELL` |
| `sentiment_score` | float | From Pass 1 |
| `price_guidance_type` | varchar(20) | |
| `price_guidance_value` | JSONB | |
| `staleness_weight` | float | Managed by Intelligence Flow decay — initialized to 1.0 at write |
| `is_active` | boolean | False when staleness_weight < 0.3 OR expires_at passed |
| `sourced_at` | timestamptz | Article publication date |
| `expires_at` | timestamptz | Hard cutoff — set at write time based on asset class |

**Write rule:** A row is created for every `BUY` or `SELL` signal from Pass 1 that has a successfully completed Pass 2 `ArticleFramework`. `HOLD` signals are not written — they carry no investment action. If Pass 2 fails, no suggestion row is written (see Section 4.1).

**Uniqueness and deduplication:** Partial unique index on `(analyst_id, ticker)` WHERE `is_active = true`. If the same analyst publishes a subsequent BUY/SELL on the same ticker while a row is already active, an upsert refreshes `expires_at`, `staleness_weight` (reset to 1.0), `article_framework_id`, `sentiment_score`, and `price_guidance_value`. This ensures Agent 07 always sees the most recent signal, not duplicates.

**Expiry defaults by asset class:**

| Asset Class | Default TTL |
| --- | --- |
| BDC, mREIT, Preferred | 45 days |
| Dividend Stock, REIT | 60 days |
| Bond, CEF | 30 days |

Configurable per analyst via `analysts.config`.

**Aging mechanism — two-layer:**

- **Soft:** `staleness_weight` decayed by Intelligence Flow using the same S-curve already applied to the existing staleness decay sweep (existing behavior — no new formula needed). Agent 07 filters `staleness_weight >= 0.3`.
- **Hard:** `expires_at < NOW()` — row excluded regardless of weight. `is_active` set to false by Intelligence Flow sweep.

**Agent 07 query:**

```sql
SELECT
    s.*,
    a.display_name       AS analyst_name,
    a.overall_accuracy   AS analyst_accuracy,
    a.sector_alpha       AS analyst_sector_alpha
FROM analyst_suggestions s
JOIN analysts a ON a.id = s.analyst_id
WHERE s.is_active = true
  AND s.expires_at > NOW()
  AND s.staleness_weight >= 0.3
ORDER BY s.staleness_weight DESC, s.sourced_at DESC
```

Agent 07 joins `analysts` directly for name and accuracy — no runtime call to Agent 02. If the result is empty, no analyst ideas scan is triggered.

### 5.4 `feature_gap_log`

Metrics identified by Pass 2 that are not in `feature_registry`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | serial PK | |
| `metric_name_raw` | varchar | As extracted from article |
| `canonical_candidate` | varchar | LLM-suggested canonical name |
| `asset_class` | varchar | |
| `article_id` | FK → articles | First occurrence |
| `analyst_id` | FK → analysts | First occurrence |
| `occurrence_count` | int | Incremented on conflict |
| `resolution_status` | varchar | `pending` / `resolved_fetchable` / `resolved_derived` / `resolved_external` / `dismissed` |
| `resolved_at` | timestamptz | |

**Unique constraint:** `(metric_name_raw, asset_class)`. Subsequent occurrences of the same raw metric name for the same asset class increment `occurrence_count` via upsert. `article_id` and `analyst_id` record the first occurrence only.

### 5.5 `feature_registry`

Canonical feature catalog. Drives Agent 01's dynamic feature fetch capability.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | serial PK | |
| `feature_name` | varchar UNIQUE | Canonical name e.g. `NAV_discount` |
| `aliases` | JSONB | Raw analyst language variants that map here |
| `category` | varchar | `fetchable` / `derived` / `external` |
| `source` | varchar | `fmp` / `polygon` / `yfinance` / `derived` / `manual` |
| `asset_classes` | JSONB | Which asset classes this applies to |
| `fetch_config` | JSONB | Category 1: API endpoint + field path + transformation |
| `computation_rule` | text | Category 2: formula using stored fields |
| `is_active` | boolean | False until validation gate passes |
| `validation_status` | varchar | `pending` / `validated` / `failed` |
| `added_at` | timestamptz | |

---

## 6. Intelligence Flow Extensions

Two new stages added after Philosophy Synthesis, before Consensus Rebuild.

### 6.1 Framework Synthesis

Aggregates all `article_frameworks` per analyst per asset class into `analyst_framework_profiles`.

**Steps:**

1. For each `(analyst_id, asset_class)` pair with new `article_frameworks` since last synthesis:
2. Compute `metric_frequency` — for each metric, count occurrences across all articles for this pair divided by total article count
3. Compute `typical_thresholds` — aggregate threshold values per metric: min, median, max across all articles where threshold was identified
4. Derive `preferred_reasoning_style` — modal value of `reasoning_structure` across all articles for this pair
5. Compute `consistency_score` — percentage of articles sharing both the modal `reasoning_structure` and all three of the top-3 most frequent `valuation_metrics_cited`
6. Synthesize `framework_summary` — Sonnet call with all `evaluation_narrative` texts for this pair as context, producing a concise analyst methodology description
7. Upsert `analyst_framework_profiles` (unique on `analyst_id, asset_class`)
8. Update `profile_embedding` via embedding model

### 6.2 Feature Gap Resolution

Processes `feature_gap_log` entries with `resolution_status = pending`.

**Steps per gap entry:**

1. Check `aliases` column in `feature_registry` for a match — if found, link to existing feature and mark `resolved_fetchable`; no new registry entry needed
2. If no match: Haiku (classification task) determines category:
   - **Category 1 (fetchable):** suggests `source` and `fetch_config` for an existing provider; entry written to `feature_registry` with `is_active = false`, `validation_status = pending`
   - **Category 2 (derived):** suggests `computation_rule` using stored fields; entry written with `is_active = false`, `validation_status = pending`
   - **Category 3 (external):** marks `resolution_status = resolved_external`; flags for human review via admin API; no registry entry created
3. **Validation gate (Category 1):** Agent 01 attempts a single live fetch for one symbol using the proposed `fetch_config`. If the result is a plausible numeric value (non-null, within expected range for the metric type), set `is_active = true`, `validation_status = validated`. If the fetch fails or returns implausible data, set `validation_status = failed` and route to human review — do not auto-activate.
4. **Validation gate (Category 2):** DerivedFeatureComputer attempts to evaluate the `computation_rule` against stored data for one symbol. If it returns a non-null numeric result, set `is_active = true`, `validation_status = validated`. Otherwise route to human review.
5. Category 3 and failed validations remain `is_active = false` pending human decision.

### 6.3 Agent 01 Feature Registry Reload

After Intelligence Flow completes and new `feature_registry` entries are activated, Intelligence Flow calls `POST /admin/reload-feature-registry` on Agent 01. Agent 01's hot-reload handler refreshes its in-memory provider feature map without restart. This avoids service downtime and ensures newly validated features are available for the next market data fetch cycle.

---

## 7. Agent 01 — Dynamic Feature Fetch Extension

Agent 01's existing architecture has a clean provider pattern (`BaseDataProvider` ABC → FMP / Polygon / yfinance → `ProviderRouter`) but a fixed contract of 5 hardcoded method types. Adding new feature types currently requires code changes.

### 7.1 Extension

Add one dynamic method to the existing interface:

**`BaseDataProvider`** — new abstract method:

```python
@abstractmethod
async def get_feature(self, symbol: str, feature_name: str) -> float | None:
    """Fetch a named feature for symbol from feature_registry config.
    Returns None if this provider does not support the feature."""
```

**Each concrete provider** implements `get_feature` using a config map loaded from `feature_registry` at startup (and on hot-reload) — Category 1 entries where `source` matches this provider and `is_active = true`. The map translates `feature_name` → API endpoint + field extraction + transformation.

**`ProviderRouter`** — new routing method:

```python
async def get_feature(self, symbol: str, feature_name: str) -> float | None:
    chain = self._build_chain(symbol, "get_feature", ...)
    return await self._try_chain(...)
```

**Hot-reload:** Agent 01 exposes `POST /admin/reload-feature-registry` (internal, not JWT-gated externally). On call, it re-queries `feature_registry` for active Category 1 entries and refreshes each provider's in-memory feature map. No restart required.

**Result:** Category 1 features validated in `feature_registry` become available to all callers of Agent 01 without code changes.

### 7.2 Derived Feature Computation

Category 2 features are computed by a `DerivedFeatureComputer` utility (new, in Agent 01's service layer):

- Reads `computation_rule` from `feature_registry` for active Category 2 entries
- Fetches required source fields from already-stored `features_historical` data
- Evaluates the rule and returns the derived value
- Results stored in `features_historical` under the canonical `feature_name`

---

## 8. Agent 02 — New API Endpoints

Agent 02 exposes two new read endpoints. No new write endpoints — all writes happen inside the Harvester and Intelligence flows.

### `GET /kb/analyst-context`

Returns enriched analyst context for a specific analyst + ticker combination. Consumed by Agent 12 when building proposal commentary.

**Query parameters:**

| Param | Type | Description |
| --- | --- | --- |
| `analyst_id` | int | Required |
| `ticker` | string | Required |
| `asset_class` | string | Optional — narrows framework profile selection |

**Response:**
```json
{
  "analyst": {
    "id": 1,
    "display_name": "John Smith",
    "overall_accuracy": 0.72,
    "sector_alpha": {"BDC": 0.18}
  },
  "framework_profile": {
    "asset_class": "BDC",
    "metric_frequency": {"FFO_coverage": 0.81, "NAV_discount": 0.74},
    "typical_thresholds": {"NAV_discount": {"min": 0.10, "median": 0.15, "max": 0.22}},
    "preferred_reasoning_style": "bottom_up",
    "consistency_score": 0.84,
    "framework_summary": "Evaluates BDCs primarily through FFO coverage sustainability and NAV discount entry discipline. Requires coverage > 1.2x and discount > 15% before initiating positions.",
    "article_count": 23
  },
  "article_framework": {
    "ticker": "ARCC",
    "valuation_metrics_cited": ["FFO_coverage", "NAV_discount"],
    "thresholds_identified": {"NAV_discount": ">15%", "FFO_coverage": ">=1.2x"},
    "conviction_level": "high",
    "price_guidance_type": "implied_yield",
    "price_guidance_value": {"type": "yield_floor", "value": 0.085},
    "evaluation_narrative": "..."
  },
  "signal": {
    "label": "STRONG_BUY",
    "sentiment_score": 0.78,
    "decay_weight": 0.91
  }
}
```

**Errors:**

- 404: No framework profile or signal found for this analyst + ticker combination

### `GET /analysts/{id}/framework`

Returns all synthesized framework profiles for an analyst — one object per asset class covered.

**Path parameters:** `id` — analyst database ID

**Response:**

```json
{
  "analyst_id": 1,
  "display_name": "John Smith",
  "profiles": [
    {
      "asset_class": "BDC",
      "metric_frequency": {"FFO_coverage": 0.81, "NAV_discount": 0.74},
      "typical_thresholds": {"NAV_discount": {"min": 0.10, "median": 0.15, "max": 0.22}},
      "preferred_reasoning_style": "bottom_up",
      "consistency_score": 0.84,
      "framework_summary": "...",
      "article_count": 23,
      "synthesized_at": "2026-03-25T08:00:00Z"
    },
    {
      "asset_class": "DIVIDEND_STOCK",
      "metric_frequency": {"payout_ratio": 0.91, "dividend_cagr_5yr": 0.78},
      "preferred_reasoning_style": "bottom_up",
      "consistency_score": 0.71,
      "framework_summary": "...",
      "article_count": 11,
      "synthesized_at": "2026-03-25T08:00:00Z"
    }
  ]
}
```

**Errors:**

- 404: Analyst not found or no framework profiles synthesized yet

---

## 9. Agent 07 — Analyst Suggestions Integration

Agent 07 requires no new API endpoints. It reads `analyst_suggestions` from `platform_shared` directly via the shared DB connection already used for `scan_results` and `securities`.

### New scan mode: Analyst Ideas

On each scheduled or triggered scan run, Agent 07 queries `analyst_suggestions` (joined with `analysts`) for active, non-expired rows with sufficient staleness weight. If the result is non-empty:

1. Extract ticker list from active suggestions
2. Score via Agent 03 (same path as any other scan)
3. Attach analyst context to each scored result (from the join — no Agent 02 API call):
   - Analyst name + overall accuracy + asset class sector alpha
   - `price_guidance_type` and `price_guidance_value` from the suggestion row
   - Agent 07 zone pricing (always present, authoritative)
4. Persist results to existing `scan_results` table (same mechanism as Opportunity Scan) tagged with `source: "analyst_ideas"`
5. Results surface to user as "Analyst Ideas" in the same scan results UX as Opportunity Scan
6. User selects which to pursue → Agent 12 generates proposal using existing delegation mechanism

If `analyst_suggestions` query returns empty → no analyst ideas scan triggered.

**Both prices always shown in proposal:**

- *Agent 07 zone pricing:* $20.10–$21.40 (authoritative, from score-based valuation)
- *Analyst implied guidance:* $20.50 at 8.5% yield floor (from suggestion row — informational)

---

## 10. Agent 12 — Proposal Commentary Enrichment

Agent 12 is unchanged in its proposal workflow. The enrichment is additive: when processing an analyst-sourced idea (identifiable via `analyst_id` present on the scan result, sourced from `source: "analyst_ideas"` tag), Agent 12 calls `GET /kb/analyst-context` before generating commentary.

**Example proposal commentary:**

> "ARCC — STRONG BUY from John Smith (72% BDC accuracy, bottom-up / FFO-coverage framework, consistency score 0.84). Analyst requires NAV discount > 15% and FFO coverage ≥ 1.2x. Platform score: 84 (above VETO gate). Agent 07 entry zone: $20.10–$21.40. Analyst implied floor: $20.50 at 8.5% yield."

---

## 11. Dependency Map

```text
Agent 02 Harvester Flow (producer)
  → writes: article_frameworks, analyst_suggestions, feature_gap_log

Agent 02 Intelligence Flow (producer)
  → writes: analyst_framework_profiles, feature_registry (activations)
  → calls:  POST /admin/reload-feature-registry on Agent 01

Agent 01 (enhanced)
  → reads:  feature_registry at startup and on hot-reload
  → new:    get_feature() dynamic method + POST /admin/reload-feature-registry
  → writes: features_historical (derived feature values)

Agent 07 (consumer)
  → reads:  analyst_suggestions JOIN analysts (direct DB, no Agent 02 call)
  → scores: via Agent 03 (existing)
  → writes: scan_results tagged source="analyst_ideas"
  → delegates to: Agent 12 (existing mechanism)

Agent 12 (enriched)
  → reads:  scan_results (existing)
  → calls:  GET /kb/analyst-context on Agent 02 (commentary enrichment only)
  → proposal workflow: unchanged
```

---

## 12. Out of Scope

- Expanding beyond Seeking Alpha (other newsletter sources)
- Agent 12 internal proposal workflow changes
- UI design for Analyst Ideas scan results (separate spec — Agent 07 persists to `scan_results` using existing mechanism; UI spec can reference `source = "analyst_ideas"` filter)
- Backtesting analyst framework accuracy against outcomes (future — v3.0 learning loop)
- Premium SA subscription article access (operational concern, not architectural — tracked in Open Questions)

---

## 13. Open Questions

1. **Premium analyst article access:** Some subscribed SA advisory analysts may require premium content fetch. Does the existing APIDojo integration handle premium content, or does this require a separate fetch path? This is operational, not architectural — does not block implementation.
2. **Expiry TTLs:** Default TTLs per asset class are proposed in Section 5.3. Should these be hardcoded config values or admin-configurable via an API endpoint?
3. **Framework synthesis frequency:** Should Framework Synthesis (Section 6.1) run on every Intelligence Flow execution or on a longer cadence (e.g., weekly)? Recommendation: weekly — synthesis is computationally heavier (Sonnet call per analyst × asset class pair) and framework evolution is slow.
4. **Agent 07 analyst ideas trigger:** Should Analyst Ideas be scored automatically at the end of each Harvester Flow run (new suggestions just arrived) or only on user-triggered scans? Recommendation: user-triggered only initially — avoids proposal noise from every harvest run.
