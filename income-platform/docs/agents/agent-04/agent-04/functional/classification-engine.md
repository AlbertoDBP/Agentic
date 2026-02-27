# Functional Spec — Classification Engine

**Agent:** 04 — Asset Classification Service  
**Component:** Classification Engine + API  
**Last Updated:** 2026-02-27  
**Status:** ✅ Production

---

## Purpose & Scope

Orchestrates the full classification pipeline for a given ticker: override check → cache → rule detection → optional enrichment → benchmarks → tax profile → persistence. Exposes results via REST API consumed by Agent 03 and Agent 05.

---

## Responsibilities

- Accept ticker classification requests (single and batch)
- Check manual overrides (confidence=1.0, bypass all rules)
- Serve cached classifications within 24hr TTL
- Invoke shared `AssetClassDetector` for rule-based classification
- Trigger Agent 01 enrichment when confidence < 0.70
- Attach class-specific benchmarks and tax efficiency profile
- Persist results to `platform_shared.asset_classifications`
- Manage classification rules via DB (no redeploy required)
- Manage manual overrides via API

---

## Classification Pipeline

### Step 1 — Override Check
- Query `classification_overrides` for active override on ticker
- Active = `effective_from <= now AND (effective_until IS NULL OR effective_until > now)`
- If found: confidence=1.0, source="override", skip all rules
- Overrides never expire from cache (valid_until=NULL)

### Step 2 — Cache Check
- Query `asset_classifications` for record where `valid_until > now`
- Cache TTL: 24 hours
- If hit: return directly, no recomputation

### Step 3 — Rule Detection
- Load active rules from `asset_class_rules` (falls back to seed rules if DB unavailable)
- Invoke `AssetClassDetector.detect(ticker, security_data)`
- Returns: asset_class, confidence, characteristics, matched_rules

### Step 4 — Enrichment (conditional)
- Triggered when `confidence < 0.70`
- Calls Agent 01: `GET /stocks/{ticker}/fundamentals` + `GET /stocks/{ticker}/etf`
- Merges enriched data with original security_data
- Re-runs detection on merged data
- Graceful degradation: returns original result if Agent 01 unavailable

### Step 5 — Benchmarks
- Looks up class-specific `BenchmarkProfile` from `benchmarks.py`
- Provides: peer_group, yield_benchmark_pct, expense_ratio_benchmark_pct, nav_stability_benchmark, pe_benchmark, debt_equity_benchmark, payout_ratio_benchmark

### Step 6 — Tax Profile
- Builds `tax_efficiency` dict from `tax_profile.py`
- Fields: income_type, tax_treatment, estimated_tax_drag_pct, preferred_account, notes
- Always populated regardless of VETO or score (0% composite weight)
- Florida-specific: no state tax calculations

### Step 7 — Persist
- Insert new record into `asset_classifications`
- Set `valid_until = now + 24h`
- Commit and return serialized result

---

## API Contracts

### POST /classify
```
Request:
  ticker: str (required)
  security_data: dict (optional — enrichment hints)

Response:
  ticker, asset_class, parent_class, confidence, is_hybrid,
  characteristics, benchmarks, sub_scores, tax_efficiency,
  source, is_override, classified_at, valid_until
```

### POST /classify/batch
```
Request:
  tickers: List[str] (max 100)
  security_data: dict (optional, applied to all)

Response:
  total, classified, errors, results[], error_details[]
```

### GET /classify/{ticker}
Returns latest classification. Runs fresh classification if not cached.

### GET /rules
Returns all active classification rules ordered by priority.

### POST /rules
Adds new rule. Takes effect immediately — no redeploy.
Fields: asset_class, rule_type, rule_config, priority, confidence_weight

### PUT /overrides/{ticker}
Sets manual override. Replaces existing override for same ticker.
Fields: asset_class, reason, created_by

### DELETE /overrides/{ticker}
Removes override. Ticker will be reclassified by rules on next request.

---

## Non-Functional Requirements

| Requirement | Target |
|---|---|
| Cache hit latency | < 50ms |
| Cache miss latency | < 500ms (without enrichment) |
| Enrichment latency | < 1500ms (Agent 01 call included) |
| Batch throughput | 100 tickers < 30s |
| Cache TTL | 24 hours |
| Availability | Graceful degradation if Agent 01 unavailable |

---

## Dependencies

| Dependency | Type | Required |
|---|---|---|
| PostgreSQL `platform_shared` | DB | Yes |
| `src/shared/asset_class_detector` | Internal | Yes (fallback to seed rules) |
| Agent 01 port 8001 | HTTP | No (enrichment only) |
