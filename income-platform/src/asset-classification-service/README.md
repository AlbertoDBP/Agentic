# Asset Classification Service — Agent 04

Rule-based asset class detector mapping symbols to income asset categories (dividend stocks, covered call ETFs, bonds, REITs) with support for custom enrichment rules.

## Overview

Agent 04 provides a lightweight, deterministic classification engine. Given a symbol, it returns an asset class (dividend stock, covered call ETF, bond, REIT, etc.) based on rule evaluation and metadata lookups. The service supports custom rules per user account, enabling portfolio-specific taxonomies. Used by Agent 03 (scoring gate logic), Agent 05 (tax treatment), and Agent 06 (stress scenario simulation).

## Port & Health Check

- **Port:** 8004
- **Health:** `GET /health` — checks database connectivity
- **Docs:** `GET /docs` (OpenAPI/Swagger UI)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + database status |
| POST | `/classify` | Classify a single symbol or list of symbols |
| GET | `/rules` | List all classification rules (system + custom) |
| POST | `/rules` | Create a custom rule for an account |
| PUT | `/rules/{rule_id}` | Update an existing rule |
| DELETE | `/rules/{rule_id}` | Delete a custom rule |

## Dependencies

**Upstream services:**
- Agent 01 (port 8001, optional) — fundamental data for enrichment (expense ratio, AUM for ETFs)

**External dependencies:**
- PostgreSQL (schema: `platform_shared`) — asset_classifications, classification_rules tables
- Redis/Valkey — caching classifications (24h TTL)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection (schema: platform_shared) |
| REDIS_URL | Yes | Redis/Valkey URL for classification cache |
| MARKET_DATA_SERVICE_URL | No | Default: http://localhost:8001 |
| JWT_SECRET | Yes | Shared JWT signing secret |
| SERVICE_PORT | No | Default: 8004 |
| LOG_LEVEL | No | Default: INFO |
| ENRICHMENT_CONFIDENCE_THRESHOLD | No | Default: 0.70 (confidence floor for API enrichment) |
| CLASSIFICATION_CACHE_TTL_HOURS | No | Default: 24 |

## Running Locally

```bash
cd src/asset-classification-service

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://user:pass@localhost/income_platform"
export REDIS_URL="redis://localhost:6379"
export MARKET_DATA_SERVICE_URL="http://localhost:8001"
export JWT_SECRET="dev-secret"

# Run service
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

## Running Tests

```bash
cd src/asset-classification-service
pytest tests/ -v
```

## Project Structure

```
asset-classification-service/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Settings: cache TTL, confidence threshold
│   ├── auth.py                 # JWT verification
│   ├── database.py             # SQLAlchemy engine + connection check
│   ├── models.py               # ORM: AssetClassification, ClassificationRule
│   ├── api/
│   │   ├── health.py           # GET /health
│   │   ├── classify.py         # POST /classify
│   │   └── rules.py            # GET/POST/PUT/DELETE /rules
│   └── classification/
│       ├── detector.py         # Core rule engine (deterministic logic)
│       ├── rules.py            # Rule definitions & evaluation
│       └── enricher.py         # Optional: Agent 01 calls for metadata
├── requirements.txt
├── Dockerfile
└── tests/
    └── ...
```

## Key Design Decisions

- **Rule-Based Over ML:** Deterministic rules avoid the black-box problem and enable quick auditing. Rules encode the platform's view of what constitutes each asset class—e.g., "a covered call ETF has CBOW or JEPI in the name, or holds >= 80% of portfolio in call-writing strategy."
- **Custom Rules Per Account:** Users can add account-specific rules to override system defaults. This allows fund managers to apply their own taxonomies (e.g., "classify VGSIX as bond equivalent because of our internal model").
- **Optional Enrichment:** If classification is ambiguous (e.g., a fund with "Income" in the name that could be bonds or dividends), the service can optionally call Agent 01 for fundamentals (expense ratio, AUM, holdings) to break the tie. Enrichment is cached for 24h.
- **Caching Strategy:** Classifications are cached 24h because asset class rarely changes (unlike prices or fundamentals). This reduces database load and API calls to Agent 01.
