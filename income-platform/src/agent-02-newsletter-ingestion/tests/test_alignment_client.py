"""
Agent 02 — Newsletter Ingestion Service
Tests: alignment_client — _derive_alignment() and score_ticker_sync()

25 tests covering:
  - _derive_alignment() boundary conditions for BULLISH / BEARISH / NEUTRAL
  - sentiment=None treated as 0.0 (NEUTRAL)
  - Exact boundary values at ±0.20
  - score_ticker_sync() with mocked httpx: success, HTTP 4xx, timeout, network error
"""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://fake:fake@localhost/fake")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APIDOJO_SA_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("FMP_API_KEY", "test-key")

from app.processors.alignment_client import _derive_alignment, score_ticker_sync  # noqa: E402


# ── _derive_alignment: BULLISH (sentiment > +0.20) ────────────────────────────

class TestDerivAlignmentBullish:

    def test_bullish_score_70_is_aligned(self):
        assert _derive_alignment(0.21, 70) == "Aligned"

    def test_bullish_score_69_is_vetoed(self):
        assert _derive_alignment(0.21, 69) == "Vetoed"

    def test_bullish_score_100_is_aligned(self):
        assert _derive_alignment(0.50, 100) == "Aligned"

    def test_bullish_score_0_is_vetoed(self):
        assert _derive_alignment(0.50, 0) == "Vetoed"

    def test_bullish_score_exactly_70_is_aligned(self):
        assert _derive_alignment(0.30, 70.0) == "Aligned"

    def test_bullish_score_69_9_is_vetoed(self):
        assert _derive_alignment(0.25, 69.9) == "Vetoed"

    def test_bullish_high_sentiment_score_80_is_aligned(self):
        assert _derive_alignment(0.99, 80) == "Aligned"


# ── _derive_alignment: BEARISH (sentiment < -0.20) ────────────────────────────

class TestDerivAlignmentBearish:

    def test_bearish_score_70_is_divergent(self):
        assert _derive_alignment(-0.21, 70) == "Divergent"

    def test_bearish_score_69_is_partial(self):
        assert _derive_alignment(-0.21, 69) == "Partial"

    def test_bearish_score_55_is_partial(self):
        assert _derive_alignment(-0.50, 55) == "Partial"

    def test_bearish_score_54_is_aligned(self):
        assert _derive_alignment(-0.50, 54) == "Aligned"

    def test_bearish_score_100_is_divergent(self):
        assert _derive_alignment(-0.80, 100) == "Divergent"

    def test_bearish_score_0_is_aligned(self):
        assert _derive_alignment(-0.50, 0) == "Aligned"

    def test_bearish_score_exactly_55_is_partial(self):
        assert _derive_alignment(-0.30, 55.0) == "Partial"

    def test_bearish_score_exactly_70_is_divergent(self):
        assert _derive_alignment(-0.30, 70.0) == "Divergent"

    def test_bearish_score_56_is_partial(self):
        assert _derive_alignment(-0.40, 56) == "Partial"

    def test_bearish_score_54_9_is_aligned(self):
        assert _derive_alignment(-0.40, 54.9) == "Aligned"


# ── _derive_alignment: NEUTRAL (−0.20 ≤ sentiment ≤ +0.20) ───────────────────

class TestDerivAlignmentNeutral:

    def test_neutral_zero_any_score_is_partial(self):
        assert _derive_alignment(0.0, 75) == "Partial"

    def test_neutral_positive_boundary_is_partial(self):
        # Exactly +0.20 is NEUTRAL (not BULLISH — condition is strictly > 0.20)
        assert _derive_alignment(0.20, 90) == "Partial"

    def test_neutral_negative_boundary_is_partial(self):
        # Exactly -0.20 is NEUTRAL (not BEARISH — condition is strictly < -0.20)
        assert _derive_alignment(-0.20, 40) == "Partial"

    def test_neutral_small_positive_is_partial(self):
        assert _derive_alignment(0.10, 50) == "Partial"

    def test_neutral_small_negative_is_partial(self):
        assert _derive_alignment(-0.10, 80) == "Partial"

    def test_sentiment_none_treated_as_neutral(self):
        # None → 0.0 → NEUTRAL → Partial regardless of score
        assert _derive_alignment(None, 85) == "Partial"

    def test_sentiment_none_low_score_still_partial(self):
        assert _derive_alignment(None, 20) == "Partial"


# ── score_ticker_sync: mocked httpx ───────────────────────────────────────────

class TestScoreTickerSync:

    def _mock_response(self, status_code: int, json_data: dict | None = None):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        if json_data is not None:
            mock_resp.json.return_value = json_data
        return mock_resp

    def test_success_returns_dict(self):
        payload = {
            "ticker": "O",
            "total_score": 78.5,
            "grade": "B+",
            "recommendation": "ACCUMULATE",
        }
        mock_resp = self._mock_response(200, payload)
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("app.processors.alignment_client.httpx.Client", return_value=mock_client_instance):
            result = score_ticker_sync("O")

        assert result is not None
        assert isinstance(result, dict)
        assert result["total_score"] == 78.5

    def test_success_response_contains_ticker(self):
        payload = {"ticker": "MAIN", "total_score": 65.0, "grade": "C"}
        mock_resp = self._mock_response(200, payload)
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("app.processors.alignment_client.httpx.Client", return_value=mock_client_instance):
            result = score_ticker_sync("MAIN")

        assert result["ticker"] == "MAIN"

    def test_http_4xx_returns_none(self):
        mock_resp = self._mock_response(422)
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("app.processors.alignment_client.httpx.Client", return_value=mock_client_instance):
            result = score_ticker_sync("BAD")

        assert result is None

    def test_http_404_returns_none(self):
        mock_resp = self._mock_response(404)
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("app.processors.alignment_client.httpx.Client", return_value=mock_client_instance):
            result = score_ticker_sync("MISSING")

        assert result is None

    def test_timeout_returns_none(self):
        import httpx

        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("app.processors.alignment_client.httpx.Client", return_value=mock_client_instance):
            result = score_ticker_sync("SLOW")

        assert result is None

    def test_network_error_returns_none(self):
        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = Exception("connection refused")
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("app.processors.alignment_client.httpx.Client", return_value=mock_client_instance):
            result = score_ticker_sync("DEAD")

        assert result is None
