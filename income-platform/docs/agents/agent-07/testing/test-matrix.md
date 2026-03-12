# Agent 07 — Test Matrix

**Total:** 100 tests (all passing)
**Last Run:** 2026-03-12

---

## Test Files

| File | Tests | Coverage |
|---|---|---|
| `test_engine.py` | 40 | Scanner engine: deduplication, ranking, VETO gate, filters, error handling |
| `test_scoring_client.py` | 25 | JWT token generation, HTTP success/error paths |
| `test_api.py` | 35 | All endpoints: auth, validation, response structure, dependency injection |

---

## test_engine.py — 40 tests

### Class TestBasicScan (10 tests)

| Test | What it verifies |
|---|---|
| `test_empty_tickers_returns_zero_result` | Empty input → zero result, no Agent 03 calls |
| `test_single_ticker_scored` | Single ticker → one Agent 03 call |
| `test_none_response_skipped` | Agent 03 returns None → ticker excluded from totals |
| `test_multiple_tickers_all_scored` | 3 tickers → 3 Agent 03 calls |
| `test_duplicate_tickers_deduplicated` | [O, O, JEPI] → only 2 Agent 03 calls |
| `test_tickers_uppercased` | lowercase input → uppercase Agent 03 call |
| `test_items_ranked_by_score_desc` | Items sorted highest score first |
| `test_rank_starts_at_1` | First item rank == 1 |
| `test_all_items_populated` | `all_items` includes all scored (not just passing) |
| `test_score_details_populated` | `score_details` dict present with pillar scores |

### Class TestVetoGate (10 tests)

| Test | What it verifies |
|---|---|
| `test_score_above_70_not_vetoed` | score=75 → veto_flag=False, passed_quality_gate=True |
| `test_score_below_70_vetoed` | score=55 → veto_flag=True, passed_quality_gate=False |
| `test_score_exactly_70_passes_gate` | score=70 → passes (boundary inclusive) |
| `test_total_vetoed_count_correct` | 2 of 3 below 70 → total_vetoed=2 |
| `test_quality_gate_only_excludes_vetoed` | quality_gate_only=True → vetoed not in items |
| `test_quality_gate_false_includes_vetoed` | quality_gate_only=False → vetoed in items with flag |
| `test_all_vetoed_total_passed_zero_when_gate_only` | All below 70 + gate_only → 0 passed |
| `test_vetoed_still_appear_in_all_items` | all_items always includes vetoed |
| `test_score_zero_is_vetoed` | score=0 → vetoed |
| `test_score_100_passes_gate` | score=100 → not vetoed |

### Class TestFilters (10 tests)

| Test | What it verifies |
|---|---|
| `test_min_score_filter_excludes_below` | min_score=75 → only score≥75 in items |
| `test_min_score_zero_passes_all` | min_score=0 → all scores pass |
| `test_min_score_exact_boundary_included` | score=75 with min_score=75 → included |
| `test_asset_class_filter_includes_matching` | Only matching asset_class in items |
| `test_asset_class_none_allows_all` | asset_classes=None → no filter applied |
| `test_asset_class_multiple_allowed` | Multiple allowed classes work |
| `test_combined_min_score_and_gate_only` | Combined filters apply independently |
| `test_total_passed_reflects_filtered_count` | total_passed = len(items after filter) |
| `test_no_match_returns_empty_items` | min_score=99 → 0 passed |
| `test_rank_sequential_after_filter` | Ranks are 1, 2, ... after filtering |

### Class TestErrorHandlingAndConcurrency (10 tests)

| Test | What it verifies |
|---|---|
| `test_partial_failure_still_returns_successes` | 1 of 3 fails → 2 scored |
| `test_all_fail_returns_zero` | All None → 0 scanned, empty items |
| `test_scan_item_ticker_matches_input` | Item ticker = input ticker |
| `test_scan_item_score_is_float` | Score type is float |
| `test_scan_item_grade_is_string` | Grade type is str |
| `test_scan_item_veto_flag_is_bool` | veto_flag type is bool |
| `test_engine_result_is_dataclass` | Result is ScanEngineResult instance |
| `test_signal_penalty_captured` | signal_penalty from Agent 03 preserved |
| `test_chowder_signal_none_allowed` | chowder_signal=None is valid |
| `test_large_batch_deduplicated_correctly` | 100 tickers (50 unique × 2) → 50 scored |

---

## test_scoring_client.py — 25 tests

### Class TestMakeToken (8 tests)

- JWT structure: 3-part format, base64-valid header/payload
- Header: `alg=HS256`, `typ=JWT`
- Payload: `sub=agent-07`, future `exp`
- Verifiable by PyJWT using the same secret

### Class TestScoreTickerSuccess (10 tests)

- 200 response → returns dict
- Posts to `/scores/evaluate`
- Sends ticker in JSON body
- Sends `Authorization: Bearer <token>` header
- Preserves all score fields in return value
- Handles score=0 and score=100
- Returns empty dict (not None) on empty 200 response

### Class TestScoreTickerErrors (7 tests)

- HTTP 500/404/422 → returns None
- `httpx.TimeoutException` → returns None
- `httpx.ConnectError` → returns None
- Generic `Exception` → returns None
- `RuntimeError` → returns None (never raises)

---

## test_api.py — 35 tests

### Class TestHealth (5 tests)

- `GET /health` returns 200
- No auth required for health
- `agent_id: 7` in response
- DB connected/unavailable reflected

### Class TestScanAuth (5 tests)

- No auth → 403
- Invalid token → 401
- Valid token → not 403
- `/universe` no auth → 403
- `/scan/{id}` no auth → 403

### Class TestScanValidation (5 tests)

- Empty tickers → 422
- Missing tickers → 422
- min_score > 100 → 422
- min_score < 0 → 422
- > 200 tickers → 422

### Class TestScanResponse (10 tests)

- Returns 200
- `scan_id` present
- `total_scanned`, `total_passed`, `total_vetoed` present
- `items` is list
- `filters_applied` present
- Item has `ticker`, `veto_flag`, `rank`

### Class TestGetScanAndUniverse (10 tests)

- Nonexistent scan_id → 404
- Invalid UUID → 422
- Valid scan_id → 200 with scan_id echoed
- Universe → 200, `total`, `securities` keys
- Universe with `asset_type` filter → 200
- Universe with `limit` param → 200
