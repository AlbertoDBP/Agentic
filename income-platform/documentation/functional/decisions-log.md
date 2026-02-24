# Architecture Decision Records — Income Fortress Platform

This log captures significant architectural and technical decisions made during development.

---

## ADR-008 — Dual-Provider Architecture: Polygon.io + FMP
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 3

### Context
Alpha Vantage free tier lacks dividend history, fundamentals, and ETF holdings required by Agent 03 Income Scorer. A migration was planned (ADR-002) for after Agent 02 completion but was prioritized earlier as a hard dependency for all downstream agents.

### Decision
Implement a dual-primary + fallback provider architecture:
- **Polygon.io Stocks Starter ($29/mo)** — OHLCV, splits, corporate actions
- **Financial Modeling Prep Starter ($22/mo annual)** — dividends, fundamentals, ETF metadata
- **yfinance (free)** — fallback for all methods, primary for ETF holdings (FMP Starter tier restriction)
- **SEC EDGAR (free)** — future tertiary source for authoritative filings

### Consequences
- Agent 03 Income Scorer now has full access to dividend history, payout ratios, and fundamentals
- $51/mo total data provider cost sustainable for development phase
- FMP ETF holdings endpoint requires higher tier — yfinance handles this permanently until upgrade
- Alpha Vantage retained as deprecated reference; not active in routing chain

---

## ADR-009 — BaseDataProvider Abstract Interface
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 3

### Context
Three providers with different APIs, authentication patterns, and data availability needed a unified contract to enable transparent routing and fallback.

### Decision
Define `BaseDataProvider` ABC with five abstract methods: `get_current_price`, `get_daily_prices`, `get_dividend_history`, `get_fundamentals`, `get_etf_holdings`. Concrete implementations per provider. `ProviderRouter` operates against the interface, not concrete classes.

### Consequences
- New providers can be added (Seeking Alpha, Intrinio) without changing router logic
- `__aenter__`/`__aexit__` default in base class — subclasses only override when managing HTTP sessions
- Interface is the single source of truth for what data each provider must supply

---

## ADR-010 — ProviderRouter Priority Chains
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 3

### Context
Different providers have different strengths. Polygon has better price data; FMP has better income data. A single fallback order doesn't serve all data types equally.

### Decision
Define per-method priority chains in `ProviderRouter`:
- Price: Polygon → FMP → yfinance
- Daily prices: Polygon → yfinance (FMP omitted — data quality inferior)
- Dividends: FMP → yfinance
- Fundamentals: FMP → yfinance
- ETF holdings: FMP → yfinance

Graceful degradation: providers that fail to initialize are set to `None` and silently skipped. `_try_chain` catches `ProviderError` and `DataUnavailableError` per attempt; unexpected exceptions propagate immediately.

### Consequences
- FMP is effectively the primary for all income-related data
- Polygon failure does not affect dividend or fundamental queries
- Every successful response logs which provider served it — operational visibility built in

---

## ADR-011 — FMP Stable API Migration
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 3

### Context
FMP migrated from `/api/v3/` to `/stable/` base URL after August 31, 2025. New API keys created after this date receive 403 on all legacy endpoints. Field names also changed (e.g. `priceEarningsRatio` → `priceToEarningsRatio`).

### Decision
All FMP endpoints use `/stable/` base URL. All field mappings updated to stable API names. `_get` raises `ProviderError("FMP API key is not configured")` immediately on empty key rather than sending `apikey=` and receiving a cryptic 403.

### Consequences
- Platform is compatible with all post-Aug-2025 FMP API keys
- `asyncio.gather(return_exceptions=True)` pattern must always re-raise critical endpoint failures — silent null returns are worse than explicit fallback
- FMP `/stable/ratios` returns 403 if called with wrong param format — always use `?symbol=` query param, never `/symbol` path format

---

## ADR-012 — yfinance as Production Fallback
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 3

### Context
yfinance has no official API contract and can break without notice. However, it provides ETF-specific data (expense ratios, fund holdings via `funds_data`) that paid providers don't expose on Starter tiers.

### Decision
Use yfinance as production fallback with these constraints:
- All yfinance calls wrapped with `asyncio.to_thread()` — sync library must not block event loop
- No Redis caching — stale fallback data is worse than fresh fetch
- No rate limiting — Yahoo Finance has no enforced per-key limits at fallback volumes
- `funds_data` guarded with try/except for older yfinance versions

### Consequences
- ETF holdings (expense_ratio, aum, top_holdings, covered_call) served reliably via yfinance
- yfinance instability would degrade ETF endpoint only — other endpoints have paid primary providers
- `_infer_frequency` helper covers dividend frequency gap in yfinance data

---

## ADR-007 — Managed Valkey over Local Redis
**Date:** 2026-02-23
**Status:** Accepted
**Session:** Market Data Service Session 2 (Security Incident)

Orphaned `redis:7-alpine` container removed. All services use managed Valkey via `${REDIS_URL}`.

---

## ADR-004 through ADR-006
See decisions-log from Session 2 documentation.

---
