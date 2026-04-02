# src/opportunity-scanner-service/tests/test_market_cache.py
import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("INCOME_SCORING_URL", "http://localhost:8003")
os.environ.setdefault("FMP_API_KEY", "test")

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.scanner.market_cache import _fmp_profile


@pytest.mark.anyio
async def test_fmp_profile_returns_expense_ratio():
    """_fmp_profile must pass expenseRatio through in its result dict."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{
        "symbol": "JEPI",
        "price": 55.0,
        "beta": 0.35,
        "volAvg": 3_000_000,
        "mktCap": 35_000_000_000,
        "lastDiv": 0.48,
        "changes": 0.12,
        "companyName": "JPMorgan Equity Premium Income ETF",
        "exchange": "NYSE",
        "industry": "Asset Management",
        "sector": "Financial Services",
        "range": "50.0-57.0",
        "expenseRatio": 0.0035,
    }]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await _fmp_profile("JEPI", mock_client)

    assert result.get("expense_ratio") == 0.0035


@pytest.mark.anyio
async def test_fmp_profile_expense_ratio_none_when_missing():
    """_fmp_profile must return expense_ratio=None when FMP doesn't report it."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{
        "symbol": "O",
        "price": 58.0,
        "beta": 0.6,
        "volAvg": 5_000_000,
        "mktCap": 40_000_000_000,
        "lastDiv": 0.26,
        "changes": -0.05,
        "companyName": "Realty Income",
        "exchange": "NYSE",
        "industry": "REIT",
        "sector": "Real Estate",
        "range": "50.0-65.0",
        # no expenseRatio key
    }]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await _fmp_profile("O", mock_client)

    assert result.get("expense_ratio") is None
