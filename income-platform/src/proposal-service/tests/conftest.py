"""Test configuration and shared fixtures for proposal-service."""
import os
import sys
import pathlib

# Make the tests/ directory importable as a package root so test files can do
# `from conftest import TestingSessionLocal, Proposal as TestProposal`.
_tests_dir = str(pathlib.Path(__file__).parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

# Ensure this module is accessible as 'conftest' in sys.modules so that
# `from conftest import X` inside test functions resolves to THIS module.
import importlib.util
_this_module = importlib.util.spec_from_file_location("conftest", __file__)
if "conftest" not in sys.modules:
    sys.modules["conftest"] = sys.modules.get(__name__, sys.modules.get("conftest"))

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("AGENT02_URL", "http://agent-02:8002")
os.environ.setdefault("AGENT03_URL", "http://agent-03:8003")
os.environ.setdefault("AGENT04_URL", "http://agent-04:8004")
os.environ.setdefault("AGENT05_URL", "http://agent-05:8005")

# Patch database.py BEFORE app modules are imported so the engine is SQLite
import sys
from datetime import datetime, timezone

import jwt
import pytest
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

# ── Build a SQLite-compatible engine and Base ─────────────────────────────────
# StaticPool ensures all connections share the same in-memory DB instance,
# so CREATE TABLE calls are visible to subsequent sessions.

SQLALCHEMY_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class TestBase(DeclarativeBase):
    pass


class Proposal(TestBase):
    """SQLite-compatible Proposal model (no schema, JSON instead of JSONB)."""

    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False)
    analyst_signal_id = Column(Integer, nullable=True)
    analyst_id = Column(Integer, nullable=True)
    platform_score = Column(Numeric(5, 1), nullable=True)
    platform_alignment = Column(String(20), nullable=True)
    veto_flags = Column(JSON, nullable=True)
    divergence_notes = Column(Text, nullable=True)
    analyst_recommendation = Column(String(20), nullable=True)
    analyst_sentiment = Column(Numeric(6, 4), nullable=True)
    analyst_thesis_summary = Column(Text, nullable=True)
    analyst_yield_estimate = Column(Numeric(8, 4), nullable=True)
    analyst_safety_grade = Column(String(10), nullable=True)
    platform_yield_estimate = Column(Numeric(8, 4), nullable=True)
    platform_safety_result = Column(JSON, nullable=True)
    platform_income_grade = Column(String(5), nullable=True)
    entry_price_low = Column(Numeric(10, 2), nullable=True)
    entry_price_high = Column(Numeric(10, 2), nullable=True)
    position_size_pct = Column(Numeric(5, 2), nullable=True)
    recommended_account = Column(String(50), nullable=True)
    sizing_rationale = Column(Text, nullable=True)
    status = Column(String(30), default="pending", nullable=False)
    trigger_mode = Column(String(30), nullable=True)
    trigger_ref_id = Column(Text, nullable=True)
    portfolio_id = Column(Text, nullable=True)
    override_rationale = Column(Text, nullable=True)
    user_acknowledged_veto = Column(Boolean, default=False, nullable=False)
    reviewed_by = Column(Text, nullable=True)
    decided_at = Column(TIMESTAMP, nullable=True)
    expires_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(
        TIMESTAMP,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# Create the table before any app import
TestBase.metadata.drop_all(bind=test_engine)
TestBase.metadata.create_all(bind=test_engine)

# ── Inject test model and DB into app modules before they import ──────────────
# We must stub app.database and app.models before importing app.main

# Stub app.database
import types

db_module = types.ModuleType("app.database")
db_module.Base = TestBase
db_module.engine = test_engine
db_module.SessionLocal = TestingSessionLocal


def _get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _check_db_health() -> bool:
    from sqlalchemy import text

    try:
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


db_module.get_db = _get_db
db_module.check_db_health = _check_db_health
sys.modules["app.database"] = db_module

# Stub app.models
models_module = types.ModuleType("app.models")
models_module.Proposal = Proposal
sys.modules["app.models"] = models_module

# Stub app.config — avoid real Settings() which tries to load env files
config_module = types.ModuleType("app.config")


class _FakeSettings:
    service_name = "proposal-service"
    service_version = "1.0.0"
    port = 8012
    log_level = "INFO"
    database_url = "sqlite://"
    jwt_secret = "test-secret-for-tests"
    agent02_url = "http://agent-02:8002"
    agent02_timeout = 10.0
    agent03_url = "http://agent-03:8003"
    agent03_timeout = 10.0
    agent04_url = "http://agent-04:8004"
    agent04_timeout = 10.0
    agent05_url = "http://agent-05:8005"
    agent05_timeout = 10.0
    proposal_expiry_days = 14
    min_override_rationale_len = 20


config_module.Settings = _FakeSettings
config_module.settings = _FakeSettings()
sys.modules["app.config"] = config_module

# Now import app modules — they will use the stubs
from fastapi.testclient import TestClient
from app.main import app

# Override get_db dependency
from app.database import get_db

app.dependency_overrides[get_db] = _get_db


# ── JWT helpers ───────────────────────────────────────────────────────────────


def make_token(sub: str = "test-user", secret: str = "test-secret-for-tests") -> str:
    payload = {
        "sub": sub,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate proposals between tests."""
    yield
    db = TestingSessionLocal()
    try:
        db.query(Proposal).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ── Shared mock signal factories ──────────────────────────────────────────────


def make_signal(
    ticker: str = "O",
    sentiment: float = 0.7,
    recommendation: str = "Buy",
    safety_grade: str = "A",
    signal_id: int = 101,
    analyst_id: int = 5,
) -> dict:
    return {
        "ticker": ticker,
        "asset_class": "REIT",
        "sector": "Real Estate",
        "signal_strength": "strong",
        "proposal_readiness": True,
        "analyst": {
            "id": analyst_id,
            "display_name": "Test Analyst",
            "accuracy_overall": "0.72",
            "churn_rate": "0.05",
            "sector_alpha": {},
            "philosophy_summary": "Income focused",
            "philosophy_source": "llm",
            "philosophy_tags": {},
        },
        "recommendation": {
            "id": signal_id,
            "label": recommendation,
            "sentiment_score": str(sentiment),
            "yield_at_publish": "0.055",
            "payout_ratio": "0.80",
            "safety_grade": safety_grade,
            "source_reliability": "high",
            "thesis_summary": "Strong income generator with stable dividends.",
            "bull_case": "Reliable monthly income.",
            "bear_case": "Rising rates risk.",
            "published_at": "2026-01-15T10:00:00Z",
            "decay_weight": "1.0",
            "flip_count": 0,
        },
        "consensus": {
            "ticker": ticker,
            "score": "0.6",
            "confidence": "high",
            "n_analysts": 3,
            "n_recommendations": 5,
            "dominant_recommendation": "Buy",
            "computed_at": "2026-03-01T00:00:00Z",
        },
        "platform_alignment": None,
        "generated_at": "2026-03-13T00:00:00Z",
    }


def make_score(
    total_score: float = 75.0,
    grade: str = "B",
    nav_erosion_penalty: float = 5.0,
) -> dict:
    return {
        "ticker": "O",
        "total_score": total_score,
        "grade": grade,
        "income_grade": grade,
        "yield_estimate": 0.055,
        "nav_erosion_penalty": nav_erosion_penalty,
        "factor_details": {
            "nav_erosion_penalty": nav_erosion_penalty,
        },
        "safety_result": {"dividend_coverage": "safe"},
    }


def make_entry_price(
    entry_price_low: float = 52.0,
    entry_price_high: float = 55.0,
    position_size_pct: float = 5.0,
    entry_method: str = "yield_based",
) -> dict:
    return {
        "ticker": "O",
        "asset_class": "REIT",
        "entry_price_low": entry_price_low,
        "entry_price_high": entry_price_high,
        "position_size_pct": position_size_pct,
        "entry_method": entry_method,
        "target_yield_used": 6.0,
        "nav_delta_pct": None,
        "etf_entry_score": None,
        "etf_entry_zone": None,
        "annual_income_estimate": 1.98,
        "notes": "Buy O at or below $55.00 to lock in >=6% yield",
    }


def make_tax_placement(account: str = "Roth IRA") -> dict:
    return {
        "ticker": "O",
        "recommended_account": account,
        "account_type": account,
        "rationale": "REIT income taxed as ordinary income — shelter in Roth.",
    }
