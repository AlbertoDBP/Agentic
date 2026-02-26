# Test Matrix — Agent 02 + Agent 12

**Last Updated:** 2026-02-25

---

## Agent 02 Test Coverage

### Phase 1 — Foundation (`test_phase1_foundation.py`)

| Test | Component | Status |
|---|---|---|
| Root endpoint returns 200 | main.py | ✅ |
| Health endpoint returns 200 | health.py | ✅ |
| Health status field present | health.py | ✅ |
| Health degraded on DB unavailable | health.py | ✅ |
| Health unhealthy on both unavailable | health.py | ✅ |
| Analyst model imports | models.py | ✅ |
| AnalystArticle model imports | models.py | ✅ |
| AnalystRecommendation model imports | models.py | ✅ |
| AnalystAccuracyLog model imports | models.py | ✅ |
| CreditOverride model imports | models.py | ✅ |
| Config loads from env | config.py | ✅ |
| Config has required fields | config.py | ✅ |
| AnalystSignalResponse schema imports | schemas.py | ✅ |

### Phase 2 — Harvester (`test_phase2_harvester.py`)

| Test | Component | Status |
|---|---|---|
| Content hash deterministic | deduplicator | ✅ |
| Content hash differs for different text | deduplicator | ✅ |
| URL hash produces 64-char hex | deduplicator | ✅ |
| is_duplicate_by_sa_id true when exists | deduplicator | ✅ |
| is_duplicate_by_sa_id false when missing | deduplicator | ✅ |
| filter_new_articles removes duplicates | deduplicator | ✅ |
| html_to_markdown converts headers | extractor | ✅ |
| html_to_markdown strips scripts | extractor | ✅ |
| html_to_markdown empty returns empty | extractor | ✅ |
| truncate does not truncate short text | extractor | ✅ |
| truncate appends marker | extractor | ✅ |
| validate_extracted_ticker clamps sentiment | extractor | ✅ |
| validate_extracted_ticker normalizes ticker | extractor | ✅ |
| validate_extracted_ticker handles None fields | extractor | ✅ |
| extract_signals parses valid JSON | extractor | ✅ |
| extract_signals returns None on invalid JSON | extractor | ✅ |
| embed_text returns list of floats | vectorizer | ✅ |
| embed_text returns None on empty input | vectorizer | ✅ |
| build_recommendation_thesis combines fields | vectorizer | ✅ |
| embed_batch returns correct count | vectorizer | ✅ |
| save_article creates ORM object | article_store | ✅ |
| save_article computes content hash | article_store | ✅ |
| save_recommendation sets is_active=True | article_store | ✅ |
| trigger_harvester returns 200 | flows.py API | ✅ |
| trigger_harvester with analyst_ids | flows.py API | ✅ |
| trigger_intelligence returns 501 (pre-Phase 3) | flows.py API | ✅ |
| flow_status endpoint exists | flows.py API | ✅ |
| _normalize_article extracts from attributes | seeking_alpha | ✅ |
| _normalize_article handles missing attributes | seeking_alpha | ✅ |
| fetch_articles uses correct endpoint | seeking_alpha | ✅ |
| fetch_article_detail extracts content | seeking_alpha | ✅ |
| fetch_article_detail returns None on empty | seeking_alpha | ✅ |
| parse_published_at handles offset timezone | seeking_alpha | ✅ |
| harvester uses normalized published_date | seeking_alpha | ✅ |

### Phase 4 — API Layer (`test_phase4_api.py`)

| Test | Component | Status |
|---|---|---|
| list_analysts returns 200 | analysts.py | ✅ |
| list_analysts returns total | analysts.py | ✅ |
| add_analyst returns 201 | analysts.py | ✅ |
| add_analyst returns 409 on duplicate | analysts.py | ✅ |
| get_analyst returns 404 when not found | analysts.py | ✅ |
| get_recommendations returns 200 | recommendations.py | ✅ |
| get_recommendations normalizes ticker | recommendations.py | ✅ |
| get_recommendations returns 404 when none | recommendations.py | ✅ |
| get_consensus returns 200 | consensus.py | ✅ |
| get_consensus dominant_recommendation Buy | consensus.py | ✅ |
| get_consensus returns 404 when no recs | consensus.py | ✅ |
| get_signal returns 200 | signal.py | ✅ |
| get_signal has all required Agent 12 fields | signal.py | ✅ |
| get_signal proposal_readiness False when weak | signal.py | ✅ |
| get_signal returns 404 when no recs | signal.py | ✅ |
| signal_strength computation logic | signal.py | ✅ |
| proposal_readiness computation logic | signal.py | ✅ |
| sentiment_to_label mapping all ranges | signal.py | ✅ |

### Phase 5 — Integration (`test_phase5_integration.py`)

| Test | Requires | Status |
|---|---|---|
| health returns 200 | live service | ⚡ Skip if down |
| health status not unhealthy | live service | ⚡ Skip if down |
| health has required fields | live service | ⚡ Skip if down |
| health timestamp is recent | live service | ⚡ Skip if down |
| docs available | live service | ⚡ Skip if down |
| openapi schema available | live service | ⚡ Skip if down |
| openapi has all phase4 routes | live service | ⚡ Skip if down |
| list_analysts returns 200 | live service | ⚡ Skip if down |
| list_analysts response shape | live service | ⚡ Skip if down |
| seeded analysts present (96726, 104956) | live service + seed | ⚡ Skip if down |
| add duplicate analyst returns 409 | live service | ⚡ Skip if down |
| get nonexistent analyst returns 404 | live service | ⚡ Skip if down |
| harvester trigger returns 200 | live service | ⚡ Skip if down |
| harvester trigger with analyst_ids | live service | ⚡ Skip if down |
| intelligence trigger returns 200 | live service | ⚡ Skip if down |
| flow_status returns 200 | live service | ⚡ Skip if down |
| signal unknown ticker returns 404 | live service | ⚡ Skip if down |
| signal ticker normalized to uppercase | live service | ⚡ Skip if down |
| consensus unknown ticker returns 404 | live service | ⚡ Skip if down |
| recommendations unknown ticker returns 404 | live service | ⚡ Skip if down |

---

## Test Execution

```bash
# Unit tests only (no live service required)
pytest tests/ -v --ignore=tests/test_phase5_integration.py

# Integration tests (requires docker compose up)
pytest tests/test_phase5_integration.py -v

# Integration tests — fail if service not running (CI mode)
pytest tests/test_phase5_integration.py -v --live

# Coverage report
pytest tests/ --ignore=tests/test_phase5_integration.py \
  --cov=app --cov-report=term-missing
```

---

## Coverage Targets

| Module | Target | Notes |
|---|---|---|
| app/api/ | ≥ 85% | Covered by Phase 4 tests |
| app/processors/ | ≥ 85% | Covered by Phase 2 tests |
| app/clients/ | ≥ 80% | SA client shape tests added |
| app/flows/ | ≥ 70% | Flow logic tested via mocks |
| app/models/ | ≥ 95% | Import tests + schema validation |
