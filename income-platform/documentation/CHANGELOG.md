# CHANGELOG — Agent 02 + Agent 12

All notable changes to Agent 02 (Newsletter Ingestion) and Agent 12 (Proposal Agent).

---

## [1.0.0] — 2026-02-25

### Agent 02 — Complete Implementation

**Phase 1 — Foundation**
- FastAPI service skeleton on port 8002
- SQLAlchemy ORM: analysts, analyst_articles, analyst_recommendations, analyst_accuracy_log, credit_overrides
- pgvector integration with IVFFlat indexes on embedding columns
- Idempotent migration script with pgvector extension validation
- Health endpoint with healthy/degraded/unhealthy states
- Pydantic schemas including AnalystSignalResponse (Agent 12 contract)
- Production Dockerfile with non-root user and health check

**Phase 2 — Harvester Flow**
- APIDojo SA client: `/articles/v2/list` + `/articles/v2/get-details` confirmed endpoints
- `_normalize_article()` flattens nested `attributes` response structure
- SHA-256 deduplicator: SA article ID check (fast) + content hash check (thorough)
- HTML → Markdown conversion via `markdownify` at ingest time
- Claude Haiku structured extraction: 12-field income signal prompt
- OpenAI text-embedding-3-small: article body + recommendation thesis embeddings (1536d)
- Recommendation supersession model: ticker-scoped, preserves history
- Prefect harvester_flow: per-analyst + per-article error isolation
- Flow trigger endpoints: POST /flows/harvester/trigger + POST /flows/intelligence/trigger
- Analyst seed script with test authors 96726 and 104956

**Phase 3 — Intelligence Flow**
- S-curve decay sweeper: configurable aging_days + halflife_days per analyst
- FMP market truth client: historical price + dividend history
- Accuracy backtest: T+30/T+90 price checks, dividend cut detection, outcome_label, accuracy_delta
- Per-analyst sector_alpha tracking
- Philosophy synthesis: LLM summary (< 20 articles) + K-Means K=5 (≥ 20 articles)
- Weighted consensus score builder: accuracy × decay × user_weight
- Intelligence Prefect flow: Monday 6AM ET schedule
- /flows/intelligence/trigger endpoint activated (was 501)

**Phase 4 — API Layer**
- GET/POST /analysts with 409 guard on duplicate SA ID
- GET /analysts/{id}/recommendations with decay_weight ordering
- GET /recommendations/{ticker} with min_decay_weight filter
- GET /consensus/{ticker}: Redis-cached 30min, weighted accuracy × decay
- GET /signal/{ticker}: Agent 12 contract — signal_strength, proposal_readiness
- signal_strength: strong/moderate/weak/insufficient quality ladder
- proposal_readiness: strength ≥ moderate AND accuracy ≥ threshold
- 16 Phase 4 unit tests + Agent 12 contract field validation

**Phase 5 — Production Hardening**
- Multi-stage Dockerfile: builder + runtime (smaller final image)
- docker-compose.yml: local dev stack (postgres + valkey + agent-02)
- nginx/agent-02.conf: Nginx location block for DO reverse proxy
- scripts/deploy.sh: DigitalOcean deployment with health check gate
- scripts/prefect_schedule.py: Harvester + Intelligence schedule registration
- .env.production.example: all variables documented
- Integration smoke tests: auto-skip if service not running

### Agent 12 — Functional Specification Complete

- Dual-lens proposal model (analyst view + platform view side by side)
- Alignment computation: Aligned | Partial | Divergent | Vetoed
- ProposalObject schema with full execution parameters
- VETO enforcement: Path A blocked, Path B requires hard acknowledgment
- Three trigger modes: signal-driven, on-demand, scheduled re-evaluation
- Platform alignment writeback to Agent 02 analyst_recommendations
- Override outcome logging to Agent 02 accuracy log
- Implementation pending (follows Agent 03 completion)

---

## Upcoming

- Agent 02: Production deployment to DigitalOcean (requires .env update)
- Agent 03: Income Scorer — builds on Agent 02 signal API
- Agent 12: Implementation (after Agent 03 completion)
