"""Tests for suggestion_store TTL DB read."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


def make_db_with_ttl(ttl_days: int):
    """Return a mock Session that returns ttl_days for any query."""
    db = MagicMock()
    row = MagicMock()
    row.ttl_days = ttl_days
    db.execute.return_value.fetchone.return_value = row
    return db


def test_get_ttl_days_returns_specific_class():
    """_get_ttl_days returns the per-class TTL when found."""
    from app.processors.suggestion_store import _get_ttl_days
    db = make_db_with_ttl(30)
    result = _get_ttl_days(db, "CEF")
    assert result == 30


def test_get_ttl_days_falls_back_to_45():
    """_get_ttl_days returns 45 when table is empty."""
    from app.processors.suggestion_store import _get_ttl_days
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None  # table empty
    result = _get_ttl_days(db, "UNKNOWN_CLASS")
    assert result == 45


def test_compute_expires_at_uses_db():
    """compute_expires_at delegates to _get_ttl_days."""
    from app.processors.suggestion_store import compute_expires_at
    db = make_db_with_ttl(60)
    sourced = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = compute_expires_at(db, sourced, "Stock")
    from datetime import timedelta
    assert result == sourced + timedelta(days=60)
