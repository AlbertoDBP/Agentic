# ADR-A01 — Finnhub as 4th Credit Rating Provider + Interest Coverage Proxy

**Status:** Accepted
**Date:** 2026-03-09
**Component:** Agent 01 — Market Data Service

---

## Context

`credit_rating` returned NULL from all three existing providers (Polygon.io, FMP,
yfinance) for the majority of income-generating securities. The BBB- quality gate
in Agent 03 was blocked by this gap — every asset was treated as unrated.

Two solutions were evaluated:

1. **Finnhub** — free API, provides S&P/Moody's credit ratings via
   `/stock/metric?metric=all`, `metric.creditRating` field
2. **SEC EDGAR** — free, no key, provides annual interest coverage ratio as proxy
   (lagging indicator, 90-day delay on annual filings)

## Decision

**Both, in cascade order:**

```
Finnhub credit_rating TEXT (primary)
    ↓ if None
FMP interest_coverage (already fetched in sync sequence)
    ≥ 3.0  → INVESTMENT_GRADE
    1.5–2.9 → BORDERLINE
    < 1.5  → SPECULATIVE_GRADE
    None   → credit_quality_proxy = NULL
```

SEC EDGAR dropped — `interest_coverage` comes from FMP which is already in
the sync sequence. No additional HTTP call required.

## Rationale

- Finnhub free tier is sufficient for the platform's universe size
- FMP `interest_coverage` is already fetched — zero additional latency
- SEC EDGAR would add latency and complexity for data already available via FMP
- Credit quality proxy makes the BBB- gate operable even when letter rating absent
- `credit_quality_proxy` stored separately from `credit_rating` — proxy is clearly
  labeled, never confused with actual rating agency data

## Consequences

- `credit_rating` NULL rate reduced significantly for investment-grade securities
- Agent 03 BBB- quality gate now operational
- `credit_quality_proxy` provides fallback for ETFs and instruments not rated by S&P
- Finnhub rate limits (free tier: 60 calls/minute) — `/sync` endpoint is on-demand,
  not scheduled, so rate limits are not a concern in v1

---

# ADR-A02 — Chowder Number Nullability

**Status:** Accepted
**Date:** 2026-03-09
**Component:** Agent 01 — Market Data Service

---

## Context

The Chowder Number is defined as `yield_trailing_12m + div_cagr_5y`. Both inputs
may be unavailable (IPO < 5 years, no dividend history, data provider gap).

Two options:
- Store `0.0` when inputs are missing (treat as unattractive)
- Store `NULL` when inputs are missing (unknown, not unattractive)

## Decision

**Store NULL when either input is missing.**

```python
chowder_number = (
    round(yield_trailing_12m + div_cagr_5y, 2)
    if yield_trailing_12m is not None and div_cagr_5y is not None
    else None    # NULL, not 0.0
)
```

## Rationale

- `0.0` Chowder Number would classify the asset as UNATTRACTIVE — incorrect for
  a stock with a strong dividend history that simply has a data gap
- NULL correctly signals "insufficient data" to Agent 03
- `chowder_signal = 'INSUFFICIENT_DATA'` when `chowder_number IS NULL`
- `missing_fields` in SyncResponse explicitly surfaces the gap

## Consequences

- Agent 03 must handle NULL `chowder_number` — emits `INSUFFICIENT_DATA` signal
- Assets with NULL Chowder are not penalized in scoring (0% weight field)
- `missing_fields` in SyncResponse allows operators to identify data gaps by symbol

---

# ADR-A03 — Lazy Securities Upsert on Existing Endpoints

**Status:** Accepted
**Date:** 2026-03-09
**Component:** Agent 01 — Market Data Service

---

## Context

`platform_shared.securities` is the master ticker registry required by the
portfolio layer FK chain. It needs to be populated before positions can reference
any ticker. Two population strategies:

- **Explicit only** — only `/sync` endpoint populates `securities`
- **Lazy + explicit (Option C)** — `GET /fundamentals` and `GET /etf` also upsert
  automatically; `/sync` does the full feature write

## Decision

**Option C — lazy upsert on fundamentals + ETF, full write on /sync.**

## Rationale

- `securities` upsert is a lightweight ON CONFLICT operation (~1ms)
- Existing endpoints are already calling FMP — `name`, `sector`, `exchange` are
  present in the response at no additional cost
- Ensures `securities` is populated organically as agents query existing endpoints,
  even before anyone calls `/sync`
- Fire-and-forget pattern means existing endpoint latency and error handling are
  completely unaffected

## Consequences

- `securities` table self-populates as existing agents run normally
- `/sync` is required only for full feature vector (yield metrics, Chowder, credit)
- Lazy upsert errors are logged but never surface to API caller
