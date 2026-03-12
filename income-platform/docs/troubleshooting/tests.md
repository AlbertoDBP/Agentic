# Test Failures

Troubleshooting pytest, test fixtures, and test environment issues.

---

## Error: pytest: command not found

**Symptom:**
```
bash: pytest: command not found
```

**Root Cause:** pytest not installed globally, or using wrong Python environment.

**Immediate Fix:**

Use Python module syntax instead:
```bash
# CORRECT - use python -m
python -m pytest tests/

# OR in container
docker compose exec market-data-service python -m pytest tests/

# WRONG - direct command (may not work)
# pytest tests/
```

Or install pytest globally:
```bash
pip install pytest
pytest tests/
```

**Prevention:**
- Always use `python -m pytest` in scripts and CI/CD
- Document in README: "Run tests with: `python -m pytest`"
- Add pytest to requirements.txt (or requirements-dev.txt)

---

## Error: ImportError: cannot import name 'verify_token' from 'auth'

**Symptom:** Test fails at import time:
```
ImportError: cannot import name 'verify_token' from 'auth'
```

Or in conftest.py:
```
ModuleNotFoundError: No module named 'auth'
```

**Root Cause:** JWT_SECRET not set BEFORE app modules are imported. Auth module is imported during app initialization and checks JWT_SECRET at module level.

**Immediate Fix:**

In conftest.py, set JWT_SECRET at the VERY BEGINNING:

```python
# conftest.py - THIS MUST BE FIRST
import os

# SET JWT_SECRET BEFORE ANY APP IMPORTS
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# ... only then import app modules
import sys
from pathlib import Path
from fastapi.testclient import TestClient

import main  # or from main import app
```

This is already correctly done in `/src/market-data-service/tests/conftest.py`.

**Prevention:**
- conftest.py MUST set JWT_SECRET at module level (not in fixtures)
- Never import app before setting env vars
- Add comment at top: "IMPORTANT: JWT_SECRET set before imports"
- Document in CONTRIBUTING.md

---

## Error: sys.modules mock leakage between test files

**Symptom:** Tests pass individually but fail when run together:
```
python -m pytest tests/unit/test_auth.py  # PASS
python -m pytest tests/unit/test_api.py   # PASS
python -m pytest tests/                   # FAIL - conflicting mocks
```

**Root Cause:** One test modifies `sys.modules` and doesn't clean up. Next test imports same module but gets the mocked version.

**Immediate Fix:**

Add cleanup in test fixtures:

```python
@pytest.fixture(autouse=True)
def cleanup_sys_modules():
    """Remove test mocks from sys.modules after each test."""
    original_modules = dict(sys.modules)

    yield

    # Restore original modules
    for key in list(sys.modules.keys()):
        if key not in original_modules:
            del sys.modules[key]
        else:
            sys.modules[key] = original_modules[key]
```

Or use monkeypatch (pytest built-in):

```python
def test_something(monkeypatch):
    # monkeypatch automatically cleans up after test
    monkeypatch.setattr(main, 'cache_manager', mock_cache)
```

**Prevention:**
- Use `monkeypatch` fixture for all sys.modules modifications
- Never directly assign to `sys.modules` without cleanup
- Use `pytest-mock` package for cleaner mocking
- Run tests with isolation: `python -m pytest --forked`

---

## Error: asyncpg pool mocking fails

**Symptom:** When mocking asyncpg connection pool:
```
AttributeError: 'MagicMock' object has no attribute '_pool'
```

Or:
```
TypeError: object NoneType can't be used in 'await' expression
```

**Root Cause:** Mocking `asyncpg.connect` directly doesn't intercept the pool. Must mock the pool object itself or use `AsyncMock` for async methods.

**Immediate Fix:**

Don't mock asyncpg.connect. Instead, mock the DatabaseManager:

```python
@pytest.fixture
def mock_db_manager():
    """Mock the DatabaseManager, not asyncpg directly."""
    mock = MagicMock()
    mock.is_connected = AsyncMock(return_value=True)
    mock.session_factory = None  # No sync session for async service
    mock.engine = None
    return mock

def test_something(monkeypatch, mock_db_manager):
    monkeypatch.setattr('app.database', mock_db_manager)
    # Now DatabaseManager is mocked
```

If you must mock asyncpg:

```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_asyncpg(monkeypatch):
    """Mock asyncpg.connect to return async connection."""
    mock_connection = AsyncMock()
    mock_connection.execute = AsyncMock(return_value="result")

    async def mock_connect(*args, **kwargs):
        return mock_connection

    monkeypatch.setattr('asyncpg.connect', mock_connect)
```

**Prevention:**
- Mock at the highest level (DatabaseManager, not asyncpg)
- Use `AsyncMock` for any awaitable
- Test mocks work: `await mock.method()` should not raise TypeError

