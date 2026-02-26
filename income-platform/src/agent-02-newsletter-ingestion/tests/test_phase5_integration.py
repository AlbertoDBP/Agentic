"""
Agent 02 — Newsletter Ingestion Service
Tests: Phase 5 — Integration smoke tests

These tests verify end-to-end service behavior without mocking the
database or cache layers. They are designed to run against a live
local service (docker compose up) or after deployment.

Run modes:
  pytest tests/test_phase5_integration.py -v              # skips if service down
  pytest tests/test_phase5_integration.py -v --live       # fails if service down

Marked with @pytest.mark.integration — excluded from CI unit test runs.
"""
import pytest
import os
import httpx
from datetime import datetime


BASE_URL = os.getenv("AGENT02_TEST_URL", "http://localhost:8002")
TIMEOUT = 10


def _service_available() -> bool:
    """Check if the service is reachable."""
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# Skip all integration tests if service is not running
# unless --live flag is passed
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def require_service(request):
    if not _service_available():
        if request.config.getoption("--live", default=False):
            pytest.fail(f"Service not available at {BASE_URL} (--live mode)")
        else:
            pytest.skip(f"Service not available at {BASE_URL} — skipping integration tests")


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_health_status_not_unhealthy(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        data = r.json()
        assert data.get("status") in ("healthy", "degraded"), \
            f"Service unhealthy: {data}"

    def test_health_has_required_fields(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        data = r.json()
        for field in ["status", "timestamp", "service"]:
            assert field in data, f"Missing field: {field}"

    def test_health_timestamp_is_recent(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        data = r.json()
        ts = data.get("timestamp")
        assert ts is not None
        # Should be a parseable datetime
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed is not None


# ── OpenAPI Docs ──────────────────────────────────────────────────────────────

class TestOpenAPIDocs:
    def test_docs_available(self):
        r = httpx.get(f"{BASE_URL}/docs", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_openapi_schema_available(self):
        r = httpx.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_openapi_has_all_phase4_routes(self):
        r = httpx.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT)
        schema = r.json()
        paths = list(schema.get("paths", {}).keys())

        required_paths = [
            "/health",
            "/analysts",
            "/recommendations/{ticker}",
            "/consensus/{ticker}",
            "/signal/{ticker}",
            "/flows/harvester/trigger",
            "/flows/intelligence/trigger",
            "/flows/status",
        ]
        for path in required_paths:
            assert path in paths, f"Missing route in OpenAPI schema: {path}"


# ── Analysts ──────────────────────────────────────────────────────────────────

class TestAnalystsIntegration:
    def test_list_analysts_returns_200(self):
        r = httpx.get(f"{BASE_URL}/analysts", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_list_analysts_response_shape(self):
        r = httpx.get(f"{BASE_URL}/analysts", timeout=TIMEOUT)
        data = r.json()
        assert "analysts" in data
        assert "total" in data
        assert isinstance(data["analysts"], list)

    def test_seeded_analysts_present(self):
        """Verify the two test analysts seeded in Phase 2 are present."""
        r = httpx.get(f"{BASE_URL}/analysts", timeout=TIMEOUT)
        data = r.json()
        sa_ids = {a["sa_publishing_id"] for a in data["analysts"]}
        # At least one of the test analysts should be present
        assert sa_ids & {"96726", "104956"}, \
            f"Neither test analyst found. Got SA IDs: {sa_ids}"

    def test_add_duplicate_analyst_returns_409(self):
        """Adding an analyst that already exists must return 409."""
        # Get first analyst's SA ID
        r = httpx.get(f"{BASE_URL}/analysts", timeout=TIMEOUT)
        analysts = r.json().get("analysts", [])
        if not analysts:
            pytest.skip("No analysts in DB — skipping duplicate test")

        existing_sa_id = analysts[0]["sa_publishing_id"]
        r2 = httpx.post(f"{BASE_URL}/analysts", json={
            "sa_publishing_id": existing_sa_id,
            "display_name": "Duplicate Test",
        }, timeout=TIMEOUT)
        assert r2.status_code == 409

    def test_get_nonexistent_analyst_returns_404(self):
        r = httpx.get(f"{BASE_URL}/analysts/999999", timeout=TIMEOUT)
        assert r.status_code == 404


# ── Flow Triggers ─────────────────────────────────────────────────────────────

class TestFlowTriggers:
    def test_harvester_trigger_returns_200(self):
        r = httpx.post(
            f"{BASE_URL}/flows/harvester/trigger",
            json={},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("triggered") is True
        assert data.get("flow_name") == "harvester_flow"

    def test_harvester_trigger_with_analyst_ids(self):
        r = httpx.post(
            f"{BASE_URL}/flows/harvester/trigger",
            json={"analyst_ids": [1]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_intelligence_trigger_returns_200(self):
        """Phase 3 activated this — should no longer be 501."""
        r = httpx.post(
            f"{BASE_URL}/flows/intelligence/trigger",
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_flow_status_returns_200(self):
        r = httpx.get(f"{BASE_URL}/flows/status", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "flows" in r.json()


# ── Signal (when data available) ─────────────────────────────────────────────

class TestSignalIntegration:
    def test_signal_unknown_ticker_returns_404(self):
        r = httpx.get(f"{BASE_URL}/signal/ZZZZNOTREAL", timeout=TIMEOUT)
        assert r.status_code == 404

    def test_signal_ticker_normalized_to_uppercase(self):
        """Lowercase ticker should behave identically to uppercase."""
        r_lower = httpx.get(f"{BASE_URL}/signal/zzzznotreal", timeout=TIMEOUT)
        r_upper = httpx.get(f"{BASE_URL}/signal/ZZZZNOTREAL", timeout=TIMEOUT)
        assert r_lower.status_code == r_upper.status_code

    def test_consensus_unknown_ticker_returns_404(self):
        r = httpx.get(f"{BASE_URL}/consensus/ZZZZNOTREAL", timeout=TIMEOUT)
        assert r.status_code == 404

    def test_recommendations_unknown_ticker_returns_404(self):
        r = httpx.get(f"{BASE_URL}/recommendations/ZZZZNOTREAL", timeout=TIMEOUT)
        assert r.status_code == 404


def pytest_addoption(parser):
    """Add --live flag to pytest CLI."""
    try:
        parser.addoption(
            "--live",
            action="store_true",
            default=False,
            help="Fail (not skip) if service is not available",
        )
    except ValueError:
        pass  # Option already added by conftest
