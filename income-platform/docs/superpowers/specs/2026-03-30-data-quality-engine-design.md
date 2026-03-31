# Data Quality Engine — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## 1. Problem

The platform accepts incomplete market data silently. Critical fields are missing for specific tickers while peers of the same asset class have them — a condition that must be treated as a system failure, not a graceful degradation. Scoring runs on whatever data is available, producing unreliable scores without warning. Users have no visibility into data freshness or completeness, which erodes trust.

---

## 2. Goals

1. Define what fields are required per asset class and enforce completeness automatically.
2. Self-heal missing fields by re-fetching from FMP (primary) or MASSIVE/Polygon (fallback).
3. Gate scoring so it never runs on incomplete data — if critical gaps remain unresolved, scoring is blocked and an alert is fired.
4. Surface data freshness and completeness status to users (portfolio page) and admins (data quality page).
5. Support dynamic field requirements promoted from analyst feature_gap_log without code deploys.

---

## 3. Architecture

A new containerised service `agent-14-data-quality` sits downstream of the market-data-service. It never fetches primary market data — it only validates what other services wrote and heals gaps.

```
market-data-service ──writes──▶ market_data_cache
                                       │
                      (triggers scan after refresh)
                                       ▼
              agent-14-data-quality ──scans──▶ data_quality_issues
                       │                              │
                       ├── FMP client (primary)       │
                       └── MASSIVE client (fallback)  ▼
                                  │         data_quality_gate
                                  │ fills            │
                                  ▼                  ▼
                         market_data_cache    income-scoring-service
                                             (checks gate before running)
```

**Schedules (via existing Prefect scheduler):**
- After every market-data-service refresh → completeness scan for all tracked symbols
- Every 15 minutes → retry loop for open issues (max 3 attempts per issue)
- Nightly → analyst feature promotion from feature_gap_log

---

## 4. Database Tables

All tables in `platform_shared`.

### 4.1 `field_requirements`

Defines what fields are required per asset class. Populated from seed data and analyst promotions.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `asset_class` | TEXT NOT NULL | `CommonStock \| ETF \| CEF \| BDC \| REIT \| MLP \| Preferred` |
| `field_name` | TEXT NOT NULL | Column name in `market_data_cache` |
| `required` | BOOLEAN NOT NULL DEFAULT TRUE | FALSE = optional (warning only, never blocks gate) |
| `fetch_source_primary` | TEXT NOT NULL | `fmp \| massive` |
| `fetch_source_fallback` | TEXT | `fmp \| massive \| null` (null = no fallback) |
| `source` | TEXT NOT NULL DEFAULT 'core' | `core \| analyst_promoted` |
| `promoted_from_gap_id` | INTEGER | FK → `feature_gap_log.id` (analyst promotions only) |
| `source_endpoint` | TEXT | e.g. `fmp:/etf-info`, `massive:/v2/snapshot` |
| `description` | TEXT | Human-readable rationale |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

**Unique constraint:** `(asset_class, field_name)`

**Seed data — required fields per asset class:**

| Field | CommonStock | ETF | CEF | BDC | REIT | MLP | Preferred |
|---|---|---|---|---|---|---|---|
| `price` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `week52_high` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `week52_low` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `dividend_yield` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `div_frequency` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `sma_50` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `sma_200` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `rsi_14d` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `payout_ratio` | ✓ | — | — | — | ✓ | — | — |
| `chowder_number` | ✓ | — | — | — | — | — | — |
| `consecutive_growth_yrs` | ✓ | — | — | — | — | — | — |
| `nav_value` | — | ✓ | ✓ | ✓ | — | — | — |
| `nav_discount_pct` | — | ✓ | ✓ | — | — | — | — |
| `coverage_ratio` | — | — | ✓ | ✓ | — | ✓ | — |
| `leverage_pct` | — | — | ✓ | ✓ | — | ✓ | — |

**Fetch source priority:**

