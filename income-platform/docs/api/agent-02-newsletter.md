# Agent 02: Newsletter Ingestion Service

Manages Seeking Alpha analyst content, extracts income investment signals, maintains analyst accuracy profiles, and produces signals consumed by the Proposal Agent (Agent 12).

**Port:** 8002
**Base URL:** `http://<host>:8002`

## Health Check

### GET /health

Service health check with flow run metadata.

**Auth:** Not required
**Method:** GET

**Response 200:**
```json
{
  "status": "healthy",
  "service": "agent-02-newsletter-ingestion",
  "version": "0.1.0",
  "environment": "production",
  "database": {
    "status": "healthy",
    "pgvector_installed": true,
    "schema_exists": true
  },
  "cache": {
    "status": "healthy",
    "version": "7.0.0"
  },
  "harvester_flow": {
    "last_run": "2026-03-12T08:00:00Z",
    "last_run_status": "success",
    "next_scheduled": "2026-03-12T09:00:00Z",
    "articles_processed_last_run": 47
  },
  "intelligence_flow": {
    "last_run": "2026-03-12T08:30:00Z",
    "last_run_status": "success",
    "next_scheduled": "2026-03-12T09:30:00Z",
    "articles_processed_last_run": null
  },
  "uptime_seconds": 34821.5,
  "timestamp": "2026-03-12T09:59:35Z"
}
```

---

## Flow Triggers

### POST /flows/harvester/trigger

Trigger the Harvester Flow asynchronously to ingest articles from Seeking Alpha.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "analyst_ids": [1, 2, 5]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| analyst_ids | array[int] | No | Specific analyst DB IDs to harvest; null = all active analysts |

**Response 200:**
```json
{
  "triggered": true,
  "message": "Harvester triggered for analysts [1, 2, 5]"
}
```

Returns immediately; the flow runs in the background.

---

### POST /flows/intelligence/trigger

Trigger the Intelligence Flow asynchronously for analyst accuracy retraining.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "analyst_ids": [1, 2, 5]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| analyst_ids | array[int] | No | Specific analyst DB IDs; null = all active analysts |

**Response 200:**
```json
{
  "triggered": true,
  "flow_name": "intelligence_flow",
  "message": "Intelligence flow triggered for analysts [1, 2, 5]"
}
```

Intelligence flow pipeline per analyst:
1. Staleness decay sweep (S-curve weighting)
2. FMP accuracy backtest (T+30, T+90)
3. Philosophy synthesis (LLM or K-Means clustering)
4. Weighted consensus rebuild

---

### GET /flows/status

Retrieve last run metadata for all registered flows.

**Auth:** Not required
**Method:** GET

**Response 200:**
```json
[
  {
    "flow_name": "harvester_flow",
    "last_run_at": "2026-03-12T08:00:00Z",
    "last_run_status": "success",
    "next_scheduled_at": "2026-03-12T09:00:00Z",
    "articles_processed": 47,
    "duration_seconds": 120
  },
  {
    "flow_name": "intelligence_flow",
    "last_run_at": "2026-03-12T08:30:00Z",
    "last_run_status": "success",
    "next_scheduled_at": "2026-03-12T09:30:00Z",
    "articles_processed": null,
    "duration_seconds": 180
  }
]
```

---

## Analysts

### GET /analysts

List all analysts in the registry.

**Auth:** Required
**Method:** GET

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| active_only | boolean | true | Include only active analysts |

**Response 200:**
```json
{
  "analysts": [
    {
      "id": 1,
      "display_name": "John Smith",
      "sa_publishing_id": "john-smith-123",
      "is_active": true,
      "overall_accuracy": 0.68,
      "philosophy_summary": "Value-focused dividend investor",
      "philosophy_source": "llm",
      "sector_alpha": {"Healthcare": 0.15, "Technology": -0.08}
    }
  ],
  "total": 1
}
```

---

### POST /analysts

Add a new analyst by Seeking Alpha author ID.

**Auth:** Required
**Method:** POST

**Request body:**
```json
{
  "sa_publishing_id": "new-author-456",
  "display_name": "Jane Doe",
  "config": {"preferred_sectors": ["Energy", "Utilities"]}
}
```

**Response 201:**
```json
{
  "id": 2,
  "display_name": "Jane Doe",
  "sa_publishing_id": "new-author-456",
  "is_active": true,
  "config": {"preferred_sectors": ["Energy", "Utilities"]}
}
```

**Errors:**
- 409: Analyst with this SA ID already exists

---

### GET /analysts/{id}

Retrieve a single analyst profile with accuracy stats and philosophy summary.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| id | integer | Analyst database ID |

**Response 200:**
```json
{
  "id": 1,
  "display_name": "John Smith",
  "sa_publishing_id": "john-smith-123",
  "is_active": true,
  "overall_accuracy": 0.68,
  "philosophy_summary": "Value-focused dividend investor",
  "philosophy_source": "llm",
  "sector_alpha": {"Healthcare": 0.15, "Technology": -0.08},
  "philosophy_tags": ["value", "dividend", "conservative"]
}
```

**Errors:**
- 404: Analyst not found

---

### GET /analysts/{id}/recommendations

Retrieve all recommendations by a specific analyst.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| id | integer | Analyst database ID |

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| active_only | boolean | true | Exclude superseded recommendations |
| limit | integer | 50 | Max results to return (max 100) |

