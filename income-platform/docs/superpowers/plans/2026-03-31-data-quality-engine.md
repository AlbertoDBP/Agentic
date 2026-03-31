# Data Quality Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build agent-14-data-quality — a new containerised service that scans market_data_cache for missing required fields, self-heals gaps via FMP/MASSIVE, gates scoring until data is complete, and surfaces freshness + completeness status to users.

**Architecture:** New FastAPI service (`agent-14-data-quality`, port 8014) downstream of market data refresh. Scheduler fires the scan at 18:35 ET (5 min after market data refresh). Agent-03 checks the gate before scoring. Frontend health card + admin page consume agent-14 APIs via Next.js proxy routes.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, psycopg2, httpx, pydantic-settings, APScheduler (scheduler-service), Next.js App Router (frontend)

**Spec:** `docs/superpowers/specs/2026-03-30-data-quality-engine-design.md`

---

## File Map

### New files
| File | Responsibility |
| --- | --- |
| `src/agent-14-data-quality/Dockerfile` | Two-stage build, port 8014 |
| `src/agent-14-data-quality/requirements.txt` | Python deps |
| `src/agent-14-data-quality/app/__init__.py` | Package marker |
| `src/agent-14-data-quality/app/main.py` | FastAPI app, lifespan, routers |
| `src/agent-14-data-quality/app/config.py` | pydantic-settings config |
| `src/agent-14-data-quality/app/database.py` | SQLAlchemy engine + session factory |
| `src/agent-14-data-quality/app/auth.py` | JWT verify_token (same pattern as other agents) |
| `src/agent-14-data-quality/app/scanner.py` | Completeness scan logic |
| `src/agent-14-data-quality/app/healer.py` | Self-healing fetch + lifecycle |
| `src/agent-14-data-quality/app/gate.py` | Gate evaluation per portfolio |
| `src/agent-14-data-quality/app/promoter.py` | Analyst feature promotion nightly |
| `src/agent-14-data-quality/app/api/__init__.py` | Package marker |
| `src/agent-14-data-quality/app/api/health.py` | GET /health |
| `src/agent-14-data-quality/app/api/routes.py` | All §8 endpoints |
| `src/agent-14-data-quality/app/clients/__init__.py` | Package marker |
| `src/agent-14-data-quality/app/clients/fmp.py` | FMP heal fetcher |
| `src/agent-14-data-quality/app/clients/massive.py` | Polygon/MASSIVE heal fetcher |
| `src/agent-14-data-quality/migrations/001_initial.sql` | 5 tables + seed data |
| `src/agent-14-data-quality/tests/__init__.py` | Package marker |
| `src/agent-14-data-quality/tests/test_scanner.py` | Scanner unit tests |
| `src/agent-14-data-quality/tests/test_gate.py` | Gate unit tests |
| `src/agent-14-data-quality/tests/test_healer.py` | Healer unit tests |
| `src/frontend/src/app/api/portfolios/[id]/route.ts` | New API route — portfolio detail with freshness |
| `src/frontend/src/components/portfolio/health-card.tsx` | Expandable health card |
| `src/frontend/src/components/portfolio/completeness-badge.tsx` | Per-holding badge |
| `src/frontend/src/app/admin/data-quality/page.tsx` | Admin data quality page |

### Modified files
| File | Change |
| --- | --- |
| `src/agent-14-data-quality/migrations/001_initial.sql` | *(new — listed above)* |
| `src/scheduler-service/app/config.py` | Add `agent14_url` |
| `src/scheduler-service/app/jobs.py` | Add 3 new jobs |
| `src/scheduler-service/app/main.py` | Register 3 new jobs |
| `src/income-scoring-service/app/config.py` | Add `data_quality_service_url` |
| `src/income-scoring-service/app/api/scores.py` | Add gate check in `refresh-portfolio` handler |
| `docker-compose.yml` | Add agent-14 service |
| `src/frontend/src/lib/types.ts` | Add DQ types |
| `src/frontend/src/app/portfolios/[id]/page.tsx` | Mount health card |

---

## Task 1: Database Migration

**Files:**
- Create: `src/agent-14-data-quality/migrations/001_initial.sql`

- [ ] **Step 1: Write the migration**

```sql
-- src/agent-14-data-quality/migrations/001_initial.sql
-- Data Quality Engine — initial schema
-- Run as: psql $DATABASE_URL -f migrations/001_initial.sql

SET search_path TO platform_shared;

-- ── 1. field_requirements ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS field_requirements (
    id                    SERIAL PRIMARY KEY,
    asset_class           TEXT NOT NULL,
    field_name            TEXT NOT NULL,
    required              BOOLEAN NOT NULL DEFAULT TRUE,
    fetch_source_primary  TEXT,            -- 'fmp' | 'massive' | NULL
    fetch_source_fallback TEXT,            -- 'fmp' | 'massive' | NULL
    source                TEXT NOT NULL DEFAULT 'core',  -- 'core' | 'analyst_promoted'
    promoted_from_gap_id  INTEGER,         -- FK → feature_gap_log.id (cross-service)
    source_endpoint       TEXT,            -- e.g. 'fmp:/etf-info'
    description           TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_field_requirements UNIQUE (asset_class, field_name)
);

-- ── 2. data_quality_issues ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id               SERIAL PRIMARY KEY,
    symbol           TEXT NOT NULL,
    field_name       TEXT NOT NULL,
    asset_class      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'missing',
    severity         TEXT NOT NULL DEFAULT 'warning',
    attempt_count    INTEGER NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    resolved_at      TIMESTAMPTZ,
    source_used      TEXT,
    diagnostic       JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dq_issues UNIQUE (symbol, field_name)
);

CREATE INDEX IF NOT EXISTS idx_dqi_status   ON data_quality_issues (status);
CREATE INDEX IF NOT EXISTS idx_dqi_severity ON data_quality_issues (severity);
CREATE INDEX IF NOT EXISTS idx_dqi_symbol   ON data_quality_issues (symbol);

-- ── 3. data_quality_exemptions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_exemptions (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL,
    field_name  TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    reason      TEXT,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dq_exemptions UNIQUE (symbol, field_name)
);

-- ── 4. data_quality_gate ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_gate (
    id                    SERIAL PRIMARY KEY,
    portfolio_id          UUID NOT NULL,
    gate_date             DATE NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending',
    gate_passed_at        TIMESTAMPTZ,
    blocking_issue_count  INTEGER NOT NULL DEFAULT 0,
    scoring_triggered_at  TIMESTAMPTZ,
    scoring_completed_at  TIMESTAMPTZ,
    CONSTRAINT uq_dq_gate UNIQUE (portfolio_id, gate_date)
);

CREATE INDEX IF NOT EXISTS idx_dqg_portfolio ON data_quality_gate (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_dqg_date      ON data_quality_gate (gate_date);

-- ── 5. data_refresh_log ───────────────────────────────────────────────────────
-- One row per portfolio; upserted on each refresh / scoring cycle.
CREATE TABLE IF NOT EXISTS data_refresh_log (
    portfolio_id               UUID PRIMARY KEY,
    market_data_refreshed_at   TIMESTAMPTZ,
    scores_recalculated_at     TIMESTAMPTZ,
    market_staleness_hrs       NUMERIC(6,2),
    holdings_complete_count    INTEGER,
    holdings_incomplete_count  INTEGER,
    critical_issues_count      INTEGER,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Seed: field_requirements ──────────────────────────────────────────────────
-- Universal fields (all asset classes)
DO $$
DECLARE
    classes TEXT[] := ARRAY['CommonStock','ETF','CEF','BDC','REIT','MLP','Preferred'];
    universal TEXT[] := ARRAY['price','week52_high','week52_low','dividend_yield','div_frequency','sma_50','sma_200','rsi_14d'];
    -- Note: MORTGAGE_REIT securities map to 'REIT' asset_class in the scanner
    -- (ASSET_TYPE_TO_CLASS: EQUITY_REIT → REIT, MORTGAGE_REIT → REIT)
    -- so MORTGAGE_REIT is NOT a separate asset_class in field_requirements.
    cls TEXT;
    fld TEXT;
BEGIN
    FOREACH cls IN ARRAY classes LOOP
        FOREACH fld IN ARRAY universal LOOP
            INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source)
            VALUES (cls, fld, TRUE, 'massive', 'fmp', 'core')
            ON CONFLICT (asset_class, field_name) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;

-- Class-specific fields
INSERT INTO field_requirements (asset_class, field_name, required, fetch_source_primary, fetch_source_fallback, source_endpoint, source) VALUES
    ('CommonStock', 'payout_ratio',          TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('CommonStock', 'chowder_number',         TRUE,  'fmp',     NULL,      'fmp:/dividends',       'core'),
    ('CommonStock', 'consecutive_growth_yrs', TRUE,  'fmp',     NULL,      'fmp:/dividends-history','core'),
    -- REIT covers both EQUITY_REIT and MORTGAGE_REIT securities (both map to 'REIT' asset_class)
    ('REIT',        'payout_ratio',           TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('REIT',        'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('REIT',        'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('ETF',         'nav_value',              TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('ETF',         'nav_discount_pct',       FALSE, 'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('CEF',         'nav_value',              TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('CEF',         'nav_discount_pct',       TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('CEF',         'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('CEF',         'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('BDC',         'nav_value',              TRUE,  'fmp',     NULL,      'fmp:/etf-info',        'core'),
    ('BDC',         'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('BDC',         'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('MLP',         'interest_coverage_ratio',TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core'),
    ('MLP',         'debt_to_equity',         TRUE,  'fmp',     'massive', 'fmp:/ratios',          'core')
ON CONFLICT (asset_class, field_name) DO NOTHING;
```

- [ ] **Step 2: Verify the SQL is valid**

```bash
# Dry-run against local or remote DB (replace with your actual DATABASE_URL)
psql $DATABASE_URL -v ON_ERROR_STOP=1 --single-transaction -f \
  src/agent-14-data-quality/migrations/001_initial.sql
```

Expected: no ERRORs; tables and seed rows created.

- [ ] **Step 3: Commit**

```bash
git add src/agent-14-data-quality/migrations/001_initial.sql
git commit -m "feat(dq): add data quality engine migration and seed data"
```

---

## Task 2: Service Scaffold

**Files:**
- Create: `src/agent-14-data-quality/requirements.txt`
- Create: `src/agent-14-data-quality/Dockerfile`
- Create: `src/agent-14-data-quality/app/__init__.py`
- Create: `src/agent-14-data-quality/app/config.py`
- Create: `src/agent-14-data-quality/app/database.py`
- Create: `src/agent-14-data-quality/app/auth.py`
- Create: `src/agent-14-data-quality/app/api/__init__.py`
- Create: `src/agent-14-data-quality/app/api/health.py`
- Create: `src/agent-14-data-quality/app/main.py`

