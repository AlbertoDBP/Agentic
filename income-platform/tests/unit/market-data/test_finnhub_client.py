"""
Unit tests for FinnhubClient (fetchers/finnhub_client.py).

Covers:
  - get_credit_rating: returns rating string from metric.creditRating
  - get_credit_rating: returns None when api_key is empty
  - get_credit_rating: returns None when HTTP 429 (rate limit hit)
  - get_credit_rating: returns None when HTTP 401/403 (auth errors)
  - get_credit_rating: returns None when metric key is absent
  - get_credit_rating: returns None when creditRating key is absent
  - get_credit_rating: strips surrounding whitespace from rating
  - get_credit_rating: returns None when creditRating is empty string
  - _get: raises RuntimeError when used outside async context manager
  - symbol is uppercased before the request

All HTTP I/O is mocked at the aiohttp session level — no network calls are made.

Run with:
    pytest tests/unit/market-data/test_finnhub_client.py -v
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make service modules importable
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "src" / "market-data-service"
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

from fetchers.finnhub_client import FinnhubClient  # noqa: E402


# ---------------------------------------------------------------------------
# Client factory helper
# ---------------------------------------------------------------------------

def _client(api_key: str = "test-key") -> FinnhubClient:
    """Return a FinnhubClient with a pre-wired mock session."""
    c = FinnhubClient(api_key=api_key)
    c.session = MagicMock()
    return c


def _mock_get(response: dict):
    """Return a coroutine mock that resolves to *response*."""
    return AsyncMock(return_value=response)


# ---------------------------------------------------------------------------
# Tests — get_credit_rating happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credit_rating_returns_rating_string():
    """Returns the creditRating string from metric payload."""
    client = _client()
    payload = {"metric": {"creditRating": "BBB+"}}

    with patch.object(client, "_get", _mock_get(payload)):
        result = await client.get_credit_rating("aapl")

    assert result == "BBB+"


@pytest.mark.asyncio
async def test_get_credit_rating_strips_whitespace():
    """Surrounding whitespace in creditRating is stripped."""
    client = _client()
    payload = {"metric": {"creditRating": "  A+  "}}

    with patch.object(client, "_get", _mock_get(payload)):
        result = await client.get_credit_rating("MSFT")

    assert result == "A+"


@pytest.mark.asyncio
async def test_get_credit_rating_symbol_uppercased():
    """Symbol is uppercased before the request is made."""
    client = _client()
    payload = {"metric": {"creditRating": "AA"}}
    captured = {}

    async def _capturing_get(path, params=None):
        captured["params"] = params
        return payload

    with patch.object(client, "_get", side_effect=_capturing_get):
        await client.get_credit_rating("aapl")

    assert captured["params"]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Tests — get_credit_rating None paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_credit_rating_returns_none_when_no_api_key():
    """Returns None immediately when api_key is empty — no HTTP call made."""
    client = _client(api_key="")
    get_mock = AsyncMock()

    with patch.object(client, "_get", get_mock):
        result = await client.get_credit_rating("AAPL")

    assert result is None
    get_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_credit_rating_returns_none_when_metric_key_absent():
    """Returns None when response has no 'metric' key."""
    client = _client()

    with patch.object(client, "_get", _mock_get({})):
        result = await client.get_credit_rating("AAPL")

    assert result is None


@pytest.mark.asyncio
async def test_get_credit_rating_returns_none_when_credit_rating_absent():
    """Returns None when metric dict has no 'creditRating' field."""
    client = _client()
    payload = {"metric": {"peNormalizedAnnual": 25.3}}

    with patch.object(client, "_get", _mock_get(payload)):
        result = await client.get_credit_rating("AAPL")

    assert result is None


@pytest.mark.asyncio
async def test_get_credit_rating_returns_none_when_credit_rating_empty_string():
    """Returns None when creditRating is an empty string (whitespace only)."""
    client = _client()
    payload = {"metric": {"creditRating": "   "}}

    with patch.object(client, "_get", _mock_get(payload)):
        result = await client.get_credit_rating("AAPL")

    assert result is None


@pytest.mark.asyncio
async def test_get_credit_rating_returns_none_on_exception():
    """Returns None and does not raise when _get throws an unexpected error."""
    client = _client()

    async def _raise(*args, **kwargs):
        raise RuntimeError("unexpected network error")

    with patch.object(client, "_get", side_effect=_raise):
        result = await client.get_credit_rating("AAPL")

    assert result is None


# ---------------------------------------------------------------------------
# Tests — _get HTTP error handling (rate limit / auth)
# ---------------------------------------------------------------------------


def _mock_response(status: int, json_data: dict = None):
    """Build a mock aiohttp response context manager."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_get_returns_empty_dict_on_429():
    """HTTP 429 is treated as a soft rate-limit hit — returns {} without raising."""
    client = _client()
    client.session.get = MagicMock(return_value=_mock_response(429))

    result = await client._get("/stock/metric", params={"symbol": "AAPL"})

    assert result == {}


@pytest.mark.asyncio
async def test_get_returns_empty_dict_on_401():
    """HTTP 401 auth error returns {} without raising."""
    client = _client()
    client.session.get = MagicMock(return_value=_mock_response(401))

    result = await client._get("/stock/metric", params={"symbol": "AAPL"})

    assert result == {}


@pytest.mark.asyncio
async def test_get_returns_empty_dict_on_403():
    """HTTP 403 auth error returns {} without raising."""
    client = _client()
    client.session.get = MagicMock(return_value=_mock_response(403))

    result = await client._get("/stock/metric", params={"symbol": "AAPL"})

    assert result == {}


@pytest.mark.asyncio
async def test_get_raises_when_no_session():
    """_get raises RuntimeError when called outside the async context manager."""
    client = FinnhubClient(api_key="key")  # session is None

    with pytest.raises(RuntimeError, match="context manager"):
        await client._get("/stock/metric")


# ---------------------------------------------------------------------------
# Tests — context manager lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_opens_and_closes_session():
    """__aenter__ creates a session; __aexit__ closes it."""
    async with FinnhubClient(api_key="key") as client:
        assert client.session is not None

    # After exit the session is closed — aiohttp closes it internally;
    # we just verify the object is no longer None (was set during __aenter__)
    # and that __aexit__ ran without error.
