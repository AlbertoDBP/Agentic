# Agent 07 — Opportunity Scanner Service

**Port:** 8007
**Version:** 1.0.0
**Status:** ✅ Live (2026-03-12)
**Tests:** 100 (all passing)

---

## Purpose

Scans a universe of income tickers, scores them via Agent 03, applies yield/quality filters, and returns a ranked candidate list. Intended to feed Agent 08 (Rebalancing) with pre-qualified, pre-ranked candidates.

---

## VETO Gate

Tickers with `total_score < 70` are flagged with `veto_flag: true`. When `quality_gate_only: true` is set in the scan request, vetoed tickers are excluded from results. When `quality_gate_only: false` (default), they appear in results but are clearly flagged — the caller decides.

The threshold `70` matches the VETO gate used across the platform (Agent 03 AGGRESSIVE_BUY/ACCUMULATE boundary).

---

## Architecture

```
POST /scan
  ↓
ScanEngine (engine.py)
  ├── asyncio.Semaphore(10) — max 10 concurrent Agent 03 calls
  ├── score_ticker() — calls Agent 03 POST /scores/evaluate
  ├── Apply filters (min_score, min_yield, asset_classes, quality_gate_only)
  ├── Flag veto_flag = score < 70
  └── Rank passing items by total_score desc
  ↓
Persist to platform_shared.scan_results (JSONB)
  ↓
Return ScanResponse
```

---

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Health check + DB status |
| POST | `/scan` | Bearer | Score tickers, apply filters, return ranked list |
| GET | `/scan/{scan_id}` | Bearer | Retrieve saved scan result |
| GET | `/universe` | Bearer | List securities in `platform_shared.securities` |

---

## Request / Response

### POST /scan

**Request:**
```json
{
  "tickers": ["O", "JEPI", "MAIN", "ARCC"],
  "min_score": 60.0,
  "min_yield": 0.0,
  "asset_classes": null,
  "quality_gate_only": true
}
```

**Response:**
```json
{
  "scan_id": "uuid",
  "total_scanned": 4,
  "total_passed": 3,
  "total_vetoed": 1,
  "items": [
    {
      "ticker": "MAIN",
      "score": 84.5,
      "grade": "A",
      "recommendation": "AGGRESSIVE_BUY",
      "asset_class": "BDC",
      "chowder_signal": "ATTRACTIVE",
      "chowder_number": 12.3,
      "signal_penalty": 0.0,
      "rank": 1,
      "passed_quality_gate": true,
      "veto_flag": false,
      "score_details": {
        "valuation_yield_score": 34.0,
        "financial_durability_score": 36.0,
        "technical_entry_score": 17.5,
        "nav_erosion_penalty": 3.0
      }
    }
  ],
  "filters_applied": {
    "min_score": 60.0,
    "min_yield": 0.0,
    "asset_classes": null,
    "quality_gate_only": true,
    "quality_gate_threshold": 70.0
  },
  "created_at": "2026-03-12T10:00:00+00:00"
}
```

---

## Database

**Table:** `platform_shared.scan_results`

| Column | Type | Description |
|---|---|---|
| id | UUID PK | Scan run identifier |
| total_scanned | INTEGER | Tickers scored (excludes Agent 03 failures) |
| total_passed | INTEGER | Tickers passing all filters |
| total_vetoed | INTEGER | Tickers with score < 70 |
| filters | JSONB | Filter criteria used |
| items | JSONB | Ranked result items (passed filters only) |
| status | TEXT | Always `COMPLETE` |
| created_at | TIMESTAMPTZ | Scan timestamp |

---

## Upstream Dependencies

| Service | Usage | Failure mode |
|---|---|---|
| Agent 03 (Income Scoring, port 8003) | `POST /scores/evaluate` per ticker | Returns `None` → ticker skipped |

Agent 07 never calls Agent 04 or Agent 05 directly. Asset class and tax profile come from Agent 03's score response.

---

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `JWT_SECRET` | — | HS256 signing secret |
| `INCOME_SCORING_URL` | `http://income-scoring-service:8003` | Agent 03 base URL |
| `INCOME_SCORING_TIMEOUT` | `30.0` | Agent 03 request timeout (seconds) |
| `SCAN_CONCURRENCY` | `10` | Max concurrent Agent 03 calls |
| `QUALITY_GATE_THRESHOLD` | `70.0` | VETO gate score floor |
| `MAX_TICKERS_PER_SCAN` | `200` | Hard limit per scan request |