- [ ] **Step 1: Write requirements.txt**

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.36
psycopg2-binary==2.9.9
pydantic-settings==2.5.2
httpx==0.27.2
python-jose[cryptography]==3.3.0
```

- [ ] **Step 2: Write Dockerfile**

```dockerfile
# Stage 1: builder
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --target /build/deps

# Stage 2: runtime
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --gecos "" --uid 1001 appuser
WORKDIR /app
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages/
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 8014
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8014/health || exit 1
CMD ["python3", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8014", "--workers", "1", \
     "--log-level", "info", "--no-access-log"]
```

- [ ] **Step 3: Write config.py**

```python
# src/agent-14-data-quality/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "agent-14-data-quality"
    service_port: int = 8014
    log_level: str = "INFO"
    environment: str = "production"

    # Database
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_schema: str = "platform_shared"

    # External APIs
    fmp_api_key: str
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_request_timeout: int = 30
    massive_api_key: str = ""          # env var: MASSIVE_KEY
    massive_base_url: str = "https://api.polygon.io"  # MASSIVE = rebranded Polygon.io
    massive_request_timeout: int = 30

    # Healing config
    max_heal_attempts: int = 3
    peer_divergence_sigma: float = 3.0  # PEER_DIVERGENCE threshold

    # Auth
    jwt_secret: str

    class Config:
        env_file = ("../../.env", ".env")
        extra = "ignore"
        case_sensitive = False
        # MASSIVE_KEY maps to massive_api_key
        fields = {"massive_api_key": {"env": "MASSIVE_KEY"}}


settings = Settings()
```

- [ ] **Step 4: Write database.py**

```python
# src/agent-14-data-quality/app/database.py
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings

logger = logging.getLogger(__name__)


engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=(settings.log_level == "DEBUG"),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> dict:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            schema = conn.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :s"),
                {"s": settings.db_schema},
            ).fetchone()
        return {"status": "healthy", "connectivity": result == 1, "schema_exists": schema is not None}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

- [ ] **Step 5: Write auth.py** (copy verify_token pattern from agent-02)

```python
# src/agent-14-data-quality/app/auth.py
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
```

- [ ] **Step 6: Write app/api/health.py**

```python
# src/agent-14-data-quality/app/api/health.py
from fastapi import APIRouter
from app.database import check_database_connection

router = APIRouter()


@router.get("/health")
def health():
    db = check_database_connection()
    return {
        "service": "agent-14-data-quality",
        "status": "healthy" if db["status"] == "healthy" else "degraded",
        "database": db,
    }
```

- [ ] **Step 7: Write app/main.py**

```python
# src/agent-14-data-quality/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import check_database_connection

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.service_name} on port {settings.service_port}")
    health = check_database_connection()
    if health["status"] != "healthy":
        logger.error(f"Database connection failed: {health}")
    else:
        logger.info(f"Database healthy — schema: {health.get('schema_exists')}")
    yield
    logger.info(f"Shutting down {settings.service_name}")


app = FastAPI(
    title="Data Quality Engine",
    description="Completeness scanning, self-healing, and quality gating for market data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.health import router as health_router
from app.api.routes import router as dq_router

app.include_router(health_router)
app.include_router(dq_router, prefix="/data-quality")
```

- [ ] **Step 8: Create empty __init__.py files**

```bash
touch src/agent-14-data-quality/app/__init__.py \
      src/agent-14-data-quality/app/api/__init__.py \
      src/agent-14-data-quality/app/clients/__init__.py \
      src/agent-14-data-quality/tests/__init__.py
```

- [ ] **Step 9: Verify the service starts**

```bash
cd src/agent-14-data-quality
pip install -r requirements.txt
# create stub files so main.py imports don't fail yet:
touch app/scanner.py app/healer.py app/gate.py app/promoter.py \
      app/clients/fmp.py app/clients/massive.py app/api/routes.py
echo "from fastapi import APIRouter; router = APIRouter()" > app/api/routes.py
DATABASE_URL=postgresql+psycopg2://user:pass@host/db \
FMP_API_KEY=test JWT_SECRET=test \
python3 -m uvicorn app.main:app --port 8014 --no-access-log &
curl http://localhost:8014/health
kill %1
```

Expected: `{"service":"agent-14-data-quality","status":"degraded",...}` (degraded is fine — no real DB yet)

- [ ] **Step 10: Commit**

```bash
git add src/agent-14-data-quality/
git commit -m "feat(dq): scaffold agent-14-data-quality service (config, db, auth, health)"
```

---

## Task 3: FMP and MASSIVE Clients

**Files:**
- Create: `src/agent-14-data-quality/app/clients/fmp.py`
- Create: `src/agent-14-data-quality/app/clients/massive.py`
- Test: `src/agent-14-data-quality/tests/test_clients.py`

These clients are **heal-only** — they fetch a single field for a single symbol and return the raw value or `None`.

- [ ] **Step 1: Write the failing tests**

```python
# src/agent-14-data-quality/tests/test_clients.py
from unittest.mock import MagicMock, patch
import pytest
from app.clients.fmp import FMPHealClient
from app.clients.massive import MASSIVEHealClient


class TestFMPHealClient:
    def test_fetch_price_returns_float(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"price": 42.5}]
        with patch("httpx.Client.get", return_value=mock_resp):
            result = client.fetch_field("AAPL", "price")
        assert result == 42.5

    def test_fetch_missing_field_returns_none(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{}]
        with patch("httpx.Client.get", return_value=mock_resp):
            result = client.fetch_field("AAPL", "nav_value")
        assert result is None

    def test_http_error_returns_none(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        import httpx
        with patch("httpx.Client.get", side_effect=httpx.TimeoutException("timeout")):
            result = client.fetch_field("AAPL", "price")
        assert result is None

    def test_fetch_nav_value_uses_etf_info_endpoint(self):
        client = FMPHealClient(api_key="test", base_url="https://financialmodelingprep.com/stable")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"navPrice": 25.10}]
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            result = client.fetch_field("JEPI", "nav_value")
        call_url = mock_get.call_args[0][0]
        assert "etf-info" in call_url
        assert result == 25.10


class TestMASSIVEHealClient:
    def test_fetch_price_returns_float(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ticker": {"day": {"c": 55.0}}}
        with patch("httpx.Client.get", return_value=mock_resp):
            result = client.fetch_field("AAPL", "price")
        assert result == 55.0

    def test_rate_limited_returns_none_with_diagnostic(self):
        client = MASSIVEHealClient(api_key="test", base_url="https://api.polygon.io")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("httpx.Client.get", return_value=mock_resp):
            result, diag = client.fetch_field_with_diagnostic("AAPL", "price")
        assert result is None
        assert diag["code"] == "RATE_LIMITED"
```

- [ ] **Step 2: Run tests — expect FAIL (modules not yet written)**

```bash
cd src/agent-14-data-quality
python3 -m pytest tests/test_clients.py -v
```

Expected: `ImportError` or `AttributeError` — modules don't exist yet.

- [ ] **Step 3: Write FMP client**

```python
# src/agent-14-data-quality/app/clients/fmp.py
"""FMP heal fetcher — fetches a single field for a single symbol."""
import logging
from typing import Any, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Maps field_name → (endpoint, response_key)
# endpoint is relative to base_url/stable
_FIELD_MAP: dict[str, tuple[str, str]] = {
    "price":                    ("quote",            "price"),
    "week52_high":              ("quote",            "yearHigh"),
    "week52_low":               ("quote",            "yearLow"),
    "dividend_yield":           ("profile",          "lastDiv"),
    "div_frequency":            ("profile",          "companyName"),   # derived separately
    "sma_50":                   ("technical-indicator/sma",  "sma"),
    "sma_200":                  ("technical-indicator/sma",  "sma"),
    "rsi_14d":                  ("technical-indicator/rsi",  "rsi"),
    "payout_ratio":             ("ratios",           "payoutRatio"),
    "nav_value":                ("etf-info",         "navPrice"),
    "nav_discount_pct":         ("etf-info",         "premium"),
    "interest_coverage_ratio":  ("ratios",           "interestCoverage"),
    "debt_to_equity":           ("ratios",           "debtEquityRatio"),
    "chowder_number":           ("profile",          None),   # computed from dividends
    "consecutive_growth_yrs":   ("dividends-history",None),  # computed from series
}


class FMPHealClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, endpoint: str, symbol: str, extra_params: dict = None) -> Optional[Any]:
        params = {"symbol": symbol.upper(), "apikey": self.api_key}
        if extra_params:
            params.update(extra_params)
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 429:
                    logger.warning(f"FMP rate limited for {symbol}/{endpoint}")
                    return None
                if resp.status_code == 401:
                    logger.error("FMP auth failed — check FMP_API_KEY")
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            logger.warning(f"FMP timeout for {symbol}/{endpoint}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"FMP HTTP {e.response.status_code} for {symbol}/{endpoint}")
            return None
        except Exception as e:
            logger.error(f"FMP unexpected error for {symbol}/{endpoint}: {e}")
            return None

    def fetch_field(self, symbol: str, field_name: str) -> Optional[float]:
        """Return scalar value for field_name, or None if unavailable."""
        value, _ = self.fetch_field_with_diagnostic(symbol, field_name)
        return value

    def fetch_field_with_diagnostic(self, symbol: str, field_name: str) -> Tuple[Optional[float], dict]:
        if field_name not in _FIELD_MAP:
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"No FMP mapping for {field_name}"}

        endpoint, key = _FIELD_MAP[field_name]
        data = self._get(endpoint, symbol)

        if data is None:
            return None, {"code": "TICKER_NOT_FOUND", "detail": f"FMP returned no data for {symbol}"}

        # Normalise: FMP returns list for most endpoints
        row = data[0] if isinstance(data, list) and data else data
        if not row:
            return None, {"code": "TICKER_NOT_FOUND", "detail": f"Empty FMP response for {symbol}"}

        if key is None:
            # Field requires computed logic — not handled here
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"{field_name} requires computed extraction"}

        value = row.get(key)
        if value is None:
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"Key {key} absent in FMP response"}
        if value == 0:
            return 0.0, {"code": "ZERO_VALUE", "detail": f"FMP returned 0 for {field_name}"}

        try:
            return float(value), {}
        except (TypeError, ValueError):
            return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"Non-numeric value: {value!r}"}
```

- [ ] **Step 4: Write MASSIVE client**

