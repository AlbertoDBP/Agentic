# Tax Optimization Service — Agent 05

Provides tax treatment profiling, after-tax yield calculation, account placement optimization, and tax-loss harvesting identification for income-generating investments.

## Overview

Agent 05 is the platform's tax specialist. It evaluates holdings through tax lenses: dividend tax treatment (qualified vs. non-qualified, foreign withholding), capital gains (short vs. long term), tax-loss harvesting opportunities, and optimal account placement (taxable vs. tax-deferred vs. tax-free). Uses rule-based tax code knowledge + calls Agent 04 for asset classifications. Enables tax-aware portfolio optimization—same investment can have very different after-tax returns depending on where it's held.

Used by Agent 06 (scenarios) and downstream advisors/portfolio managers.

## Port & Health Check

- **Port:** 8005
- **Health:** `GET /health` — checks database connectivity
- **Docs:** `GET /docs` (OpenAPI/Swagger UI)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + database status |
| POST | `/tax-treatment` | Analyze tax treatment for a symbol or holding |
| POST | `/after-tax-yield` | Calculate after-tax yield given position & account type |
| POST | `/account-placement` | Recommend optimal account (taxable/401k/IRA/529) for holding |
| GET | `/harvesting-opportunities` | Identify tax-loss harvesting candidates from portfolio |
| POST | `/estimated-liability` | Estimate annual tax liability for a portfolio |

## Dependencies

**Upstream services:**
- Agent 01 (port 8001) — fundamental data (dividend distribution, asset type)
- Agent 04 (port 8004) — asset classification to determine tax treatment rules

**External dependencies:**
- PostgreSQL (schema: `platform_shared`) — user_preferences, holdings, portfolios (read-only)
- Tax code reference tables (embedded in service or external reference)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection (read-only access to platform_shared) |
| JWT_SECRET | Yes | Shared JWT signing secret |
| ASSET_CLASSIFICATION_URL | No | Default: http://asset-classification-service:8004 |
| AGENT04_TIMEOUT_SECONDS | No | Default: 3.0 |
| SERVICE_PORT | No | Default: 8005 |
| LOG_LEVEL | No | Default: INFO |

## Running Locally

```bash
cd src/tax-optimization-service

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://user:pass@localhost/income_platform?sslmode=disable"
export ASSET_CLASSIFICATION_URL="http://localhost:8004"
export JWT_SECRET="dev-secret"

# Run service
uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
```

## Running Tests

```bash
cd src/tax-optimization-service
pytest tests/ -v
```

## Project Structure

```
tax-optimization-service/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Settings: DB, service URLs, timeouts
│   ├── auth.py                 # JWT verification
│   ├── database.py             # SQLAlchemy engine (read-only pool)
│   ├── models.py               # ORM: Holdings, Portfolios (read-only views)
│   ├── api/
│   │   └── routes.py           # All tax optimization endpoints
│   └── tax/
│       ├── engine.py           # Core tax calculation logic
│       ├── treatment.py        # Dividend/capital gains tax treatment rules
│       ├── placement.py        # Account placement optimization
│       ├── harvesting.py       # Tax-loss harvesting candidates
│       ├── yields.py           # After-tax yield calculation
│       └── clients.py          # Agent 04 HTTP client
├── requirements.txt
├── Dockerfile
└── tests/
    └── ...
```

## Key Design Decisions

- **Rule-Based Tax Engine:** Encodes IRS rules (2026 tax year, assumed US context) for qualified dividend treatment, long-term capital gains, foreign dividend withholding, REIT preferential treatment. Updatable annually without code changes via configuration.
- **Account-Type Aware Yields:** After-tax yield is context-dependent. A 4% dividend stock yields 3.2% in a taxable account (20% long-term dividend tax + 3.8% NIIT) but 4% in a Roth IRA. The service returns yields scoped to account type.
- **Classification-Dependent Treatment:** Tax rules differ by asset class (equity dividends vs. REIT dividends vs. bond interest vs. municipal bond interest). Service calls Agent 04 to classify first, then applies appropriate tax treatment.
- **Tax-Loss Harvesting Scanner:** Identifies positions down > X% (configurable, default 10%) in the current tax year. Flags potential harvesting candidates subject to wash-sale rules (avoid repurchase within 30 days).
