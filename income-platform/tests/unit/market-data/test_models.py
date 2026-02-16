"""Test Pydantic models"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from src.market_data_service.models import PriceData


def test_price_data_valid():
    """Test valid PriceData creation"""
    data = PriceData(
        ticker="AAPL",
        price=182.45,
        change=1.23,
        change_percent=0.68,
        volume=45678900,
        timestamp=datetime.now(),
        source="alpha_vantage"
    )
    
    assert data.ticker == "AAPL"
    assert data.price == 182.45
    assert data.cached is False


def test_price_data_uppercase_ticker():
    """Test ticker normalization to uppercase"""
    data = PriceData(
        ticker="aapl",  # lowercase
        price=100.0,
        change=0.0,
        change_percent=0.0,
        volume=1000,
        timestamp=datetime.now(),
        source="test"
    )
    
    assert data.ticker == "AAPL"  # Should be uppercase


def test_price_data_invalid_negative_price():
    """Test validation rejects negative prices"""
    with pytest.raises(ValidationError):
        PriceData(
            ticker="AAPL",
            price=-10.0,  # Invalid
            change=0.0,
            change_percent=0.0,
            volume=1000,
            timestamp=datetime.now(),
            source="test"
        )