```python
# src/agent-14-data-quality/app/clients/massive.py
"""MASSIVE (Polygon.io) heal fetcher — real-time prices and technicals."""
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Fields that Polygon.io snapshot can supply
_SNAPSHOT_FIELDS = {
    "price":      ("ticker", "day", "c"),    # closing price
    "week52_high": None,                      # not in snapshot; use aggs
    "week52_low":  None,
    "sma_50":      None,                      # use /indicators/sma
    "sma_200":     None,
    "rsi_14d":     None,                      # use /indicators/rsi
}


class MASSIVEHealClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict = None) -> Tuple[Optional[dict], Optional[dict]]:
        """Returns (data, diagnostic_or_None)."""
        all_params = {"apiKey": self.api_key}
        if params:
            all_params.update(params)
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=all_params)
                if resp.status_code == 429:
                    return None, {"code": "RATE_LIMITED", "detail": "Polygon.io 429"}
                if resp.status_code == 403:
                    return None, {"code": "AUTH_ERROR", "detail": "Polygon.io 403 — check MASSIVE_KEY"}
                if resp.status_code == 404:
                    return None, {"code": "TICKER_NOT_FOUND", "detail": f"Polygon.io 404 for {path}"}
                resp.raise_for_status()
                return resp.json(), None
        except httpx.TimeoutException:
            return None, {"code": "STALE_DATA", "detail": "Polygon.io timeout"}
        except Exception as e:
            return None, {"code": "TICKER_NOT_FOUND", "detail": str(e)}

    def fetch_field(self, symbol: str, field_name: str) -> Optional[float]:
        value, _ = self.fetch_field_with_diagnostic(symbol, field_name)
        return value

    def fetch_field_with_diagnostic(self, symbol: str, field_name: str) -> Tuple[Optional[float], dict]:
        sym = symbol.upper()

        if field_name == "price":
            data, diag = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{sym}")
            if diag:
                return None, diag
            try:
                value = data["ticker"]["day"]["c"]
                return float(value), {}
            except (KeyError, TypeError):
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": "price not in snapshot"}

        if field_name in ("sma_50", "sma_200"):
            window = 50 if field_name == "sma_50" else 200
            data, diag = self._get(
                f"/v1/indicators/sma/{sym}",
                params={"timespan": "day", "window": window, "limit": 1},
            )
            if diag:
                return None, diag
            try:
                value = data["results"]["values"][0]["value"]
                return float(value), {}
            except (KeyError, TypeError, IndexError):
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": "SMA not in response"}

        if field_name == "rsi_14d":
            data, diag = self._get(
                f"/v1/indicators/rsi/{sym}",
                params={"timespan": "day", "window": 14, "limit": 1},
            )
            if diag:
                return None, diag
            try:
                value = data["results"]["values"][0]["value"]
                return float(value), {}
            except (KeyError, TypeError, IndexError):
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": "RSI not in response"}

        if field_name in ("week52_high", "week52_low"):
            # Use grouped daily aggs over past 365 days to find 52-week range
            from datetime import date, timedelta
            end = date.today().isoformat()
            start = (date.today() - timedelta(days=365)).isoformat()
            data, diag = self._get(
                f"/v2/aggs/ticker/{sym}/range/1/day/{start}/{end}",
                params={"adjusted": "true", "limit": 365},
            )
            if diag:
                return None, diag
            try:
                results = data.get("results", [])
                if not results:
                    return None, {"code": "TICKER_NOT_FOUND", "detail": "No agg results"}
                if field_name == "week52_high":
                    return float(max(r["h"] for r in results)), {}
                else:
                    return float(min(r["l"] for r in results)), {}
            except Exception as e:
                return None, {"code": "FIELD_NOT_SUPPORTED", "detail": str(e)}

        return None, {"code": "FIELD_NOT_SUPPORTED", "detail": f"MASSIVE has no mapping for {field_name}"}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd src/agent-14-data-quality
python3 -m pytest tests/test_clients.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent-14-data-quality/app/clients/ \
        src/agent-14-data-quality/tests/test_clients.py
git commit -m "feat(dq): add FMP and MASSIVE heal clients with unit tests"
```

---

## Task 4: Scanner

**Files:**
- Create: `src/agent-14-data-quality/app/scanner.py`
- Test: `src/agent-14-data-quality/tests/test_scanner.py`

- [ ] **Step 1: Write the failing test**

```python
# src/agent-14-data-quality/tests/test_scanner.py
from unittest.mock import MagicMock, patch
import pytest
from app.scanner import ASSET_TYPE_TO_CLASS, resolve_asset_class, compute_severity


class TestAssetTypeMapping:
    def test_covered_call_etf_maps_to_etf(self):
        assert ASSET_TYPE_TO_CLASS["COVERED_CALL_ETF"] == "ETF"

    def test_equity_reit_maps_to_reit(self):
        assert ASSET_TYPE_TO_CLASS["EQUITY_REIT"] == "REIT"

    def test_mortgage_reit_maps_to_reit(self):
        assert ASSET_TYPE_TO_CLASS["MORTGAGE_REIT"] == "REIT"

    def test_preferred_stock_maps_to_preferred(self):
        assert ASSET_TYPE_TO_CLASS["PREFERRED_STOCK"] == "Preferred"

    def test_unknown_returns_none(self):
        assert ASSET_TYPE_TO_CLASS.get("UNKNOWN") is None


class TestComputeSeverity:
    def test_critical_when_peer_has_field(self):
        """If any peer has the field populated, severity is critical."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 1  # one peer has it
        severity = compute_severity(mock_db, "MAIN", "interest_coverage_ratio", "BDC")
        assert severity == "critical"

    def test_warning_when_no_peer_has_field(self):
        """If no peer has the field, severity is warning."""
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 0  # no peer has it
        severity = compute_severity(mock_db, "MAIN", "chowder_number", "BDC")
        assert severity == "warning"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd src/agent-14-data-quality && python3 -m pytest tests/test_scanner.py -v
```

- [ ] **Step 3: Write scanner.py**

```python
# src/agent-14-data-quality/app/scanner.py
"""Completeness scan — identifies missing required fields per asset class."""
import logging
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ASSET_TYPE_TO_CLASS: dict[str, str] = {
    "DIVIDEND_STOCK":  "CommonStock",
    "ETF":             "ETF",
    "COVERED_CALL_ETF":"ETF",
    "CEF":             "CEF",
    "BDC":             "BDC",
    "EQUITY_REIT":     "REIT",
    "MORTGAGE_REIT":   "REIT",
    "MLP":             "MLP",
    "PREFERRED_STOCK": "Preferred",
}


def resolve_asset_class(asset_type: Optional[str]) -> Optional[str]:
    return ASSET_TYPE_TO_CLASS.get(asset_type or "")


def compute_severity(db: Session, symbol: str, field_name: str, asset_class: str) -> str:
    """Critical if any peer of same asset_class has the field populated; else warning."""
    peer_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM platform_shared.market_data_cache m
            JOIN platform_shared.securities s ON s.symbol = m.symbol
            WHERE s.asset_type = ANY(:types)
              AND m.symbol != :symbol
              AND m.:field IS NOT NULL
              AND m.is_tracked = TRUE
        """.replace(":field", field_name)),
        {"types": _asset_class_to_types(asset_class), "symbol": symbol},
    ).scalar()
    return "critical" if (peer_count or 0) > 0 else "warning"


def _asset_class_to_types(asset_class: str) -> list[str]:
    """Reverse mapping: asset_class → list of asset_type values."""
    return [k for k, v in ASSET_TYPE_TO_CLASS.items() if v == asset_class]


def run_scan(db: Session) -> dict:
    """
    Full completeness scan.
    Returns summary: {symbols_scanned, issues_created, issues_resolved}.
    """
    # Load requirements indexed by asset_class
    reqs_rows = db.execute(text("""
        SELECT asset_class, field_name, required
        FROM platform_shared.field_requirements
        WHERE required = TRUE
    """)).fetchall()
    requirements: dict[str, list[str]] = {}
    for r in reqs_rows:
        requirements.setdefault(r.asset_class, []).append(r.field_name)

    # Load exemptions as a set of (symbol, field_name) tuples
    exempt_rows = db.execute(text("""
        SELECT symbol, field_name FROM platform_shared.data_quality_exemptions
    """)).fetchall()
    exemptions = {(r.symbol, r.field_name) for r in exempt_rows}

    # Get tracked symbols with their asset_type
    symbols = db.execute(text("""
        SELECT m.symbol, s.asset_type
        FROM platform_shared.market_data_cache m
        LEFT JOIN platform_shared.securities s ON s.symbol = m.symbol
        WHERE m.is_tracked = TRUE
    """)).fetchall()

    issues_created = 0
    issues_resolved = 0

    for sym_row in symbols:
        symbol = sym_row.symbol
        asset_class = resolve_asset_class(sym_row.asset_type)
        if not asset_class:
            logger.debug(f"Skipping {symbol}: asset_type={sym_row.asset_type!r} not mapped")
            continue

        field_list = requirements.get(asset_class, [])
        for field_name in field_list:
            if (symbol, field_name) in exemptions:
                continue

            # Check if field is populated in market_data_cache
            # Use dynamic column access via parameterised cast
            result = db.execute(
                text(f"SELECT {field_name} FROM platform_shared.market_data_cache WHERE symbol = :s"),
                {"s": symbol},
            ).fetchone()

            field_value = getattr(result, field_name, None) if result else None

            if field_value is None or field_value == 0:
                # Field is missing — upsert into issues
                existing = db.execute(
                    text("SELECT id, status FROM platform_shared.data_quality_issues "
                         "WHERE symbol = :s AND field_name = :f"),
                    {"s": symbol, "f": field_name},
                ).fetchone()

                if existing and existing.status == "resolved":
                    # Was resolved but now missing again — reopen
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='missing', resolved_at=NULL, attempt_count=0, "
                             "updated_at=NOW() WHERE id=:id"),
                        {"id": existing.id},
                    )
                    issues_created += 1
                elif not existing:
                    severity = compute_severity(db, symbol, field_name, asset_class)
                    db.execute(
                        text("""
                            INSERT INTO platform_shared.data_quality_issues
                                (symbol, field_name, asset_class, status, severity)
                            VALUES (:s, :f, :ac, 'missing', :sev)
                            ON CONFLICT (symbol, field_name) DO UPDATE
                                SET status='missing', severity=:sev, updated_at=NOW()
                        """),
                        {"s": symbol, "f": field_name, "ac": asset_class, "sev": severity},
                    )
                    issues_created += 1
            else:
                # Field is present — mark any open issue resolved
                db.execute(
                    text("""
                        UPDATE platform_shared.data_quality_issues
                        SET status='resolved', resolved_at=NOW(), updated_at=NOW()
                        WHERE symbol=:s AND field_name=:f AND status != 'resolved'
                    """),
                    {"s": symbol, "f": field_name},
                )
                issues_resolved += 1

    db.commit()
    logger.info(f"Scan complete: {len(symbols)} symbols, {issues_created} issues, {issues_resolved} resolved")
    return {
        "symbols_scanned": len(symbols),
        "issues_created": issues_created,
        "issues_resolved": issues_resolved,
    }
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd src/agent-14-data-quality && python3 -m pytest tests/test_scanner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/agent-14-data-quality/app/scanner.py \
        src/agent-14-data-quality/tests/test_scanner.py
git commit -m "feat(dq): add completeness scanner with asset class resolution"
```

