# tests/conftest.py
"""Set required env vars before any app module imports trigger pydantic Settings validation."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("FMP_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("MASSIVE_KEY", "test-massive-key")
