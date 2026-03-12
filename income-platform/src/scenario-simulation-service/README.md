# Scenario Simulation Service — Agent 06

Monte Carlo stress testing, income projection, and portfolio vulnerability analysis for income portfolios under market shocks.

## Overview

Agent 06 is the platform's stress testing engine. Given a portfolio and a scenario (market crash, interest rate shock, dividend cut, volatility spike, or custom params), it simulates outcomes via Monte Carlo using scipy financial models. Returns stressed portfolio value, income impact, per-position vulnerability ranking, and breakeven analysis. Enables what-if planning—"What if interest rates jump 200 bps?" or "What if dividend stocks crash 30%?"

Used by portfolio managers, advisors, and the platform's risk dashboards.

## Port & Health Check

- **Port:** 8006
- **Health:** `GET /health` — checks database connectivity + asyncpg pool
- **Docs:** `GET /docs` (OpenAPI/Swagger UI)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + database + asyncpg pool status |
| GET | `/scenarios` | List available predefined scenarios (market crash, rate shock, etc.) |
| POST | `/stress-test` | Run stress test on portfolio with given scenario |
| POST | `/income-projection` | Project portfolio income under multiple market conditions |
| GET | `/vulnerabilities` | Identify most vulnerable positions in portfolio |
| POST | `/custom-scenario` | Build and test a custom scenario |

## Dependencies

**Upstream services:**
- Agent 01 (port 8001) — price history, volatility estimates
- Agent 03 (port 8003) — income scores & quality gate results
- Agent 04 (port 8004) — asset classification for stress modeling

**External dependencies:**
- PostgreSQL (schema: `platform_shared`) — portfolios, holdings, scenario_results tables
- scipy — financial simulation (GBM, correlation matrices)
- numpy — numerical computation

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection (schema: platform_shared) |
| JWT_SECRET | Yes | Shared JWT signing secret |
| SERVICE_PORT | No | Default: 8006 |
| LOG_LEVEL | No | Default: INFO |

## Running Locally

```bash
cd src/scenario-simulation-service

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DATABASE_URL="postgresql://user:pass@localhost/income_platform"
export JWT_SECRET="dev-secret"

# Run service
uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload
```

## Running Tests

```bash
cd src/scenario-simulation-service
pytest tests/ -v
```

## Project Structure

```
scenario-simulation-service/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Settings: service identity, DB, auth
│   ├── auth.py                 # JWT verification
│   ├── database.py             # SQLAlchemy engine + asyncpg pool
│   ├── models.py               # ORM: Portfolio, ScenarioResult, PositionImpact
│   ├── api/
│   │   ├── health.py           # GET /health
│   │   └── scenarios.py        # POST /stress-test, GET /scenarios, etc.
│   └── simulation/
│       ├── portfolio_reader.py # Fetch portfolio + holdings from DB via asyncpg
│       ├── scenario_library.py # Predefined scenarios (crash, rate shock, etc.)
│       ├── stress_engine.py    # Core Monte Carlo stress engine (scipy/GBM)
│       ├── income_projector.py # Income projection under stress
│       └── clients.py          # Upstream service HTTP clients
├── requirements.txt
├── Dockerfile
└── tests/
    └── ...
```

## Key Design Decisions

- **Monte Carlo Via GBM:** Uses Geometric Brownian Motion (scipy) to simulate 1000+ stock price paths under given scenario parameters (drift, volatility, correlation). Captures tail risk and non-linear effects better than simple sensitivity analysis.
- **Scenario Library Approach:** Predefined scenarios encode common shocks: market crash (-20% single day), interest rate shock (+100 to +300 bps), dividend cut (-50% distribution), vol spike (historical vol x2.5). Enables fast "press the button" analysis without deep modeling knowledge.
- **Per-Position Vulnerability:** Ranks positions by both absolute loss and relative contribution to portfolio volatility. An ETF down 30% in crash scenario ranks lower if it's 5% of portfolio vs. 40%. Guides concentration reduction.
- **Custom Scenario Builder:** Allows advanced users to define custom scenarios: "S&P down 15%, high-yield spreads widen 300bp, gold up 10%." Returns correlations & simulations. Enables tail-risk hedging analysis.