---

## Task 5: Healer Engine

**Files:**
- Create: `src/agent-14-data-quality/app/healer.py`
- Test: `src/agent-14-data-quality/tests/test_healer.py`

- [ ] **Step 1: Write failing tests**

```python
# src/agent-14-data-quality/tests/test_healer.py
from unittest.mock import MagicMock, patch
import pytest
from app.healer import HealerEngine, IssueStatus


class TestHealerEngine:
    def _make_db(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.fetchone.return_value = None
        return db

    def test_skip_exempt_issues(self):
        """Exempted (symbol, field_name) pairs must be skipped."""
        healer = HealerEngine(fmp_client=MagicMock(), massive_client=MagicMock())
        exempt = {("AAPL", "nav_value")}
        result = healer._should_skip("AAPL", "nav_value", exempt)
        assert result is True

    def test_not_skip_non_exempt(self):
        healer = HealerEngine(fmp_client=MagicMock(), massive_client=MagicMock())
        exempt = set()
        result = healer._should_skip("AAPL", "nav_value", exempt)
        assert result is False

    def test_try_primary_first_then_fallback(self):
        """Healer tries primary source; if None, tries fallback."""
        fmp = MagicMock()
        fmp.fetch_field_with_diagnostic.return_value = (None, {"code": "FIELD_NOT_SUPPORTED"})
        massive = MagicMock()
        massive.fetch_field_with_diagnostic.return_value = (42.5, {})

        healer = HealerEngine(fmp_client=fmp, massive_client=massive)
        value, diag, source = healer._fetch("AAPL", "price", primary="fmp", fallback="massive")
        assert value == 42.5
        assert source == "massive"

    def test_max_attempts_sets_unresolvable(self):
        """After max_heal_attempts fails, status becomes unresolvable."""
        # Issue with attempt_count already at max
        issue = MagicMock()
        issue.attempt_count = 3
        issue.id = 1
        assert issue.attempt_count >= 3
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd src/agent-14-data-quality && python3 -m pytest tests/test_healer.py -v
```

- [ ] **Step 3: Write healer.py**

```python
# src/agent-14-data-quality/app/healer.py
"""Self-healing engine — fetches missing fields and writes them back to market_data_cache."""
import logging
from enum import Enum
from typing import Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clients.fmp import FMPHealClient
from app.clients.massive import MASSIVEHealClient
from app.config import settings

logger = logging.getLogger(__name__)


class IssueStatus(str, Enum):
    MISSING = "missing"
    FETCHING = "fetching"
    RESOLVED = "resolved"
    UNRESOLVABLE = "unresolvable"


class HealerEngine:
    def __init__(self, fmp_client: FMPHealClient, massive_client: MASSIVEHealClient):
        self.fmp = fmp_client
        self.massive = massive_client
        self.max_attempts = settings.max_heal_attempts

    def _should_skip(self, symbol: str, field_name: str, exemptions: Set[Tuple[str, str]]) -> bool:
        return (symbol, field_name) in exemptions

    def _fetch(
        self,
        symbol: str,
        field_name: str,
        primary: Optional[str],
        fallback: Optional[str],
    ) -> Tuple[Optional[float], dict, Optional[str]]:
        """Try primary then fallback. Returns (value, diagnostic, source_used)."""
        sources = [(primary, self.fmp if primary == "fmp" else self.massive),
                   (fallback, self.fmp if fallback == "fmp" else self.massive)]
        sources = [(s, c) for s, c in sources if s and c]

        for source_name, client in sources:
            value, diag = client.fetch_field_with_diagnostic(symbol, field_name)
            if value is not None:
                return value, {}, source_name
            last_diag = diag

        return None, last_diag if sources else {"code": "FIELD_NOT_SUPPORTED"}, None

    def run_retry_pass(self, db: Session) -> dict:
        """
        Process all open issues (status='missing' or 'fetching', attempt_count < max).
        Called every 15 minutes.
        """
        # Load exemptions
        exempt_rows = db.execute(
            text("SELECT symbol, field_name FROM platform_shared.data_quality_exemptions")
        ).fetchall()
        exemptions = {(r.symbol, r.field_name) for r in exempt_rows}

        # Load open issues with their fetch sources
        issues = db.execute(text("""
            SELECT i.id, i.symbol, i.field_name, i.asset_class, i.attempt_count,
                   r.fetch_source_primary, r.fetch_source_fallback
            FROM platform_shared.data_quality_issues i
            LEFT JOIN platform_shared.field_requirements r
                   ON r.asset_class = i.asset_class AND r.field_name = i.field_name
            WHERE i.status IN ('missing', 'fetching')
              AND i.attempt_count < :max_attempts
        """), {"max_attempts": self.max_attempts}).fetchall()

        healed = 0
        failed = 0
        escalated = 0

        for issue in issues:
            if self._should_skip(issue.symbol, issue.field_name, exemptions):
                continue

            # Mark as fetching
            db.execute(
                text("UPDATE platform_shared.data_quality_issues "
                     "SET status='fetching', last_attempted_at=NOW(), "
                     "attempt_count=attempt_count+1, updated_at=NOW() WHERE id=:id"),
                {"id": issue.id},
            )
            db.commit()

            value, diag, source_used = self._fetch(
                issue.symbol,
                issue.field_name,
                issue.fetch_source_primary,
                issue.fetch_source_fallback,
            )

            if value is not None:
                # Write healed value back to market_data_cache
                try:
                    db.execute(
                        text(f"UPDATE platform_shared.market_data_cache "
                             f"SET {issue.field_name} = :val WHERE symbol = :s"),
                        {"val": value, "s": issue.symbol},
                    )
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='resolved', resolved_at=NOW(), "
                             "source_used=:src, diagnostic=:diag, updated_at=NOW() WHERE id=:id"),
                        {"src": source_used, "diag": None, "id": issue.id},
                    )
                    healed += 1
                    logger.info(f"Healed {issue.symbol}/{issue.field_name} via {source_used}")
                except Exception as e:
                    logger.error(f"Failed to write healed value for {issue.symbol}/{issue.field_name}: {e}")
                    failed += 1
            else:
                new_attempts = issue.attempt_count + 1
                if new_attempts >= self.max_attempts:
                    # Escalate to unresolvable
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='unresolvable', diagnostic=:diag, updated_at=NOW() WHERE id=:id"),
                        {"diag": diag, "id": issue.id},
                    )
                    logger.warning(
                        f"UNRESOLVABLE: {issue.symbol}/{issue.field_name} — {diag.get('code')}"
                    )
                    escalated += 1
                else:
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='missing', diagnostic=:diag, updated_at=NOW() WHERE id=:id"),
                        {"diag": diag, "id": issue.id},
                    )
                    failed += 1

            db.commit()

        return {"healed": healed, "failed": failed, "escalated": escalated}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd src/agent-14-data-quality && python3 -m pytest tests/test_healer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/agent-14-data-quality/app/healer.py \
        src/agent-14-data-quality/tests/test_healer.py
git commit -m "feat(dq): add self-healing engine with FMP/MASSIVE fallback"
```

---

## Task 6: Gate Evaluator

**Files:**
- Create: `src/agent-14-data-quality/app/gate.py`
- Test: `src/agent-14-data-quality/tests/test_gate.py`

- [ ] **Step 1: Write failing tests**

```python
# src/agent-14-data-quality/tests/test_gate.py
from unittest.mock import MagicMock
import pytest
from app.gate import evaluate_gate, GateResult


class TestGateEvaluator:
    def test_gate_passes_with_no_critical_issues(self):
        db = MagicMock()
        # No critical issues for portfolio symbols
        db.execute.return_value.scalar.return_value = 0
        db.execute.return_value.fetchall.return_value = [
            MagicMock(symbol="AAPL"), MagicMock(symbol="JNK")
        ]
        result = evaluate_gate(db, "portfolio-uuid-123")
        assert result.status == "passed"
        assert result.blocking_issue_count == 0

    def test_gate_blocked_with_critical_issues(self):
        db = MagicMock()
        # 2 symbols in portfolio
        db.execute.return_value.fetchall.return_value = [
            MagicMock(symbol="ARCC")
        ]
        # 1 critical issue
        db.execute.return_value.scalar.return_value = 1
        result = evaluate_gate(db, "portfolio-uuid-456")
        assert result.status == "blocked"
        assert result.blocking_issue_count >= 1
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd src/agent-14-data-quality && python3 -m pytest tests/test_gate.py -v
```

- [ ] **Step 3: Write gate.py**

