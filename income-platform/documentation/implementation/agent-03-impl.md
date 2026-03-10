# Implementation Specification — Agent 03: Income Scoring Service v1.1.0

**Version:** 1.1.0
**Date:** 2026-03-09
**Status:** Built — 17/17 chowder tests passing — Ready for deployment

---

## File Structure

```
src/income-scoring-service/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── api/
│   │   ├── health.py
│   │   ├── scores.py          ← MODIFIED v1.1.0
│   │   └── quality_gate.py
│   └── scoring/
│       ├── data_client.py     ← MODIFIED v1.1.0
│       ├── income_scorer.py   ← MODIFIED v1.1.0
│       ├── nav_erosion.py
│       └── quality_gate.py
├── requirements.txt           ← +asyncpg==0.30.0
└── tests/
    ├── test_chowder.py        ← NEW (17 tests)
    ├── test_income_scorer.py  ← UPDATED
    └── ...existing tests
```

---

## Modified File Details

### `requirements.txt`
```
asyncpg==0.30.0    # added for direct features_historical read
```

### `app/scoring/data_client.py` — `get_features()`

```python
async def get_features(self, ticker: str) -> dict:
    """Read latest features_historical row for ticker via asyncpg.
    
    Returns dict with keys:
        yield_trailing_12m, div_cagr_5y, chowder_number,
        yield_5yr_avg, credit_rating, credit_quality_proxy
    Returns {} on any error — never raises.
    """
    try:
        url = settings.database_url
        if "?sslmode=require" in url:
            url = url.split("?sslmode=require")[0]
        conn = await asyncpg.connect(url, ssl="require")
        row = await conn.fetchrow("""
            SELECT yield_trailing_12m, div_cagr_5y, chowder_number,
                   yield_5yr_avg, credit_rating, credit_quality_proxy
            FROM platform_shared.features_historical
            WHERE symbol = $1
            ORDER BY as_of_date DESC
            LIMIT 1
        """, ticker.upper())
        await conn.close()
        return dict(row) if row else {}
    except Exception as e:
        logger.warning(f"get_features({ticker}) failed: {e}")
        return {}
```

### `app/api/scores.py` — `_fetch_market_data()`

```python
tasks: dict[str, object] = {
    "fundamentals":     _client.get_fundamentals(ticker),
    "dividend_history": _client.get_dividend_history(ticker),
    "history_stats":    _client.get_history_stats(ticker, start_date, end_date),
    "current_price":    _client.get_current_price(ticker),
    "features":         _client.get_features(ticker),   # NEW
}
```

### `app/scoring/income_scorer.py` — chowder additions

```python
# Module-level constants
CHOWDER_THRESHOLDS = {
    "DIVIDEND_STOCK":   {"attractive": 12.0, "floor": 8.0},
    "COVERED_CALL_ETF": {"attractive": 8.0,  "floor": 5.0},
    "BOND":             {"attractive": 8.0,  "floor": 5.0},
}

# Shared signal helper (used by both compute paths)
def _chowder_signal_from_number(chowder: float, asset_class: str) -> str:
    t = CHOWDER_THRESHOLDS.get(
        asset_class.upper(), CHOWDER_THRESHOLDS["DIVIDEND_STOCK"]
    )
    if chowder >= t["attractive"]: return "ATTRACTIVE"
    if chowder >= t["floor"]:      return "BORDERLINE"
    return "UNATTRACTIVE"

# Compute helper
def _compute_chowder(
    yield_ttm: Optional[float],
    div_cagr_5y: Optional[float],
    asset_class: str,
) -> tuple[Optional[float], Optional[str]]:
    if yield_ttm is None or div_cagr_5y is None:
        return None, "INSUFFICIENT_DATA"
    chowder = round(yield_ttm + div_cagr_5y, 4)
    return chowder, _chowder_signal_from_number(chowder, asset_class)

# In score() — chowder attachment
features = market_data.get("features", {})
yield_ttm = features.get("yield_trailing_12m")
div_cagr5 = features.get("div_cagr_5y")

if features.get("chowder_number") is not None and yield_ttm is None:
    # Use pre-computed value from features_historical
    chowder_number = float(features["chowder_number"])
    chowder_signal = _chowder_signal_from_number(chowder_number, asset_class)
else:
    chowder_number, chowder_signal = _compute_chowder(yield_ttm, div_cagr5, asset_class)

result.chowder_number = chowder_number
result.chowder_signal = chowder_signal
result.factor_details["chowder_number"] = chowder_number
result.factor_details["chowder_signal"] = chowder_signal
```

---

## Testing

### Test Results
- `tests/test_chowder.py` — **17/17 passing**
- Pre-existing failures in `test_quality_gate.py` — unrelated to this update

### Test Coverage

| Test | Description |
|------|-------------|
| ATTRACTIVE threshold (DGI ≥12) | chowder_number=14.2 → ATTRACTIVE |
| BORDERLINE threshold (DGI 8–12) | chowder_number=10.0 → BORDERLINE |
| UNATTRACTIVE (DGI <8) | chowder_number=6.0 → UNATTRACTIVE |
| ATTRACTIVE ETF (≥8) | chowder_number=9.0, ETF → ATTRACTIVE |
| BORDERLINE ETF (5–8) | chowder_number=6.5, ETF → BORDERLINE |
| yield_ttm None | → (None, INSUFFICIENT_DATA) |
| div_cagr_5y None | → (None, INSUFFICIENT_DATA) |
| Both None | → (None, INSUFFICIENT_DATA) |
| Exact boundary 12.0 | → ATTRACTIVE |
| Exact boundary 8.0 (DGI) | → BORDERLINE |
| ScoreResponse accepts optional fields | chowder_number=None accepted |
| factor_details contains chowder after scoring | keys present |
| get_features swallows DB error | returns {} |
| get_features maps DB row correctly | keys match |
| score() uses pre-computed chowder_number | fallback path works |

### Acceptance Criteria (Testable)

- [ ] `POST /scores/evaluate` for JEPI returns `chowder_number` and `chowder_signal`
- [ ] `chowder_signal` = ATTRACTIVE/BORDERLINE/UNATTRACTIVE (not INSUFFICIENT_DATA)
      after Agent 01 `/sync` has been run for the ticker
- [ ] `total_score` unchanged before and after Amendment A2 for same inputs
- [ ] `factor_details` contains `chowder_number` and `chowder_signal` keys
- [ ] 17 chowder unit tests pass

---

## Deployment

```bash
# Push from Mac
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform
git add src/income-scoring-service/
git commit -m "feat(agent-03): v1.1.0 - Amendment A2 Chowder Number signal"
git push origin main

# On server
cd /opt/Agentic/income-platform
git pull origin main
docker compose build --no-cache income-scoring-service
docker compose up -d income-scoring-service
```

### Smoke test
```bash
# First ensure JEPI is synced
curl -X POST https://legatoinvest.com/api/market-data/stocks/JEPI/sync

# Then score
curl -X POST https://legatoinvest.com/api/nav-erosion/scores/evaluate \
  -H "Content-Type: application/json" \
  -d '{"ticker": "JEPI", "asset_class": "COVERED_CALL_ETF"}'
# Expect: chowder_number and chowder_signal in response
```

---

## Implementation Notes

- `get_features()` opens a new asyncpg connection per call — acceptable for
  current load; connection pooling can be added in v2 if latency becomes an issue
- `factor_details` is JSONB — chowder keys absorbed without schema migration
- ADR-P11 filed for sector-aware threshold refinement before Agent 12 design
- Pre-existing test failures in `test_quality_gate.py` are unrelated to this
  update and were present before Amendment A2
