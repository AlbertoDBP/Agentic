# Agent 02 + Agent 12 — Documentation Index

**Income Fortress Platform** | Newsletter Ingestion & Proposal Agent  
**Last Updated:** 2026-02-25  
**Status:** ✅ Agent 02 Complete | 📐 Agent 12 Spec Complete

---

## Overview

This index covers two tightly coupled agents in the Income Fortress Platform:

**Agent 02 — The Dividend Detective (Newsletter Ingestion Service)**  
Ingests Seeking Alpha analyst articles, extracts income investment signals via Claude Haiku, embeds content with OpenAI, and provides a weighted consensus API consumed by Agent 12. Runs as a FastAPI microservice on port 8002.

**Agent 12 — The Proposal Agent**  
Synthesizes Agent 02 signals with platform assessments from Agents 03/04/05 into structured user-facing proposals. Always presents both analyst and platform perspectives — never silently blocks. Enforces VETO conditions with mandatory override acknowledgment.

---

## Quick Links

### Architecture
- [Reference Architecture](architecture/reference-architecture.md)
- [System Diagram](diagrams/system-diagram.mmd)
- [Component Interactions — Harvester Flow](diagrams/harvester-flow-sequence.mmd)
- [Component Interactions — Intelligence Flow](diagrams/intelligence-flow-sequence.mmd)
- [Component Interactions — Proposal Flow](diagrams/proposal-flow-sequence.mmd)
- [Data Model](diagrams/data-model.mmd)

### Functional Specifications
- [Agent 02 — Newsletter Ingestion](functional/agent-02-newsletter-ingestion.md)
- [Agent 12 — Proposal Agent](functional/agent-12-proposal-agent.md)

### Implementation Specifications
- [Agent 02 — Harvester Flow](implementation/agent-02-harvester-flow.md)
- [Agent 02 — Intelligence Flow](implementation/agent-02-intelligence-flow.md)
- [Agent 02 — API Layer](implementation/agent-02-api-layer.md)
- [Agent 12 — Proposal Pipeline](implementation/agent-12-proposal-pipeline.md)

### Testing
- [Test Matrix](testing/test-matrix.md)

### Project Records
- [Decisions Log](decisions-log.md)
- [CHANGELOG](CHANGELOG.md)

---

## Component Status

| Component | Status | Port | Phase |
|---|---|---|---|
| Agent 02 — Foundation | ✅ Complete | 8002 | Phase 1 |
| Agent 02 — Harvester Flow | ✅ Complete | 8002 | Phase 2 |
| Agent 02 — Intelligence Flow | ✅ Complete | 8002 | Phase 3 |
| Agent 02 — API Layer | ✅ Complete | 8002 | Phase 4 |
| Agent 02 — Production Hardening | ✅ Complete | 8002 | Phase 5 |
| Agent 12 — Proposal Agent | 📐 Spec Complete | TBD | Pending |

---

## Repository Location

```
/Agentic/income-platform/src/agent-02-newsletter-ingestion/
├── app/
│   ├── api/          analysts.py, consensus.py, flows.py, health.py,
│   │                 recommendations.py, signal.py
│   ├── clients/      seeking_alpha.py, fmp_client.py
│   ├── flows/        harvester_flow.py, intelligence_flow.py
│   ├── models/       models.py, schemas.py
│   ├── processors/   article_store.py, backtest.py, consensus.py,
│   │                 deduplicator.py, extractor.py, philosophy.py,
│   │                 staleness.py, vectorizer.py
│   ├── config.py, database.py, main.py
├── nginx/            agent-02.conf
├── scripts/          deploy.sh, migrate.py, prefect_schedule.py,
│                     seed_analysts.py
├── tests/            test_phase1_foundation.py, test_phase2_harvester.py,
│                     test_phase4_api.py, test_phase5_integration.py
├── Dockerfile, docker-compose.yml, requirements.txt
```
