import os

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")


# Force anyio to use asyncio backend for all async tests.
@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param