---

## Error: Fixture 'client' not found / Fixture dependency missing

**Symptom:**
```
fixture 'client' not found
```

**Root Cause:** conftest.py not found in test directory, or fixture not defined.

**Immediate Fix:**

1. Verify conftest.py exists:
```bash
ls tests/conftest.py
```

If not, create it (or ensure it's in the right directory):
```bash
# conftest.py must be in tests/ directory
# Pytest discovers it automatically
```

2. If running from wrong directory:
```bash
# Run from repo root
cd /path/to/income-platform
python -m pytest tests/

# Not from tests/ directory
# cd tests/
# python -m pytest  # Would fail
```

3. Verify fixture is defined:
```bash
grep "def client" tests/conftest.py
```

**Prevention:**
- Keep conftest.py in tests/ root directory
- Use `python -m pytest` from repo root
- List available fixtures: `python -m pytest --fixtures`

---

## Error: Timeout during test execution

**Symptom:** Test hangs indefinitely:
```
test session hangs...
<timeout after 300s>
```

**Root Cause:** Awaiting async mock that returns sync value, or real database being hit (timeout).

**Immediate Fix:**

1. For async functions, ensure mock returns awaitable:
```python
# WRONG
mock = MagicMock()
mock.get_price = MagicMock(return_value=100)
result = await mock.get_price()  # TypeError or hangs

# CORRECT
mock = MagicMock()
mock.get_price = AsyncMock(return_value=100)
result = await mock.get_price()  # Works
```

2. For database operations, add timeout:
```bash
python -m pytest --timeout=10 tests/
```

Requires `pytest-timeout`:
```bash
pip install pytest-timeout
```

3. If database actually querying, check connection:
```bash
docker compose exec postgres psql -U user -d testdb -c "SELECT 1;"
```

**Prevention:**
- Use `AsyncMock` for all async methods
- Add `pytest-timeout` to catch hanging tests
- Mock external services completely (don't hit real DB in tests)
- Use fixtures to provide mocks

---

## Error: Test database connection refused

**Symptom:** Test fails with:
```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Root Cause:** Test trying to connect to real PostgreSQL, but DB not running.

**Immediate Fix:**

1. Start test database:
```bash
# If using docker-compose
docker compose up -d postgres

# If using separate test container
docker run -d --name testdb \
  -e POSTGRES_USER=test \
  -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=testdb \
  postgres:15
```

2. Verify connection:
```bash
docker compose exec postgres psql -U test -d testdb -c "SELECT 1;"
```

3. Set DATABASE_URL in conftest:
```python
os.environ.setdefault("DATABASE_URL",
    "postgresql://test:test@localhost:5432/testdb")
```

4. Re-run test:
```bash
python -m pytest tests/
```

**Prevention:**
- Mock database connections in unit tests (don't use real DB)
- For integration tests, use separate test database
- Use `pytest-postgresql` fixture for auto-managed test DB:

```python
@pytest.fixture
def db(postgresql):
    """Pytest fixture that auto-creates/teardowns test database."""
    return postgresql
```

Requires: `pip install pytest-postgresql`

---

## Error: Fixture dependency cycle detected

**Symptom:**
```
fixture dependency cycle detected: ...
```

**Root Cause:** Circular fixture dependencies (A depends on B, B depends on A).

**Immediate Fix:**

Redesign fixture hierarchy. Example:

```python
# WRONG - cycle
@pytest.fixture
def mock_cache(mock_db):
    # depends on mock_db
    return MagicMock()

@pytest.fixture
def mock_db(mock_cache):
    # depends on mock_cache - CYCLE!
    return MagicMock()

# CORRECT - linear
@pytest.fixture
def mock_cache():
    return MagicMock()

@pytest.fixture
def mock_db(mock_cache):
    # Can depend on mock_cache
    m = MagicMock()
    m.cache = mock_cache
    return m
```

**Prevention:**
- Keep fixture dependencies linear (no cycles)
- Use `autouse=True` for fixtures that should always run
- Document fixture dependencies in docstring

---

## Error: Test passes locally but fails in CI/CD

**Symptom:** `pytest` works locally but fails in GitHub Actions / GitLab CI.

**Root Cause:** Different environment (missing env vars, different Python version, different dependencies).

**Immediate Fix:**

1. Check Python version in CI:
```yaml
# .github/workflows/test.yml
- uses: actions/setup-python@v4
  with:
    python-version: "3.11"  # Match local version
```

2. Ensure all env vars set in CI:
```yaml
env:
  JWT_SECRET: test-secret
  DATABASE_URL: postgresql://test:test@localhost:5432/testdb
  REDIS_URL: redis://localhost:6379/0
```

3. Install dependencies:
```yaml
- run: pip install -r requirements-dev.txt
```

4. Run same test command as local:
```yaml
- run: python -m pytest tests/ -v
```

5. Debug in CI by printing env:
```bash
python -c "import os; print(dict(os.environ))"
```

**Prevention:**
- requirements.txt pinned versions
- CI env vars match local .env
- Run CI locally: `act` (GitHub Actions) or use docker-compose
- Document test requirements in README

---

## Error: Mock side_effect raises exception immediately

**Symptom:** Mocking with side_effect:
```python
mock.get.side_effect = Exception("Not found")
```

Then exception is raised at wrong time:
```
# Test fails immediately, not when calling mock
```

**Root Cause:** `side_effect` is evaluated immediately if it's an exception instance.

**Immediate Fix:**

Use lambda to delay exception:

```python
# WRONG - raises immediately
mock.get.side_effect = Exception("Not found")

# CORRECT - raises when called
mock.get.side_effect = Exception("Not found")  # Still works because MagicMock checks type

# Better - explicit
mock.get.side_effect = lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Not found"))

# Best - use return_value for normal, side_effect for errors
mock.get.return_value = {"data": "ok"}
# For error case:
mock_err = MagicMock()
mock_err.get.side_effect = Exception("Not found")
```

**Prevention:**
- Prefer `return_value` for normal cases, `side_effect` for errors
- Test your test mocks: ensure exception is raised when you call the method
- Use `AsyncMock(side_effect=Exception(...))` for async

---

## Error: Test modifies global state and breaks other tests

**Symptom:** Test passes alone but fails when run with others in suite.

**Root Cause:** Test modifies global variable or module state without cleanup.

**Immediate Fix:**

Use `monkeypatch.setattr()` which auto-reverts:

```python
# WRONG - modifies global state
def test_something():
    import os
    os.environ['DEBUG'] = 'true'  # Never reverted!

# CORRECT - auto-reverts after test
def test_something(monkeypatch):
    monkeypatch.setenv('DEBUG', 'true')
    # Automatically reverted after test
```

Or use context manager:

```python
from unittest.mock import patch

def test_something():
    with patch.dict(os.environ, {'DEBUG': 'true'}):
        # Changes isolated to this block
        pass
    # Reverted here
```

**Prevention:**
- Always use `monkeypatch` for env/global changes
- Use `pytest --forked` to run tests in separate processes
- Add `autouse=True` cleanup fixture:

```python
@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Cleanup code here
    global_state.reset()
```

---

## Debugging Test Failures

### Run single test with verbose output:
```bash
python -m pytest tests/unit/test_auth.py::test_verify_token -vv -s
```

### See print statements:
```bash
python -m pytest -s  # Don't capture stdout
```

### Show local variables on failure:
```bash
python -m pytest -l  # Show locals
```

### Break into debugger on failure:
```bash
python -m pytest --pdb  # Drop to pdb on failure
```

### Run only failing tests:
```bash
python -m pytest --lf  # Last failed
python -m pytest --ff  # Failed first
```

### Collect tests without running:
```bash
python -m pytest --collect-only tests/
```

### Check fixture resolution:
```bash
python -m pytest --fixtures tests/
```

---

## Common Test Patterns

### Testing protected endpoints:

```python
def test_protected_endpoint_with_token(authed_client):
    """authed_client includes Authorization header."""
    response = authed_client.get("/stocks/AAPL/price")
    assert response.status_code == 200

def test_protected_endpoint_without_token(client):
    """client without auth header."""
    response = client.get("/stocks/AAPL/price")
    assert response.status_code == 401
```

### Mocking async service:

```python
def test_service_call(monkeypatch):
    mock_service = AsyncMock()
    mock_service.get_data.return_value = {"result": "ok"}

    monkeypatch.setattr('app.service', mock_service)

    result = await mock_service.get_data()
    assert result == {"result": "ok"}
```

### Testing with fixture:

```python
@pytest.fixture
def sample_data():
    return {"ticker": "AAPL", "price": 150.0}

def test_process_data(sample_data):
    result = process(sample_data)
    assert result is not None
```

---

## Debugging Checklist

- [ ] JWT_SECRET set before app import? Check conftest.py top lines
- [ ] Using `AsyncMock` for async methods? Not `MagicMock`
- [ ] Fixtures defined in conftest.py? Check filename
- [ ] Running from repo root? `python -m pytest tests/`
- [ ] All mocks cleaned up? Use `monkeypatch`
- [ ] Test database running? `docker compose exec postgres psql -c "SELECT 1;"`
- [ ] Same Python version locally and CI?
- [ ] All dependencies installed? `pip install -r requirements-dev.txt`

---

## See Also

- [Service Startup Failures](./service-startup.md) — Import and startup issues
- [Authentication Errors](./authentication.md) — JWT token testing
- Source: `/src/market-data-service/tests/conftest.py` — Test fixtures reference
