# Agent 02 — Newsletter Ingestion Service

The Dividend Detective: ingests Seeking Alpha analyst content, extracts income investment signals, and maintains analyst accuracy profiles via Prefect orchestration and Claude/OpenAI AI analysis.

## Overview

Agent 02 harvests analyst recommendations and research from Seeking Alpha (via RapidAPI), processes articles using Anthropic Claude for extraction and OpenAI embeddings, maintains accuracy profiles by tracking analyst performance over time, and produces consensus-weighted investment signals. Prefect coordinates two main workflows: Harvester (fetches & analyzes articles) and Intelligence (aggregates into consensus). The service enables data-driven analyst selection—bad actors are automatically downweighted.

## Port & Health Check

- **Port:** 8002
- **Health:** `GET /health` — checks database, pgvector extension, platform_shared schema
- **Docs:** `GET /docs` (OpenAPI/Swagger UI)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + database + pgvector extension status |
| POST | `/flows/harvester/trigger` | Trigger background Harvester Flow (fetch & analyze articles) |
| POST | `/flows/intelligence/trigger` | Trigger background Intelligence Flow (aggregate consensus) |
| GET | `/flows/status` | Last run metadata for both flows |
| GET | `/analysts` | List all tracked analysts + accuracy profiles |
| GET | `/analysts/{analyst_id}` | Detailed analyst performance history |
| POST | `/recommendations` | Query recommendations by symbol/recommendation/date |
| GET | `/consensus/{symbol}` | Weighted consensus score for a symbol (by philosophy cluster) |
| GET | `/signal/{symbol}` | Investment signal derived from consensus (aggregated analyst opinion) |

## Dependencies

**Upstream services:** None (standalone ingestion pipeline)

**External dependencies:**
- PostgreSQL (schema: `platform_shared`) — analysts, articles, recommendations, analyst_signals, consensus_signals, embeddings
- Redis/Valkey (optional) — caching analyst & consensus signals (1h, 30m TTL)
- **Seeking Alpha (via RapidAPI/APIDojo)** — analyst recommendations & articles
- **Financial Modeling Prep** — market truth for validation/enrichment
- **Anthropic Claude** — article extraction & philosophy synthesis (bulk vs quality models)
- **OpenAI** — embeddings for semantic clustering (text-embedding-3-small, 1536 dims)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string (schema: platform_shared) |
| REDIS_URL | Yes | Redis/Valkey URL for signal caching |
| APIDOJO_SA_API_KEY | Yes | RapidAPI key for Seeking Alpha endpoints |
| ANTHROPIC_API_KEY | Yes | Anthropic API key for Claude models |
| OPENAI_API_KEY | Yes | OpenAI API key for embeddings |
| FMP_API_KEY | Yes | Financial Modeling Prep API key |
| JWT_SECRET | Yes | Shared JWT signing secret |
| SERVICE_PORT | No | Default: 8002 |
| LOG_LEVEL | No | Default: INFO |
| EXTRACTION_MODEL | No | Default: claude-haiku-20250310 (cost-optimized) |
| PHILOSOPHY_MODEL | No | Default: claude-sonnet-4-20250514 (quality) |
| EMBEDDING_DIMENSIONS | No | Default: 1536 |

## Running Locally

```bash
cd src/agent-02-newsletter-ingestion

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://user:pass@localhost/income_platform"
export REDIS_URL="redis://localhost:6379"
export APIDOJO_SA_API_KEY="your_key"
export ANTHROPIC_API_KEY="your_key"
export OPENAI_API_KEY="your_key"
export FMP_API_KEY="your_key"
export JWT_SECRET="dev-secret"

# Run service
python -m app.main
# or via uvicorn:
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## Running Tests

```bash
cd src/agent-02-newsletter-ingestion
pytest tests/ -v
```

## Project Structure

```
agent-02-newsletter-ingestion/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Settings: API keys, models, cron schedules
│   ├── auth.py                 # JWT verification
│   ├── database.py             # SQLAlchemy setup + health check
│   ├── models.py               # ORM: Analyst, Article, Recommendation, AnalystSignal, ConsensusSignal
│   ├── api/
│   │   ├── health.py           # GET /health
│   │   ├── flows.py            # POST /flows/{harvester,intelligence}/trigger, GET /flows/status
│   │   ├── analysts.py         # GET /analysts, /analysts/{id}
│   │   ├── recommendations.py  # POST /recommendations (query)
│   │   ├── consensus.py        # GET /consensus/{symbol}
│   │   └── signal.py           # GET /signal/{symbol}
│   ├── flows/
│   │   ├── harvester_flow.py   # Prefect flow: fetch SA articles, extract, embed
│   │   └── intelligence_flow.py # Prefect flow: K-Means clustering, consensus aggregation
│   ├── services/
│   │   ├── seeking_alpha.py    # Seeking Alpha client (RapidAPI)
│   │   ├── extraction.py       # Claude extraction: article → structured data
│   │   ├── embedding.py        # OpenAI embeddings: article → vector
│   │   ├── consensus.py        # Consensus aggregation: K-Means + decay weighting
│   │   └── accuracy_tracker.py # Analyst performance tracking
│   └── utils/
│       ├── validators.py       # Recommendation validation
│       └── helpers.py          # Common utilities
├── requirements.txt
├── Dockerfile
└── tests/
    └── ...
```

## Key Design Decisions

- **Two-Flow Architecture:** Harvester (batch data ingestion) and Intelligence (consensus aggregation) run on separate Prefect schedules (Tue/Fri 7AM and Mon 6AM ET). This decouples data freshness from signal stability and allows manual trigger via API.
- **Dual-Model Claude Strategy:** Haiku for cheap bulk extraction (cost), Sonnet for philosophy synthesis (quality). This balances API costs with output quality—raw extraction is compute-intensive and repetitive, while philosophy synthesis benefits from better reasoning.
- **Aging & Decay Weighting:** Recommendations older than a configurable window (default 365 days) decay via S-curve. This handles the classic "old good advice is stale" problem—analysts who made great calls 2 years ago shouldn't weigh equally with recent calls.
- **Analyst Accuracy Profiles:** Tracks each analyst's precision, recall, and Sharpe-like metrics. Bad actors (< 50% accuracy threshold) are automatically downweighted in consensus. This prevents one analyst's bad calls from skewing the crowd.