**Response 200:**
```json
{
  "analyst_id": 1,
  "analyst_name": "John Smith",
  "total": 15,
  "recommendations": [
    {
      "id": 101,
      "ticker": "JNJ",
      "asset_class": "DIVIDEND_STOCK",
      "sector": "Healthcare",
      "sentiment_score": 0.75,
      "label": "STRONG_BUY",
      "published_at": "2026-03-10T14:30:00Z",
      "yield_at_publish": 2.85,
      "payout_ratio": 0.62,
      "safety_grade": "A",
      "decay_weight": 0.92,
      "is_active": true
    }
  ]
}
```

---

### PATCH /analysts/{id}/deactivate

Deactivate an analyst — stops future harvesting for this analyst.

**Auth:** Required
**Method:** PATCH

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| id | integer | Analyst database ID |

**Response 200:**
```json
{
  "analyst_id": 1,
  "is_active": false,
  "message": "Analyst deactivated"
}
```

**Errors:**
- 404: Analyst not found

---

## Recommendations

### GET /recommendations/{ticker}

Retrieve all analyst recommendations for a given ticker, ordered by signal strength.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol (case-insensitive) |

**Query parameters:**
| Param | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| active_only | boolean | true | - | Exclude superseded recommendations |
| min_decay_weight | float | 0.1 | 0.0-1.0 | Minimum signal strength threshold |
| limit | integer | 20 | 1-100 | Max results to return |

**Response 200:**
```json
{
  "ticker": "JNJ",
  "total": 3,
  "recommendations": [
    {
      "id": 101,
      "analyst_id": 1,
      "analyst_name": "John Smith",
      "sentiment_score": 0.75,
      "label": "STRONG_BUY",
      "published_at": "2026-03-10T14:30:00Z",
      "yield_at_publish": 2.85,
      "payout_ratio": 0.62,
      "safety_grade": "A",
      "decay_weight": 0.92
    }
  ]
}
```

Results are ordered by `decay_weight` descending (freshest, highest-weighted signals first).

**Errors:**
- 404: No recommendations found for ticker

---

## Consensus

### GET /consensus/{ticker}

Retrieve weighted consensus score for a ticker across all active analysts.

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol (case-insensitive) |

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| force_refresh | boolean | false | Bypass Redis cache and recompute |

**Response 200:**
```json
{
  "ticker": "JNJ",
  "score": 0.65,
  "confidence": "high",
  "n_analysts": 3,
  "n_recommendations": 5,
  "dominant_recommendation": "BUY",
  "computed_at": "2026-03-12T09:59:35Z"
}
```

| Field | Description |
|-------|-------------|
| score | Range -1.0 (strong sell) to 1.0 (strong buy) |
| confidence | `high` (≥3 analysts), `low` (<3), or `insufficient_data` |
| dominant_recommendation | Mapped from score: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL |

Consensus is weighted by: `analyst_accuracy × decay_weight × user_weight (default 1.0)`

Cached for 30 minutes. Use `force_refresh=true` to bypass cache.

**Errors:**
- 404: No active recommendations found for ticker

---

## Analyst Signal

### GET /signal/{ticker}

Retrieve complete analyst signal for a ticker — consumed by Agent 12 (Proposal Agent).

**Auth:** Required
**Method:** GET

**Path parameters:**
| Param | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol (case-insensitive) |

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| force_refresh | boolean | false | Bypass cache and recompute |

**Response 200:**
```json
{
  "ticker": "JNJ",
  "asset_class": "DIVIDEND_STOCK",
  "sector": "Healthcare",
  "signal_strength": "strong",
  "proposal_readiness": true,
  "analyst": {
    "id": 1,
    "display_name": "John Smith",
    "accuracy_overall": 0.68,
    "sector_alpha": {"Healthcare": 0.15, "Technology": -0.08},
    "philosophy_summary": "Value-focused dividend investor",
    "philosophy_source": "llm",
    "philosophy_tags": ["value", "dividend", "conservative"]
  },
  "recommendation": {
    "id": 101,
    "label": "STRONG_BUY",
    "sentiment_score": 0.75,
    "yield_at_publish": 2.85,
    "payout_ratio": 0.62,
    "safety_grade": "A",
    "source_reliability": 0.85,
    "thesis_summary": "Strong dividend yield with predictable growth",
    "bull_case": "Stable cash flow, market leadership, consistent growth",
    "bear_case": "Valuation premium relative to sector peers",
    "published_at": "2026-03-10T14:30:00Z",
    "decay_weight": 0.92
  },
  "consensus": {
    "score": 0.65,
    "confidence": "high",
    "n_analysts": 3,
    "n_recommendations": 5,
    "dominant_recommendation": "BUY"
  },
  "platform_alignment": 0.88,
  "generated_at": "2026-03-12T09:59:35Z"
}
```

**Signal strength:** strong | moderate | weak | insufficient
- **Strong:** ≥2 analysts, decay_weight ≥0.7, accuracy ≥0.65
- **Moderate:** ≥1 analyst, decay_weight ≥0.4
- **Weak:** ≥1 analyst, decay_weight <0.4
- **Insufficient:** No qualifying recommendations

**Proposal readiness:** true when signal_strength is "strong" or "moderate" AND analyst accuracy meets minimum threshold (default 0.55)

Cached for 1 hour. Use `force_refresh=true` to bypass cache.

**Errors:**
- 404: No active recommendations found for ticker