| Field(s) | Primary | Fallback |
|---|---|---|
| `price`, `week52_*`, `sma_*`, `rsi_14d` | MASSIVE | FMP |
| `dividend_yield`, `div_frequency`, `payout_ratio`, `chowder_number` | FMP `/dividends` | MASSIVE |
| `nav_value`, `nav_discount_pct` | FMP `/etf-info` | none |
| `coverage_ratio`, `leverage_pct` | FMP `/ratios` | MASSIVE financials |
| `consecutive_growth_yrs` | FMP `/dividends-history` | none |

---

### 4.2 `data_quality_issues`

Live tracker — one row per open or recently-resolved issue.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `symbol` | TEXT NOT NULL | Affected ticker |
| `field_name` | TEXT NOT NULL | Which field is missing |
| `asset_class` | TEXT NOT NULL | For peer comparison |
| `status` | TEXT NOT NULL | `missing \| fetching \| resolved \| unresolvable` |
| `severity` | TEXT NOT NULL | `warning \| critical` |
| `attempt_count` | INTEGER NOT NULL DEFAULT 0 | Max 3 before → unresolvable |
| `last_attempted_at` | TIMESTAMPTZ | |
| `resolved_at` | TIMESTAMPTZ | Set on resolution |
| `source_used` | TEXT | `fmp \| massive` — which source resolved it |
| `diagnostic` | JSONB | See §5.2 |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