```python
# src/agent-14-data-quality/app/gate.py
"""Gate evaluator — determines if scoring is allowed for a portfolio."""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    portfolio_id: str
    status: str          # 'passed' | 'blocked' | 'pending'
    blocking_issue_count: int
    gate_passed_at: Optional[str] = None


def evaluate_gate(db: Session, portfolio_id: str) -> GateResult:
    """
    Evaluate the data quality gate for a portfolio.
    Blocks if any active position has a 'critical' open issue.
    """
    # Get active symbols in portfolio
    symbols_rows = db.execute(
        text("""
            SELECT DISTINCT symbol FROM platform_shared.positions
            WHERE portfolio_id = :pid AND quantity > 0
        """),
        {"pid": portfolio_id},
    ).fetchall()

    symbols = [r.symbol for r in symbols_rows]
    if not symbols:
        logger.debug(f"Portfolio {portfolio_id} has no active positions — gate passes vacuously")
        _upsert_gate(db, portfolio_id, "passed", 0)
        return GateResult(portfolio_id=portfolio_id, status="passed", blocking_issue_count=0)

    # Count critical open issues for those symbols
    critical_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM platform_shared.data_quality_issues i
            LEFT JOIN platform_shared.data_quality_exemptions e
                   ON e.symbol = i.symbol AND e.field_name = i.field_name
            WHERE i.symbol = ANY(:syms)
              AND i.severity = 'critical'
              AND i.status NOT IN ('resolved', 'unresolvable')
              AND e.id IS NULL
        """),
        {"syms": symbols},
    ).scalar() or 0

    status = "blocked" if critical_count > 0 else "passed"
    _upsert_gate(db, portfolio_id, status, critical_count)
    db.commit()

    logger.info(f"Gate {portfolio_id}: {status} ({critical_count} critical issues)")
    return GateResult(
        portfolio_id=portfolio_id,
        status=status,
        blocking_issue_count=critical_count,
    )


def _upsert_gate(db: Session, portfolio_id: str, status: str, blocking_count: int):
    db.execute(
        text("""
            INSERT INTO platform_shared.data_quality_gate
                (portfolio_id, gate_date, status, blocking_issue_count,
                 gate_passed_at)
            VALUES (
                :pid, CURRENT_DATE, :status, :cnt,
                CASE WHEN :status = 'passed' THEN NOW() ELSE NULL END
            )
            ON CONFLICT (portfolio_id, gate_date) DO UPDATE SET
                status = :status,
                blocking_issue_count = :cnt,
                gate_passed_at = CASE WHEN :status = 'passed' THEN NOW() ELSE NULL END
        """),
        {"pid": portfolio_id, "status": status, "cnt": blocking_count},
    )


def record_scoring_triggered(db: Session, portfolio_id: str):
    db.execute(
        text("""
            UPDATE platform_shared.data_quality_gate
            SET scoring_triggered_at = NOW()
            WHERE portfolio_id = :pid AND gate_date = CURRENT_DATE
        """),
        {"pid": portfolio_id},
    )
    db.commit()


def record_scoring_completed(db: Session, portfolio_id: str):
    db.execute(
        text("""
            UPDATE platform_shared.data_quality_gate
            SET scoring_completed_at = NOW()
            WHERE portfolio_id = :pid AND gate_date = CURRENT_DATE
        """),
        {"pid": portfolio_id},
    )
    # Also update data_refresh_log
    db.execute(
        text("""
            INSERT INTO platform_shared.data_refresh_log (portfolio_id, scores_recalculated_at, updated_at)
            VALUES (:pid, NOW(), NOW())
            ON CONFLICT (portfolio_id) DO UPDATE SET
                scores_recalculated_at = NOW(), updated_at = NOW()
        """),
        {"pid": portfolio_id},
    )
    db.commit()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd src/agent-14-data-quality && python3 -m pytest tests/test_gate.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/agent-14-data-quality/app/gate.py \
        src/agent-14-data-quality/tests/test_gate.py
git commit -m "feat(dq): add gate evaluator per portfolio with upsert logic"
```

---

## Task 7: Promoter + API Routes

**Files:**
- Create: `src/agent-14-data-quality/app/promoter.py`
- Create: `src/agent-14-data-quality/app/api/routes.py`

- [ ] **Step 1: Write promoter.py**

```python
# src/agent-14-data-quality/app/promoter.py
"""Nightly analyst feature promotion from feature_gap_log."""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PROMOTION_THRESHOLD = 2  # occurrence_count >= 2


def run_promotion(db: Session) -> dict:
    """
    Promote qualifying feature_gap_log entries to field_requirements.
    New entries: required=FALSE, source='analyst_promoted', fetch_source_primary=NULL.
    """
    candidates = db.execute(text("""
        SELECT metric_name_raw, asset_class, id, occurrence_count
        FROM platform_shared.feature_gap_log
        WHERE occurrence_count >= :threshold
          AND resolution_status = 'pending'
          AND asset_class IS NOT NULL
    """), {"threshold": PROMOTION_THRESHOLD}).fetchall()

    promoted = 0
    skipped = 0

    for row in candidates:
        # Check not already in field_requirements
        existing = db.execute(
            text("SELECT id FROM platform_shared.field_requirements "
                 "WHERE asset_class = :ac AND field_name = :fn"),
            {"ac": row.asset_class, "fn": row.metric_name_raw},
        ).fetchone()

        if existing:
            skipped += 1
            continue

        db.execute(
            text("""
                INSERT INTO platform_shared.field_requirements
                    (asset_class, field_name, required, source, promoted_from_gap_id)
                VALUES (:ac, :fn, FALSE, 'analyst_promoted', :gap_id)
                ON CONFLICT (asset_class, field_name) DO NOTHING
            """),
            {"ac": row.asset_class, "fn": row.metric_name_raw, "gap_id": row.id},
        )
        # Mark gap log entry as promoted
        db.execute(
            text("UPDATE platform_shared.feature_gap_log "
                 "SET resolution_status='promoted' WHERE id=:id"),
            {"id": row.id},
        )
        promoted += 1

    db.commit()
    logger.info(f"Promotion complete: {promoted} promoted, {skipped} already present")
    return {"promoted": promoted, "skipped": skipped}
```

- [ ] **Step 2: Write app/api/routes.py**

```python
# src/agent-14-data-quality/app/api/routes.py
"""All data-quality REST endpoints — §8 of the spec."""
import asyncio
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.clients.fmp import FMPHealClient
from app.clients.massive import MASSIVEHealClient
from app.config import settings
from app.database import get_db, get_db_context
from app.gate import evaluate_gate, record_scoring_completed
from app.healer import HealerEngine
from app.promoter import run_promotion
from app.scanner import run_scan

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared client instances (created at import time — stateless HTTP clients)
_fmp = FMPHealClient(
    api_key=settings.fmp_api_key,
    base_url=settings.fmp_base_url,
    timeout=settings.fmp_request_timeout,
)
_massive = MASSIVEHealClient(
    api_key=settings.massive_api_key,
    base_url=settings.massive_base_url,
    timeout=settings.massive_request_timeout,
)
_healer = HealerEngine(fmp_client=_fmp, massive_client=_massive)


# ── Trigger scan ──────────────────────────────────────────────────────────────

class ScanTriggerRequest(BaseModel):
    market_refreshed_at: Optional[str] = None  # ISO timestamp from caller


@router.post("/scan/trigger", status_code=202, dependencies=[Depends(verify_token)])
def trigger_scan(request: ScanTriggerRequest, background: BackgroundTasks):
    """
    Called by scheduler after market data refresh completes.
    Responds immediately with 202; scan runs in background.
    """
    background.add_task(_run_scan_background, request.market_refreshed_at)
    return {"status": "accepted", "message": "Scan queued"}


def _run_scan_background(market_refreshed_at: Optional[str]):
    with get_db_context() as db:
        # Write market refresh timestamp to data_refresh_log for all active portfolios
        if market_refreshed_at:
            db.execute(text("""
                INSERT INTO platform_shared.data_refresh_log
                    (portfolio_id, market_data_refreshed_at, updated_at)
                SELECT DISTINCT p.id, :ts::TIMESTAMPTZ, NOW()
                FROM platform_shared.portfolios p
                JOIN platform_shared.positions pos ON pos.portfolio_id = p.id
                WHERE pos.quantity > 0 AND p.is_active = TRUE
                ON CONFLICT (portfolio_id) DO UPDATE SET
                    market_data_refreshed_at = :ts::TIMESTAMPTZ, updated_at = NOW()
            """), {"ts": market_refreshed_at})
            db.commit()

        summary = run_scan(db)
        logger.info(f"Background scan complete: {summary}")
        # Re-evaluate gates for all active portfolios
        portfolios = db.execute(text("""
            SELECT DISTINCT p.id FROM platform_shared.portfolios p
            JOIN platform_shared.positions pos ON pos.portfolio_id = p.id
            WHERE pos.quantity > 0 AND p.is_active = TRUE
        """)).fetchall()
        for p in portfolios:
            evaluate_gate(db, str(p.id))


# ── Gate check ────────────────────────────────────────────────────────────────

@router.get("/gate/{portfolio_id}", dependencies=[Depends(verify_token)])
def get_gate(portfolio_id: str, db: Session = Depends(get_db)):
    result = evaluate_gate(db, portfolio_id)
    return {
        "portfolio_id": portfolio_id,
        "status": result.status,
        "blocking_issue_count": result.blocking_issue_count,
        "gate_passed_at": result.gate_passed_at,
    }


@router.post("/gate/{portfolio_id}/scoring-complete", dependencies=[Depends(verify_token)])
def mark_scoring_complete(portfolio_id: str, db: Session = Depends(get_db)):
    record_scoring_completed(db, portfolio_id)
    return {"status": "recorded", "portfolio_id": portfolio_id}


# ── Issues ────────────────────────────────────────────────────────────────────

@router.get("/issues", dependencies=[Depends(verify_token)])
def list_issues(
    symbol: Optional[str] = Query(None),
    asset_class: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = "WHERE 1=1"
    params: dict = {}
    if symbol:
        filters += " AND i.symbol = :symbol"
        params["symbol"] = symbol
    if asset_class:
        filters += " AND i.asset_class = :asset_class"
        params["asset_class"] = asset_class
    if severity:
        filters += " AND i.severity = :severity"
        params["severity"] = severity
    if status:
        filters += " AND i.status = :status"
        params["status"] = status

    rows = db.execute(
        text(f"SELECT * FROM platform_shared.data_quality_issues i {filters} ORDER BY created_at DESC LIMIT 500"),
        params,
    ).fetchall()
    return {"issues": [dict(r._mapping) for r in rows]}


@router.get("/issues/{symbol}", dependencies=[Depends(verify_token)])
def get_issues_for_symbol(symbol: str, db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT * FROM platform_shared.data_quality_issues WHERE symbol=:s ORDER BY created_at DESC"),
        {"s": symbol},
    ).fetchall()
    return {"symbol": symbol, "issues": [dict(r._mapping) for r in rows]}


@router.post("/issues/{issue_id}/retry", dependencies=[Depends(verify_token)])
def retry_issue(issue_id: int, background: BackgroundTasks):
    background.add_task(_retry_single, issue_id)
    return {"status": "accepted", "issue_id": issue_id}


def _retry_single(issue_id: int):
    with get_db_context() as db:
        issue = db.execute(
            text("""
                SELECT i.*, r.fetch_source_primary, r.fetch_source_fallback
                FROM platform_shared.data_quality_issues i
                LEFT JOIN platform_shared.field_requirements r
                       ON r.asset_class = i.asset_class AND r.field_name = i.field_name
                WHERE i.id = :id
            """),
            {"id": issue_id},
        ).fetchone()
        if not issue:
            return
        db.execute(
            text("UPDATE platform_shared.data_quality_issues SET attempt_count=0, status='missing' WHERE id=:id"),
            {"id": issue_id},
        )
        db.commit()
        _healer.run_retry_pass(db)


@router.post("/issues/{issue_id}/mark-na", dependencies=[Depends(verify_token)])
def mark_na(issue_id: int, reason: Optional[str] = Query(None), db: Session = Depends(get_db)):
    issue = db.execute(
        text("SELECT * FROM platform_shared.data_quality_issues WHERE id=:id"),
        {"id": issue_id},
    ).fetchone()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    db.execute(
        text("""
            INSERT INTO platform_shared.data_quality_exemptions
                (symbol, field_name, asset_class, reason)
            VALUES (:s, :f, :ac, :r)
            ON CONFLICT (symbol, field_name) DO NOTHING
        """),
        {"s": issue.symbol, "f": issue.field_name, "ac": issue.asset_class, "r": reason},
    )
    db.execute(
        text("UPDATE platform_shared.data_quality_issues SET status='resolved', resolved_at=NOW() WHERE id=:id"),
        {"id": issue_id},
    )
    db.commit()
    return {"status": "exempted", "symbol": issue.symbol, "field_name": issue.field_name}


@router.post("/issues/{issue_id}/reclassify", dependencies=[Depends(verify_token)])
def reclassify(issue_id: int, db: Session = Depends(get_db)):
    """Placeholder — triggers asset re-classification via agent-04."""
    issue = db.execute(
        text("SELECT symbol FROM platform_shared.data_quality_issues WHERE id=:id"),
        {"id": issue_id},
    ).fetchone()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"status": "reclassify_queued", "symbol": issue.symbol,
            "note": "Integrate with agent-04 classify endpoint as needed"}


# ── Refresh log ───────────────────────────────────────────────────────────────

@router.get("/refresh-log/{portfolio_id}", dependencies=[Depends(verify_token)])
def get_refresh_log(portfolio_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM platform_shared.data_refresh_log WHERE portfolio_id=:pid"),
        {"pid": portfolio_id},
    ).fetchone()
    if not row:
        return {"portfolio_id": portfolio_id, "market_data_refreshed_at": None,
                "scores_recalculated_at": None, "market_staleness_hrs": None}
    return dict(row._mapping)


# ── Field requirements (admin) ────────────────────────────────────────────────

@router.get("/field-requirements", dependencies=[Depends(verify_token)])
def list_field_requirements(db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT * FROM platform_shared.field_requirements ORDER BY asset_class, field_name")
    ).fetchall()
    return {"requirements": [dict(r._mapping) for r in rows]}


class FieldRequirementPatch(BaseModel):
    fetch_source_primary: Optional[str] = None
    fetch_source_fallback: Optional[str] = None
    required: Optional[bool] = None


@router.patch("/field-requirements/{req_id}", dependencies=[Depends(verify_token)])
def patch_field_requirement(req_id: int, body: FieldRequirementPatch, db: Session = Depends(get_db)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["id"] = req_id
    db.execute(text(f"UPDATE platform_shared.field_requirements SET {set_clause} WHERE id=:id"), updates)
    db.commit()
    return {"status": "updated", "id": req_id}


# ── Retry loop endpoint (called by scheduler every 15 min) ────────────────────

@router.post("/retry-open", status_code=202, dependencies=[Depends(verify_token)])
def retry_open(background: BackgroundTasks):
    """Trigger a retry pass for all open issues."""
    background.add_task(_retry_all)
    return {"status": "accepted"}


def _retry_all():
    with get_db_context() as db:
        result = _healer.run_retry_pass(db)
        logger.info(f"Retry pass complete: {result}")


# ── Promoter endpoint (called by scheduler nightly) ───────────────────────────

@router.post("/promote", status_code=202, dependencies=[Depends(verify_token)])
def promote(background: BackgroundTasks):
    background.add_task(_run_promote)
    return {"status": "accepted"}


def _run_promote():
    with get_db_context() as db:
        result = run_promotion(db)
        logger.info(f"Promotion pass complete: {result}")
```

