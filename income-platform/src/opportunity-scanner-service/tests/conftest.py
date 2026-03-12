import os

# Must be set before any app module is imported (config.py requires jwt_secret + database_url).
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")
