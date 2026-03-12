# Agent 07 — Opportunity Scanner — CHANGELOG

## v1.0.0 — 2026-03-12

Initial release.

- `POST /scan` — score up to 200 tickers via Agent 03, apply filters, rank results
- `GET /scan/{scan_id}` — retrieve persisted scan result
- `GET /universe` — list tracked securities from `platform_shared.securities`
- `GET /health` — health check with DB status
- VETO gate enforcement: tickers with score < 70 flagged (`veto_flag: true`)
- Concurrent scoring: asyncio semaphore limiting to 10 parallel Agent 03 calls
- Graceful degradation: Agent 03 failures return `None`; ticker skipped, scan continues
- Results persisted to `platform_shared.scan_results` (JSONB items column)
- 100 tests: 40 engine, 25 scoring client, 35 API