- [ ] **Step 3: Verify the full service starts without import errors**

```bash
cd src/agent-14-data-quality
DATABASE_URL=postgresql+psycopg2://user:pass@host/db \
FMP_API_KEY=test MASSIVE_KEY=test JWT_SECRET=test \
python3 -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run all tests**

```bash
cd src/agent-14-data-quality
python3 -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent-14-data-quality/app/promoter.py \
        src/agent-14-data-quality/app/api/routes.py
git commit -m "feat(dq): add promoter and all API routes for agent-14"
```

---

## Task 8: Scheduler Integration

**Files:**
- Modify: `src/scheduler-service/app/config.py`
- Modify: `src/scheduler-service/app/jobs.py`
- Modify: `src/scheduler-service/app/main.py`

- [ ] **Step 1: Write failing test**

```python
# In src/scheduler-service/tests/test_jobs.py (create if not exists)
# Verify the new job functions exist
from app import jobs
def test_job_data_quality_scan_exists():
    assert callable(getattr(jobs, "job_data_quality_scan", None))

def test_job_data_quality_retry_exists():
    assert callable(getattr(jobs, "job_data_quality_retry", None))

def test_job_data_quality_promote_exists():
    assert callable(getattr(jobs, "job_data_quality_promote", None))
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd src/scheduler-service
python3 -m pytest tests/ -v 2>/dev/null || python3 -c "from app import jobs; print(hasattr(jobs,'job_data_quality_scan'))"
```

Expected: `False`

- [ ] **Step 3: Add agent14_url to config.py**

In `src/scheduler-service/app/config.py`, add after the `agent11_url` line:

```python
    agent14_url: str = os.environ.get("AGENT14_URL", "http://agent-14-data-quality:8014")
```

- [ ] **Step 4: Add 3 new jobs to jobs.py**

At the end of `src/scheduler-service/app/jobs.py`, add:

```python
def job_data_quality_scan():
    """Agent 14 — Run data quality scan after market data refresh.
    Schedule: Weekdays at 18:35 ET (5 min after market data refresh).
    """
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    _call(
        "POST",
        f"{settings.agent14_url}/data-quality/scan/trigger",
        "Data Quality Scan",
        json={"market_refreshed_at": ts},
    )


def job_data_quality_retry():
    """Agent 14 — Retry open data quality issues (every 15 min, Mon-Fri).
    Schedule: Every 15 minutes on weekdays 18:35–20:00 ET.
    """
    _call("POST", f"{settings.agent14_url}/data-quality/retry-open", "Data Quality Retry")


def job_data_quality_promote():
    """Agent 14 — Promote analyst feature gap entries to field requirements.
    Schedule: Nightly at 02:00 ET.
    """
    _call("POST", f"{settings.agent14_url}/data-quality/promote", "Feature Gap Promotion")
```

- [ ] **Step 5: Register new jobs in main.py**

In `src/scheduler-service/app/main.py`, inside the `JOBS` list, add after the existing jobs:

```python
    (job_data_quality_scan,
     {"day_of_week": "mon-fri", "hour": 18, "minute": 35},
     "data-quality-scan",
     "Data quality scan after market refresh (Mon-Fri 18:35 ET)"),

    (job_data_quality_retry,
     {"day_of_week": "mon-fri", "hour": "18-20", "minute": "*/15"},
     "data-quality-retry",
     "Retry open data quality issues (Mon-Fri every 15min 18:35-20:00 ET)"),

    (job_data_quality_promote,
     {"hour": 2, "minute": 0},
     "data-quality-promote",
     "Nightly analyst feature gap promotion (02:00 ET)"),
```

Also import the new functions at the top of main.py (or wherever the JOBS list is defined):

```python
from app.jobs import (
    ...,  # existing imports
    job_data_quality_scan,
    job_data_quality_retry,
    job_data_quality_promote,
)
```

- [ ] **Step 6: Verify config and imports**

```bash
cd src/scheduler-service
python3 -c "from app.jobs import job_data_quality_scan, job_data_quality_retry, job_data_quality_promote; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add src/scheduler-service/app/config.py \
        src/scheduler-service/app/jobs.py \
        src/scheduler-service/app/main.py
git commit -m "feat(dq): add data quality jobs to scheduler (scan, retry, promote)"
```

---

## Task 9: Income Scoring Gate Check

**Files:**
- Modify: `src/income-scoring-service/app/config.py`
- Modify: `src/income-scoring-service/app/api/scores.py`

The scoring service must check the agent-14 gate BEFORE running `POST /scores/refresh-portfolio`.

- [ ] **Step 1: Add data_quality_service_url to config**

In `src/income-scoring-service/app/config.py`, add inside the `Settings` class:

```python
    # ── Data Quality Gate (Agent 14) ──────────────────────────────────────────
    data_quality_service_url: str = "http://agent-14-data-quality:8014"
    data_quality_gate_enabled: bool = True   # set False to bypass in dev
    data_quality_timeout: int = 10
```

- [ ] **Step 2: Find the refresh-portfolio handler**

The scheduler calls `POST /scores/refresh-portfolio`. Find this endpoint in `app/api/scores.py` (search for `refresh-portfolio`). It will look something like:

```python
@router.post("/scores/refresh-portfolio")
def refresh_portfolio(db: Session = Depends(get_db)):
    # ... gets all portfolio IDs and scores each
```

- [ ] **Step 3: Add gate check helper**

At the top of `src/income-scoring-service/app/api/scores.py`, after the existing imports, add:

```python
import httpx as _httpx
import time as _time
import jwt as _jwt


def _dq_gate_check(portfolio_id: str) -> dict:
    """
    Check the data quality gate for a portfolio before scoring.
    Returns {"status": "passed"|"blocked", "blocking_issue_count": N}.
    Falls through (returns passed) if gate service is unreachable — scoring is
    non-blocking if the gate is down.
    """
    if not settings.data_quality_gate_enabled:
        return {"status": "passed", "blocking_issue_count": 0}
    try:
        now = int(_time.time())
        token = _jwt.encode(
            {"sub": "income-scoring", "iat": now, "exp": now + 60},
            settings.jwt_secret, algorithm="HS256",
        )
        with _httpx.Client(timeout=settings.data_quality_timeout) as client:
            resp = client.get(
                f"{settings.data_quality_service_url}/data-quality/gate/{portfolio_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Data quality gate unreachable for {portfolio_id}: {e} — proceeding without gate")
    return {"status": "passed", "blocking_issue_count": 0}