**Severity rule:**
- `critical` — field is required for this asset class AND at least one peer ticker of the same class has it populated → **blocks the quality gate**
- `warning` — field is required but no peer has it either (data doesn't exist yet in any source) → does not block gate

---

### 4.3 `data_quality_gate`

One row per portfolio per trading day. Controls whether scoring is allowed to run.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `portfolio_id` | TEXT NOT NULL | FK to portfolios |
| `gate_date` | DATE NOT NULL | Trading day |
| `status` | TEXT NOT NULL DEFAULT 'pending' | `pending \| passed \| blocked` |
| `gate_passed_at` | TIMESTAMPTZ | When all critical issues resolved |
| `blocking_issue_count` | INTEGER NOT NULL DEFAULT 0 | |
| `scoring_triggered_at` | TIMESTAMPTZ | When scoring was fired after gate passed |
| `scoring_completed_at` | TIMESTAMPTZ | When scoring confirmed completion |

**Unique constraint:** `(portfolio_id, gate_date)`

---

### 4.4 `data_refresh_log`

Updated by market-data-service and income-scoring-service after each successful run.

| Column | Type | Notes |
|---|---|---|
| `portfolio_id` | TEXT PK | FK to portfolios |
| `market_data_refreshed_at` | TIMESTAMPTZ | Written by market-data-service |
| `scores_recalculated_at` | TIMESTAMPTZ | Written by income-scoring-service |
| `market_staleness_hrs` | NUMERIC(6,2) | Computed by agent-14 |
| `holdings_complete_count` | INTEGER | Holdings with zero open issues |
| `holdings_incomplete_count` | INTEGER | Holdings with ≥1 open issue |
| `critical_issues_count` | INTEGER | Issues where severity = critical |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

---

## 5. Self-Healing Engine

### 5.1 Issue Lifecycle

```
MISSING → FETCHING → RESOLVED
                  ↘ FAILED → (retry in 15 min, max 3 total)
                           ↘ UNRESOLVABLE → ALERT
```

**Heal logic per attempt:**
1. Try primary source (per `field_requirements.fetch_source_primary`)
2. If empty/error → try fallback source
3. If both fail → increment `attempt_count`, schedule retry
4. After 3 failed attempts → `status = unresolvable`, fire system alert

**Peer comparison before UNRESOLVABLE:** Before escalating, the engine queries whether any peer ticker of the same asset class has the field populated. If yes → severity = `critical`. If no → severity = `warning`. This is the distinction between a fetch failure (system failure) and a data gap that doesn't exist anywhere yet.

### 5.2 Diagnostic Codes

Stored as JSONB in `data_quality_issues.diagnostic`:

| Code | Meaning | Suggested Action |
|---|---|---|
| `TICKER_NOT_FOUND` | Symbol absent from source entirely | Verify ticker; may be delisted or OTC |
| `FIELD_NOT_SUPPORTED` | Ticker found but source doesn't carry this field | Try fallback; if both fail, accept N/A |
| `CLASSIFICATION_MISMATCH` | Source asset type differs from our `asset_class` | Re-run asset classification |
| `PEER_DIVERGENCE` | Value resolves but is >3σ from peer average | Flag for human review |
| `STALE_DATA` | `fetched_at` is older than staleness threshold | Source may be throttling |
| `RATE_LIMITED` | API responded 429 | Auto-retry with backoff; escalate if recurring |
| `AUTH_ERROR` | API key rejected | System-level alert; blocks all fetches from source |
| `ZERO_VALUE` | Field returned 0 — ambiguous with missing | Compare to peers |

**Example diagnostic payload:**
```json
{
  "code": "CLASSIFICATION_MISMATCH",
  "detail": "FMP classifies MAIN as 'CommonStock'; registry expects BDC fields",
  "fmp_response_asset_type": "CommonStock",
  "peer_sample": ["ARCC", "ORCC", "GBDC"],
  "peers_have_field": true,
  "suggested_action": "re_classify"
}
```

---

## 6. Quality Gate

### 6.1 Gate Logic

After each scan cycle, agent-14 evaluates the gate for each portfolio:
- Count open `critical` issues for tracked symbols in that portfolio
- If `critical_issues_count == 0` → `gate_status = passed`, record `gate_passed_at`
- If `critical_issues_count > 0` → `gate_status = blocked`

### 6.2 Scoring Service Integration

Before running, income-scoring-service calls:
```
GET /data-quality/gate/{portfolio_id}
→ { "status": "passed" | "blocked", "blocking_issue_count": N, "gate_passed_at": "..." }
```

- `status == passed` → proceed with scoring run, write `scoring_triggered_at`
- `status != passed` → log at WARNING level, exit cleanly — no scores produced

### 6.3 End-of-Day Timeline

| Time (ET) | Event |
|---|---|
| 4:00 PM | Market close |
| ~4:30 PM | market-data-service refresh completes; writes `market_data_refreshed_at` |
| ~4:31 PM | agent-14 scan triggered; issues detected and written |
| ~4:31–5:30 PM | Self-healing retries (15-min intervals, up to 3 attempts) |
| ~5:30 PM | Gate evaluated: passed or blocked |
| ~5:30–10:00 PM | income-scoring-service runs if gate passed (target: <6h after close) |

**Warning threshold:** If `scores_recalculated_at` is >6h behind `market_data_refreshed_at`, a drift warning is raised even if the gate eventually passed.

---

## 7. Analyst Feature Promotion

Nightly job reads `feature_gap_log` (agent-02):
- If a field appears in ≥2 analyst evaluation frameworks for the same `asset_class`
- AND that field is not already in `field_requirements`
- → INSERT into `field_requirements` with `source = 'analyst_promoted'`, `required = FALSE` (warning-only until manually promoted to required), `fetch_source_primary = NULL` (status `pending_source_mapping`)

Admin reviews promoted fields in the data quality page:
- Assign `fetch_source_primary` → field becomes active in next scan cycle
- OR mark as N/A → `required = FALSE` permanently, no further promotion attempts

No code deploy required — the scanner reads the registry live.

---

## 8. API Endpoints (agent-14)

| Method | Path | Description |
|---|---|---|
| `GET` | `/data-quality/gate/{portfolio_id}` | Gate status for scoring service |
| `GET` | `/data-quality/issues` | All open issues (filterable by symbol, class, severity) |
| `GET` | `/data-quality/issues/{symbol}` | Issues for a specific ticker |
| `GET` | `/data-quality/refresh-log/{portfolio_id}` | Freshness timestamps |
| `POST` | `/data-quality/issues/{id}/retry` | Manual retry trigger |
| `POST` | `/data-quality/issues/{id}/mark-na` | Accept as N/A (removes from gate blocking) |
| `POST` | `/data-quality/issues/{id}/reclassify` | Trigger asset re-classification for symbol |
| `GET` | `/data-quality/field-requirements` | Full registry (read) |
| `PATCH` | `/data-quality/field-requirements/{id}` | Update source mapping (admin only) |

---

## 9. Frontend Changes

### 9.1 Portfolio Page — Health Card

Expandable card below the portfolio name/value header. Collapsed by default.

**Collapsed (healthy):**
```
● Data Health: All Good   Market 4:32 PM · Scores 6:14 PM   ▾
```

**Collapsed (blocked):**
```
● Data Health: Scoring Blocked   2 critical gaps · ARCC, MAIN   Expand ▾
```

**Expanded:**
- Market refresh timestamp + staleness status
- Score recalc timestamp + gate status
- Complete holdings count / total
- Critical issues count with ticker list
- Link to Data Quality Dashboard

### 9.2 Holdings Table — Completeness Badges

New `Data` column in the holdings table:
- `✓ Complete` — green — no open issues
- `✕ N critical` — red — N critical issues (clicking opens admin page filtered to ticker)
- `⚠ N warning` — amber — N warning-only issues
- Badges use tooltip showing the specific missing field names on hover

### 9.3 Data Quality Admin Page (`/admin/data-quality`)

**KPI row (4 cards):** Gate status · Market refresh time · Last scores time · Holdings complete count

**Issues table columns:** Ticker · Class · Missing Field · Severity · Attempts · Diagnostic code (with tooltip) · Actions (Retry Now / Re-classify / Mark N/A)

**Resolved section:** Last 24h resolutions with source and timestamp.

**Filter bar:** By asset class · By severity · By status

---

## 10. Design Constraints

### 10.1 Contrast & Readability

All new UI components (and retroactively applied to existing screens) must meet:
- **WCAG AA** minimum: 4.5:1 contrast ratio for body text, 3:1 for large/bold text and UI components
- Muted labels (`text-muted-foreground`) against dark backgrounds must be verified — many current instances fall below 3:1
- Status colors (red/amber/green) must remain distinguishable for common color-vision deficiencies; pair color with icon/text (never color alone)

This standard applies platform-wide, not only to data quality UI.

---

## 11. Component Map

| File | Change |
|---|---|
| `src/agent-14-data-quality/` | New service: scanner, self-healer, gate logic, API |
| `src/agent-14-data-quality/app/api/routes.py` | REST endpoints §8 |
| `src/agent-14-data-quality/app/scanner.py` | Completeness scan logic |
| `src/agent-14-data-quality/app/healer.py` | Self-healing fetch loop |
| `src/agent-14-data-quality/app/gate.py` | Gate evaluation + scoring trigger |
| `src/agent-14-data-quality/app/promoter.py` | Analyst feature promotion |
| `src/agent-14-data-quality/app/clients/fmp.py` | FMP heal fetcher |
| `src/agent-14-data-quality/app/clients/massive.py` | MASSIVE/Polygon heal fetcher |
| `src/agent-14-data-quality/migrations/` | SQL for 4 new tables |
| `src/income-scoring-service/` | Add gate check before scoring run |
| `src/market-data-service/` | Write `market_data_refreshed_at` after refresh |
| `src/frontend/src/app/api/portfolios/[id]/route.ts` | Include freshness + completeness summary |
| `src/frontend/src/components/portfolio/health-card.tsx` | New expandable health card |
| `src/frontend/src/components/portfolio/completeness-badge.tsx` | New inline badge component |
| `src/frontend/src/app/admin/data-quality/page.tsx` | New admin page |
| `src/frontend/src/lib/types.ts` | Add DataQualityIssue, GateStatus, RefreshLog types |
| `docker-compose.yml` | Add agent-14-data-quality service |

---

## 12. Key Constraints

- **No new primary data fetching** — agent-14 only heals gaps; market-data-service remains the primary fetcher.
- **Single gate check** — scoring service calls one endpoint; no polling.
- **MASSIVE key** — `MASSIVE_KEY` env var already present in `.env`; add to agent-14 container environment.
- **Field registry is live** — scanner reads `field_requirements` on every cycle; no restart required to add fields.
- **Scoring service must not self-start** — scoring only runs after explicit gate pass, never on a fixed clock independent of the gate.
- **Warning-only issues never block** — gate only blocks on `critical` severity; warnings are surfaced but do not prevent scoring.
