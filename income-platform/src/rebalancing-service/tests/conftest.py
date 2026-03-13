import os

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("INCOME_SCORING_URL", "http://agent-03:8003")
os.environ.setdefault("TAX_OPTIMIZATION_URL", "http://agent-05:8005")


# Force anyio to use asyncio for all async tests (engine uses asyncio.Semaphore
# which is not compatible with the trio backend).
@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param