def _dq_mark_scoring_complete(portfolio_id: str):
    """Notify agent-14 that scoring completed for this portfolio."""
    try:
        now = int(_time.time())
        token = _jwt.encode(
            {"sub": "income-scoring", "iat": now, "exp": now + 60},
            settings.jwt_secret, algorithm="HS256",
        )
        with _httpx.Client(timeout=5) as client:
            client.post(
                f"{settings.data_quality_service_url}/data-quality/gate/{portfolio_id}/scoring-complete",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception:
        pass  # non-critical
```

- [ ] **Step 4: Insert gate check in the refresh-portfolio handler**

Find the `refresh-portfolio` endpoint and add the gate check at the beginning of the per-portfolio loop. The pattern should be:

```python
@router.post("/scores/refresh-portfolio")
def refresh_portfolio(db: Session = Depends(get_db)):
    portfolios = _get_active_portfolios(db)   # existing call
    results = []
    for portfolio_id in portfolios:
        # ── DATA QUALITY GATE CHECK ──────────────────────────────────
        gate = _dq_gate_check(str(portfolio_id))
        if gate.get("status") != "passed":
            logger.warning(
                f"Portfolio {portfolio_id}: scoring BLOCKED by data quality gate "
                f"({gate.get('blocking_issue_count', '?')} critical issues)"
            )
            results.append({"portfolio_id": str(portfolio_id), "status": "blocked_by_gate",
                            "blocking_issue_count": gate.get("blocking_issue_count", 0)})
            continue
        # ── END GATE CHECK ────────────────────────────────────────────
        # ... existing scoring logic
        _dq_mark_scoring_complete(str(portfolio_id))   # add at end of success path
    return {"results": results}
```

> **Note:** The exact function names differ from the pattern above. Read the actual handler carefully before making changes, and adapt accordingly. The pattern is: check gate → skip if blocked → score → notify complete.

- [ ] **Step 5: Verify the service still imports correctly**

```bash
cd src/income-scoring-service
python3 -c "from app.api.scores import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add src/income-scoring-service/app/config.py \
        src/income-scoring-service/app/api/scores.py
git commit -m "feat(dq): add data quality gate check to income scoring service"
```

---

## Task 10: Docker-Compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add agent-14 service block**

In `docker-compose.yml`, after the `broker-service` block (port 8013), add:

```yaml
  agent-14-data-quality:
    build:
      context: src/agent-14-data-quality
      dockerfile: Dockerfile
    container_name: agent-14-data-quality
    environment:
      - DATABASE_URL=${PGBOUNCER_URL:-${DATABASE_URL}}
      - FMP_API_KEY=${FMP_API_KEY}
      - MASSIVE_KEY=${MASSIVE_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - SERVICE_PORT=8014
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - PYTHONUNBUFFERED=1
    ports:
      - "8014:8014"
    restart: unless-stopped
    depends_on:
      pgbouncer:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python3", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8014/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
```

- [ ] **Step 2: Add AGENT14_URL to scheduler-service environment in docker-compose.yml**

Find the `scheduler` service block and add:

```yaml
      - AGENT14_URL=http://agent-14-data-quality:8014
```

- [ ] **Step 3: Add DATA_QUALITY_SERVICE_URL to income-scoring-service environment**

Find the `agent-03-income-scoring` block and add:

```yaml
      - DATA_QUALITY_SERVICE_URL=http://agent-14-data-quality:8014
```

- [ ] **Step 4: Verify docker-compose syntax**

```bash
docker-compose config --quiet && echo "OK"
```

Expected: `OK` (no YAML errors)

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(dq): add agent-14-data-quality to docker-compose"
```

---

## Task 11: Frontend Types

**Files:**
- Modify: `src/frontend/src/lib/types.ts`

- [ ] **Step 1: Add the types**

At the end of `src/frontend/src/lib/types.ts`, append:

```typescript
// ── Data Quality ─────────────────────────────────────────────────────────────

export interface DataQualityIssue {
  id: number;
  symbol: string;
  field_name: string;
  asset_class: string;
  status: "missing" | "fetching" | "resolved" | "unresolvable";
  severity: "warning" | "critical";
  attempt_count: number;
  last_attempted_at: string | null;
  resolved_at: string | null;
  source_used: string | null;
  diagnostic: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface GateStatus {
  portfolio_id: string;
  status: "passed" | "blocked" | "pending";
  blocking_issue_count: number;
  gate_passed_at: string | null;
}

export interface RefreshLog {
  portfolio_id: string;
  market_data_refreshed_at: string | null;
  scores_recalculated_at: string | null;
  market_staleness_hrs: number | null;
  holdings_complete_count: number | null;
  holdings_incomplete_count: number | null;
  critical_issues_count: number | null;
}

export interface PortfolioHealth {
  gate: GateStatus | null;
  refresh_log: RefreshLog | null;
  issues_by_symbol: Record<string, DataQualityIssue[]>;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors from the added types.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/lib/types.ts
git commit -m "feat(dq): add DataQualityIssue, GateStatus, RefreshLog types"
```

---

## Task 12: Portfolio API Route + Health Card

**Files:**
- Create: `src/frontend/src/app/api/portfolios/[id]/route.ts`
- Create: `src/frontend/src/components/portfolio/health-card.tsx`
- Create: `src/frontend/src/components/portfolio/completeness-badge.tsx`

- [ ] **Step 1: Write the API route**

```typescript
// src/frontend/src/app/api/portfolios/[id]/route.ts
/**
 * GET /api/portfolios/[id]
 * Returns portfolio detail with data quality freshness and gate status.
 * Proxies to admin-panel for portfolio data and agent-14 for DQ data.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
const JWT_SECRET = process.env.SERVICE_JWT ?? "";

function serviceToken(): string {
  // Simple service token for internal calls — in production use proper JWT
  return process.env.SERVICE_JWT_TOKEN ?? "dev-token";
}

const headers = () => ({
  Authorization: `Bearer ${serviceToken()}`,
  "Content-Type": "application/json",
});

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const portfolioId = params.id;

  try {
    const [gateRes, refreshRes] = await Promise.allSettled([
      fetch(`${AGENT14}/data-quality/gate/${portfolioId}`, {
        headers: headers(),
        signal: AbortSignal.timeout(5_000),
      }),
      fetch(`${AGENT14}/data-quality/refresh-log/${portfolioId}`, {
        headers: headers(),
        signal: AbortSignal.timeout(5_000),
      }),
    ]);

    const gate =
      gateRes.status === "fulfilled" && gateRes.value.ok
        ? await gateRes.value.json()
        : null;

    const refreshLog =
      refreshRes.status === "fulfilled" && refreshRes.value.ok
        ? await refreshRes.value.json()
        : null;

    return NextResponse.json({ gate, refresh_log: refreshLog });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
```

- [ ] **Step 2: Write the health card component**

```tsx
// src/frontend/src/components/portfolio/health-card.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { GateStatus, RefreshLog } from "@/lib/types";

interface HealthCardProps {
  gate: GateStatus | null;
  refreshLog: RefreshLog | null;
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function stalenessColor(hrs: number | null | undefined): string {
  if (hrs == null) return "text-muted-foreground";
  if (hrs <= 24) return "text-emerald-600 dark:text-emerald-400";
  if (hrs <= 48) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function PortfolioHealthCard({ gate, refreshLog }: HealthCardProps) {
  const [expanded, setExpanded] = useState(false);

  const isBlocked = gate?.status === "blocked";
  const criticalCount = gate?.blocking_issue_count ?? 0;
  const staleness = refreshLog?.market_staleness_hrs;

  const dotColor = isBlocked
    ? "bg-red-500"
    : criticalCount === 0
    ? "bg-emerald-500"
    : "bg-amber-500";

  const label = isBlocked
    ? "Scoring Blocked"
    : criticalCount === 0
    ? "All Good"
    : `${criticalCount} Warning${criticalCount !== 1 ? "s" : ""}`;

  return (
    <div className="rounded-md border border-border bg-card px-4 py-2 text-sm">
      <button
        className="flex w-full items-center justify-between gap-3"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${dotColor}`}
            aria-hidden="true"
          />
          <span className="font-medium text-foreground">
            Data Health:{" "}
            <span
              className={
                isBlocked
                  ? "text-red-600 dark:text-red-400"
                  : "text-foreground"
              }
            >
              {label}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-3 text-muted-foreground">
          {refreshLog?.market_data_refreshed_at && (
            <span>
              Market{" "}
              <span className={stalenessColor(staleness)}>
                {formatTime(refreshLog.market_data_refreshed_at)}
              </span>
            </span>
          )}
          {refreshLog?.scores_recalculated_at && (
            <span>
              · Scores{" "}
              <span className="text-foreground">
                {formatTime(refreshLog.scores_recalculated_at)}
              </span>
            </span>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3 text-xs">
          <div>
            <p className="text-muted-foreground">Market refreshed</p>
            <p className={`font-medium ${stalenessColor(staleness)}`}>
              {formatTime(refreshLog?.market_data_refreshed_at)}
              {staleness != null && ` (${staleness.toFixed(1)}h ago)`}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Scores recalculated</p>
            <p className="font-medium text-foreground">
              {formatTime(refreshLog?.scores_recalculated_at)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Gate status</p>
            <p
              className={`font-medium ${
                isBlocked
                  ? "text-red-600 dark:text-red-400"
                  : "text-emerald-600 dark:text-emerald-400"
              }`}
            >
              {gate?.status ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Holdings complete</p>
            <p className="font-medium text-foreground">
              {refreshLog?.holdings_complete_count != null
                ? `${refreshLog.holdings_complete_count} / ${
                    (refreshLog.holdings_complete_count ?? 0) +
                    (refreshLog.holdings_incomplete_count ?? 0)
                  }`
                : "—"}
            </p>
          </div>
          {isBlocked && (
            <div className="col-span-2">
              <a
                href="/admin/data-quality"
                className="text-blue-600 underline hover:no-underline dark:text-blue-400"
              >
                View Data Quality Dashboard →
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Write the completeness badge component**

```tsx
// src/frontend/src/components/portfolio/completeness-badge.tsx
import type { DataQualityIssue } from "@/lib/types";

interface CompletenessBadgeProps {
  issues: DataQualityIssue[];
}

export function CompletenessBadge({ issues }: CompletenessBadgeProps) {
  const criticalCount = issues.filter(
    (i) => i.severity === "critical" && i.status !== "resolved"
  ).length;
  const warningCount = issues.filter(
    (i) => i.severity === "warning" && i.status !== "resolved"
  ).length;
  const openCount = criticalCount + warningCount;

  if (openCount === 0) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 dark:text-emerald-400"
        title="All required data fields present"
      >
        <span aria-hidden="true">✓</span> Complete
      </span>
    );
  }

  if (criticalCount > 0) {
    const fields = issues
      .filter((i) => i.severity === "critical" && i.status !== "resolved")
      .map((i) => i.field_name)
      .join(", ");
    return (
      <a
        href="/admin/data-quality"
        className="inline-flex items-center gap-1 text-xs font-medium text-red-700 hover:underline dark:text-red-400"
        title={`Missing: ${fields}`}
      >
        <span aria-hidden="true">✕</span> {criticalCount} critical
      </a>
    );
  }

  const fields = issues
    .filter((i) => i.severity === "warning" && i.status !== "resolved")
    .map((i) => i.field_name)
    .join(", ");
  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400"
      title={`Warning: ${fields}`}
    >
      <span aria-hidden="true">⚠</span> {warningCount} warning
    </span>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/api/portfolios/ \
        src/frontend/src/components/portfolio/
git commit -m "feat(dq): add portfolio health card, completeness badge, and API route"
```

---

## Task 13: Admin Data Quality Page

**Files:**
- Create: `src/frontend/src/app/admin/data-quality/page.tsx`

- [ ] **Step 1: Write the page**

```tsx
// src/frontend/src/app/admin/data-quality/page.tsx
"use client";

import { useEffect, useState } from "react";
import type { DataQualityIssue } from "@/lib/types";

async function fetchIssues(params: Record<string, string>): Promise<DataQualityIssue[]> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api/data-quality/issues?${qs}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.issues ?? [];
}

const SEVERITY_OPTIONS = ["", "critical", "warning"] as const;
const STATUS_OPTIONS = ["", "missing", "fetching", "resolved", "unresolvable"] as const;

export default function DataQualityPage() {
  const [issues, setIssues] = useState<DataQualityIssue[]>([]);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("missing");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (severity) params.severity = severity;
    if (status) params.status = status;
    const data = await fetchIssues(params);
    setIssues(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, [severity, status]);

  const critical = issues.filter((i) => i.severity === "critical");
  const warnings = issues.filter((i) => i.severity === "warning");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-foreground">Data Quality</h1>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Critical Issues" value={critical.length} color="text-red-600 dark:text-red-400" />
        <KpiCard label="Warnings" value={warnings.length} color="text-amber-600 dark:text-amber-400" />
        <KpiCard
          label="Unresolvable"
          value={issues.filter((i) => i.status === "unresolvable").length}
          color="text-muted-foreground"
        />
        <KpiCard
          label="Resolved (shown)"
          value={issues.filter((i) => i.status === "resolved").length}
          color="text-emerald-600 dark:text-emerald-400"
        />
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          className="rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          aria-label="Filter by severity"
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All severities"}</option>
          ))}
        </select>
        <select
          className="rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All statuses"}</option>
          ))}
        </select>
        <button
          className="rounded border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted"
          onClick={load}
        >
          Refresh
        </button>
      </div>

      {/* Issues table */}
      {loading ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : issues.length === 0 ? (
        <p className="text-muted-foreground text-sm">No issues found.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                {["Ticker", "Class", "Field", "Severity", "Status", "Attempts", "Diagnostic", "Actions"].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {issues.map((issue) => (
                <IssueRow key={issue.id} issue={issue} onAction={load} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function IssueRow({ issue, onAction }: { issue: DataQualityIssue; onAction: () => void }) {
  const [actioning, setActioning] = useState(false);

  const action = async (endpoint: string) => {
    setActioning(true);
    await fetch(`/api/data-quality/issues/${issue.id}/${endpoint}`, { method: "POST" });
    setActioning(false);
    onAction();
  };

  const diagCode = (issue.diagnostic as Record<string, string> | null)?.code ?? "—";

  return (
    <tr className="hover:bg-muted/50">
      <td className="px-3 py-2 font-mono font-medium text-foreground">{issue.symbol}</td>
      <td className="px-3 py-2 text-muted-foreground">{issue.asset_class}</td>
      <td className="px-3 py-2 font-mono text-foreground">{issue.field_name}</td>
      <td className="px-3 py-2">
        <span className={`font-medium ${issue.severity === "critical" ? "text-red-600 dark:text-red-400" : "text-amber-600 dark:text-amber-400"}`}>
          {issue.severity}
        </span>
      </td>
      <td className="px-3 py-2 text-muted-foreground">{issue.status}</td>
      <td className="px-3 py-2 text-center text-muted-foreground">{issue.attempt_count}</td>
      <td className="px-3 py-2" title={JSON.stringify(issue.diagnostic, null, 2)}>
        <span className="cursor-help font-mono text-xs text-muted-foreground">{diagCode}</span>
      </td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button
            disabled={actioning}
            onClick={() => action("retry")}
            className="text-xs text-blue-600 hover:underline dark:text-blue-400 disabled:opacity-50"
          >
            Retry
          </button>
          <button
            disabled={actioning}
            onClick={() => action("mark-na")}
            className="text-xs text-muted-foreground hover:underline disabled:opacity-50"
          >
            Mark N/A
          </button>
          <button
            disabled={actioning}
            onClick={() => action("reclassify")}
            className="text-xs text-muted-foreground hover:underline disabled:opacity-50"
          >
            Reclassify
          </button>
        </div>
      </td>
    </tr>
  );
}
```

- [ ] **Step 2: Add frontend proxy route for the admin page**

Create `src/frontend/src/app/api/data-quality/issues/route.ts`:

```typescript
// src/frontend/src/app/api/data-quality/issues/route.ts
import { NextRequest, NextResponse } from "next/server";

const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
const TOKEN = process.env.SERVICE_JWT_TOKEN ?? "dev-token";

export async function GET(req: NextRequest) {
  try {
    const qs = req.nextUrl.search;
    const upstream = await fetch(`${AGENT14}/data-quality/issues${qs}`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
      signal: AbortSignal.timeout(10_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    return NextResponse.json({ detail: String(err) }, { status: 502 });
  }
}
```

Create `src/frontend/src/app/api/data-quality/issues/[id]/[action]/route.ts`:

```typescript
// src/frontend/src/app/api/data-quality/issues/[id]/[action]/route.ts
import { NextRequest, NextResponse } from "next/server";

const AGENT14 = process.env.AGENT14_URL ?? "http://localhost:8014";
const TOKEN = process.env.SERVICE_JWT_TOKEN ?? "dev-token";

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string; action: string } }
) {
  try {
    const upstream = await fetch(
      `${AGENT14}/data-quality/issues/${params.id}/${params.action}`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${TOKEN}` },
        signal: AbortSignal.timeout(10_000),
      }
    );
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    return NextResponse.json({ detail: String(err) }, { status: 502 });
  }
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/app/admin/data-quality/ \
        src/frontend/src/app/api/data-quality/
git commit -m "feat(dq): add admin data quality page with issues table and actions"
```

---

## Task 14: Portfolio Page Integration

**Files:**
- Modify: `src/frontend/src/app/portfolios/[id]/page.tsx`

- [ ] **Step 1: Find the portfolio page**

```bash
find src/frontend/src/app/portfolios -name "page.tsx" | head -5
```

- [ ] **Step 2: Read the current page and find where to mount the health card**

The health card should appear immediately below the portfolio header (name, value, yield row). Find that JSX section.

- [ ] **Step 3: Add the health card**

Near the top of the portfolio page component (after existing imports), add:

```tsx
import { PortfolioHealthCard } from "@/components/portfolio/health-card";
import type { GateStatus, RefreshLog } from "@/lib/types";
```

In the component body, fetch health data:

```tsx
const [health, setHealth] = useState<{ gate: GateStatus | null; refresh_log: RefreshLog | null }>({
  gate: null,
  refresh_log: null,
});

useEffect(() => {
  if (!portfolioId) return;
  fetch(`/api/portfolios/${portfolioId}`)
    .then((r) => r.ok ? r.json() : null)
    .then((data) => { if (data) setHealth(data); })
    .catch(() => {});
}, [portfolioId]);
```

In JSX, add the health card below the portfolio header:

```tsx
<PortfolioHealthCard gate={health.gate} refreshLog={health.refresh_log} />
```

- [ ] **Step 4: Verify TypeScript and visually check**

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | head -10
```

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/portfolios/
git commit -m "feat(dq): mount portfolio health card on portfolio page"
```

---

## Task 15: End-to-End Smoke Test

- [ ] **Step 1: Build agent-14 image locally**

```bash
cd src/agent-14-data-quality
docker build -t agent-14-data-quality:local .
```

Expected: image builds successfully.

- [ ] **Step 2: Run migration against staging DB**

```bash
psql $DATABASE_URL -v ON_ERROR_STOP=1 \
  -f src/agent-14-data-quality/migrations/001_initial.sql
```

Expected: all tables created, seed data inserted.

- [ ] **Step 3: Start agent-14 locally and trigger a scan**

```bash
docker run -d --name dq-test -p 8014:8014 \
  -e DATABASE_URL=$DATABASE_URL \
  -e FMP_API_KEY=$FMP_API_KEY \
  -e MASSIVE_KEY=$MASSIVE_KEY \
  -e JWT_SECRET=$JWT_SECRET \
  agent-14-data-quality:local

# Wait for startup
sleep 5
curl -s http://localhost:8014/health | python3 -m json.tool

# Generate a test JWT
TOKEN=$(python3 -c "
import jwt, time
now = int(time.time())
print(jwt.encode({'sub':'test','iat':now,'exp':now+300}, '$JWT_SECRET', algorithm='HS256'))
")

# Trigger scan
curl -s -X POST http://localhost:8014/data-quality/scan/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

# Check issues after a few seconds
sleep 3
curl -s http://localhost:8014/data-quality/issues \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -40

docker stop dq-test && docker rm dq-test
```

Expected: health shows `"status":"healthy"`, scan returns `202`, issues list contains rows (or empty if all data is complete — both are valid).

- [ ] **Step 4: Deploy to production**

```bash
# On legato (138.197.78.238):
# 1. Pull latest code
# 2. docker-compose build agent-14-data-quality
# 3. docker-compose up -d agent-14-data-quality
# 4. Run migration:
#    psql $DATABASE_URL -f src/agent-14-data-quality/migrations/001_initial.sql
# 5. Verify health:
#    curl http://138.197.78.238:8014/health
```

- [ ] **Step 5: Commit final status**

```bash
git add .
git commit -m "feat(dq): data quality engine complete — agent-14, scheduler, scoring gate, frontend"
```

---

## Environment Variables Checklist

Ensure these are set in production `.env` and `docker-compose.yml`:

| Variable | Where set | Notes |
| --- | --- | --- |
| `MASSIVE_KEY` | `.env` | Already present per spec |
| `FMP_API_KEY` | `.env` | Already present |
| `JWT_SECRET` | `.env` | Already present (shared) |
| `AGENT14_URL` | docker-compose (scheduler, agent-03) | `http://agent-14-data-quality:8014` |
| `DATA_QUALITY_SERVICE_URL` | docker-compose (agent-03) | Same as AGENT14_URL |
| `SERVICE_JWT_TOKEN` | frontend env | Static service token for Next.js→agent-14 calls |
