"""
Agent 03 — Income Scoring Service
Tests: Phase 2 — Signal Penalty Layer.

Coverage:
  TestSignalPenaltyEngine    — pure penalty computation logic (32 tests)
  TestNewsletterClient       — async HTTP client behaviour (8 tests)
  TestSignalConfigAPI        — GET /signal-config/ endpoint (6 tests)
  TestScoresEvaluateSignal   — integration: score → signal → final score (14 tests)
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from app.scoring.signal_penalty import PenaltyResult, SignalPenaltyEngine

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(
    bearish_strong=8.0,
    bearish_moderate=5.0,
    bearish_weak=2.0,
    bullish_bonus_cap=0.0,
    min_n=1,
    min_dw=0.30,
    bearish_threshold=-0.20,
    bullish_threshold=0.20,
    version=1,
):
    """Build a mock SignalPenaltyConfig-like object."""
    return SimpleNamespace(
        bearish_strong_penalty=Decimal(str(bearish_strong)),
        bearish_moderate_penalty=Decimal(str(bearish_moderate)),
        bearish_weak_penalty=Decimal(str(bearish_weak)),
        bullish_strong_bonus_cap=Decimal(str(bullish_bonus_cap)),
        min_n_analysts=min_n,
        min_decay_weight=Decimal(str(min_dw)),
        consensus_bearish_threshold=Decimal(str(bearish_threshold)),
        consensus_bullish_threshold=Decimal(str(bullish_threshold)),
        version=version,
        is_active=True,
    )


def _make_signal(
    signal_strength="strong",
    consensus_score=-0.5,
    n_analysts=3,
    decay_weight=0.80,
):
    """Build a mock Agent 02 signal response dict."""
    return {
        "ticker": "TEST",
        "signal_strength": signal_strength,
        "consensus": {
            "score": Decimal(str(consensus_score)),
            "n_analysts": n_analysts,
        },
        "recommendation": {
            "decay_weight": Decimal(str(decay_weight)),
        },
    }


_ENGINE = SignalPenaltyEngine()
_CFG    = _make_config()


# ═══════════════════════════════════════════════════════════════════════════════
# TestSignalPenaltyEngine
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalPenaltyEngine:
    """Pure computation tests for SignalPenaltyEngine.compute()."""

    # ── Unavailable signal ────────────────────────────────────────────────────

    def test_none_signal_returns_zero_penalty(self):
        pr = _ENGINE.compute(75.0, None, _CFG)
        assert pr.penalty == 0.0
        assert pr.score_after == 75.0
        assert pr.signal_type == "UNAVAILABLE"
        assert pr.agent02_available is False
        assert pr.eligible is False

    def test_none_signal_score_unchanged(self):
        for score in (0.0, 50.0, 100.0):
            pr = _ENGINE.compute(score, None, _CFG)
            assert pr.score_after == score

    # ── Signal type resolution ────────────────────────────────────────────────

    def test_bearish_signal_type_below_threshold(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.21)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.signal_type == "BEARISH"

    def test_bullish_signal_type_above_threshold(self):
        sig = _make_signal(signal_strength="strong", consensus_score=0.21)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.signal_type == "BULLISH"

    def test_neutral_signal_type_in_band(self):
        for score in (-0.19, 0.0, 0.19):
            sig = _make_signal(signal_strength="moderate", consensus_score=score)
            pr = _ENGINE.compute(80.0, sig, _CFG)
            assert pr.signal_type == "NEUTRAL"

    def test_neutral_at_exact_bearish_boundary(self):
        """consensus_score == threshold is not < threshold → NEUTRAL."""
        sig = _make_signal(signal_strength="moderate", consensus_score=-0.20)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.signal_type == "NEUTRAL"

    def test_neutral_at_exact_bullish_boundary(self):
        sig = _make_signal(signal_strength="moderate", consensus_score=0.20)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.signal_type == "NEUTRAL"

    def test_insufficient_strength_overrides_bearish_consensus(self):
        """Even with strongly negative consensus, 'insufficient' strength → INSUFFICIENT."""
        sig = _make_signal(signal_strength="insufficient", consensus_score=-0.90)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.signal_type == "INSUFFICIENT"
        assert pr.penalty == 0.0

    def test_none_consensus_score_gives_insufficient(self):
        sig = _make_signal(consensus_score=0.0)  # start with valid
        sig["consensus"]["score"] = None
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.signal_type == "INSUFFICIENT"
        assert pr.penalty == 0.0

    # ── Bearish penalty amounts ───────────────────────────────────────────────

    def test_bearish_strong_penalty(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=3, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.penalty == 8.0
        assert pr.score_after == 72.0
        assert pr.eligible is True

    def test_bearish_moderate_penalty(self):
        sig = _make_signal(signal_strength="moderate", consensus_score=-0.4, n_analysts=2, decay_weight=0.5)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.penalty == 5.0
        assert pr.score_after == 75.0

    def test_bearish_weak_penalty(self):
        sig = _make_signal(signal_strength="weak", consensus_score=-0.3, n_analysts=1, decay_weight=0.35)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.penalty == 2.0
        assert pr.score_after == 78.0

    # ── Architecture constraint: no bullish inflation ─────────────────────────

    def test_bullish_strong_zero_penalty(self):
        sig = _make_signal(signal_strength="strong", consensus_score=0.8, n_analysts=5, decay_weight=0.9)
        pr = _ENGINE.compute(70.0, sig, _CFG)
        assert pr.penalty == 0.0
        assert pr.score_after == 70.0
        assert pr.eligible is False  # BULLISH never sets eligible

    def test_bullish_with_nonzero_bonus_cap_still_zero(self):
        """Even if someone accidentally sets bullish_bonus_cap > 0, engine pays 0 (not implemented)."""
        sig = _make_signal(signal_strength="strong", consensus_score=0.8)
        pr = _ENGINE.compute(70.0, sig, _CFG)
        assert pr.score_after == pr.score_before  # no inflation

    # ── Eligibility thresholds ────────────────────────────────────────────────

    def test_bearish_insufficient_n_analysts(self):
        """n_analysts below minimum → ineligible → no penalty."""
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=0, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.eligible is False
        assert pr.penalty == 0.0

    def test_bearish_exactly_min_n_analysts(self):
        """n_analysts == min_n_analysts is eligible."""
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=1, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.eligible is True

    def test_bearish_low_decay_weight_ineligible(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=5, decay_weight=0.29)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.eligible is False
        assert pr.penalty == 0.0

    def test_bearish_exactly_min_decay_weight_eligible(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=5, decay_weight=0.30)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.eligible is True
        assert pr.penalty == 8.0

    def test_bearish_none_decay_weight_ineligible(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=5, decay_weight=0.8)
        sig["recommendation"]["decay_weight"] = None
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.eligible is False

    def test_neutral_never_eligible(self):
        sig = _make_signal(signal_strength="strong", consensus_score=0.0, n_analysts=10, decay_weight=1.0)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.eligible is False
        assert pr.penalty == 0.0

    # ── Score floor at 0 ─────────────────────────────────────────────────────

    def test_penalty_floors_at_zero(self):
        """Penalty cannot push score below 0."""
        sig = _make_signal(signal_strength="strong", consensus_score=-0.9, n_analysts=5, decay_weight=0.8)
        pr = _ENGINE.compute(5.0, sig, _CFG)
        assert pr.penalty == 8.0
        assert pr.score_after == 0.0  # not -3.0

    def test_zero_score_stays_zero(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.9, n_analysts=5, decay_weight=0.8)
        pr = _ENGINE.compute(0.0, sig, _CFG)
        assert pr.score_after == 0.0

    # ── PenaltyResult fields ──────────────────────────────────────────────────

    def test_result_has_all_expected_fields(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=3, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert isinstance(pr, PenaltyResult)
        assert pr.signal_strength == "strong"
        assert pr.n_analysts == 3
        assert abs(pr.consensus_score - (-0.5)) < 1e-9
        assert abs(pr.decay_weight - 0.8) < 1e-9
        assert pr.agent02_available is True

    def test_details_dict_populated(self):
        sig = _make_signal(signal_strength="moderate", consensus_score=-0.4, n_analysts=2, decay_weight=0.5)
        pr = _ENGINE.compute(75.0, sig, _CFG)
        d = pr.details
        assert d["signal_type"] == "BEARISH"
        assert d["signal_strength"] == "moderate"
        assert d["penalty_applied"] == 5.0
        assert d["score_before"] == 75.0
        assert d["score_after"] == 70.0
        assert "config_thresholds" in d

    def test_unavailable_details_has_reason(self):
        pr = _ENGINE.compute(80.0, None, _CFG)
        assert "reason" in pr.details

    # ── Custom threshold config ───────────────────────────────────────────────

    def test_custom_bearish_threshold(self):
        cfg = _make_config(bearish_threshold=-0.50, bullish_threshold=0.50)
        # consensus_score = -0.30 → not below -0.50 → NEUTRAL with default cfg
        sig = _make_signal(signal_strength="strong", consensus_score=-0.30, n_analysts=3, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, cfg)
        assert pr.signal_type == "NEUTRAL"
        assert pr.penalty == 0.0

    def test_custom_penalty_amounts(self):
        cfg = _make_config(bearish_strong=15.0, bearish_moderate=10.0, bearish_weak=5.0)
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=3, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, cfg)
        assert pr.penalty == 15.0
        assert pr.score_after == 65.0

    def test_custom_min_n_analysts(self):
        cfg = _make_config(min_n=5)
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=4, decay_weight=0.8)
        pr = _ENGINE.compute(80.0, sig, cfg)
        assert pr.eligible is False  # 4 < 5

    # ── n_analysts as various types ───────────────────────────────────────────

    def test_n_analysts_string_coerced(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=3, decay_weight=0.8)
        sig["consensus"]["n_analysts"] = "3"   # string from JSON
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.n_analysts == 3
        assert pr.eligible is True

    def test_n_analysts_none_means_zero(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5, n_analysts=0, decay_weight=0.8)
        sig["consensus"]["n_analysts"] = None
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert pr.n_analysts == 0
        assert pr.eligible is False

    # ── Decimal coercion (Agent 02 returns Decimal) ───────────────────────────

    def test_decimal_consensus_score_coerced(self):
        sig = _make_signal()
        sig["consensus"]["score"] = Decimal("-0.50")
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert isinstance(pr.consensus_score, float)
        assert pr.signal_type == "BEARISH"

    def test_decimal_decay_weight_coerced(self):
        sig = _make_signal(signal_strength="strong", consensus_score=-0.5)
        sig["recommendation"]["decay_weight"] = Decimal("0.80")
        pr = _ENGINE.compute(80.0, sig, _CFG)
        assert isinstance(pr.decay_weight, float)
        assert pr.eligible is True


# ═══════════════════════════════════════════════════════════════════════════════
# TestNewsletterClient
# ═══════════════════════════════════════════════════════════════════════════════

class TestNewsletterClient:
    """Tests for newsletter_client.fetch_signal()."""

    def test_disabled_returns_none(self):
        from app.scoring import newsletter_client
        with patch("app.scoring.newsletter_client.settings") as mock_settings:
            mock_settings.newsletter_service_enabled = False
            result = asyncio.run(
                newsletter_client.fetch_signal("AAPL")
            )
        assert result is None

    def test_200_returns_parsed_dict(self):
        from app.scoring import newsletter_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"signal_strength": "strong", "consensus": {"score": "-0.5", "n_analysts": 3}}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://agent02"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(
                newsletter_client.fetch_signal("AAPL")
            )

        assert result is not None
        assert result["signal_strength"] == "strong"

    def test_404_returns_none(self):
        from app.scoring import newsletter_client
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://agent02"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(
                newsletter_client.fetch_signal("UNKNOWN")
            )

        assert result is None

    def test_timeout_returns_none(self):
        from app.scoring import newsletter_client
        import httpx

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://agent02"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(
                newsletter_client.fetch_signal("AAPL")
            )

        assert result is None

    def test_connection_error_returns_none(self):
        from app.scoring import newsletter_client

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://agent02"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(
                newsletter_client.fetch_signal("AAPL")
            )

        assert result is None

    def test_500_returns_none(self):
        from app.scoring import newsletter_client
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        ))

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://agent02"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(
                newsletter_client.fetch_signal("AAPL")
            )

        assert result is None

    def test_url_uses_newsletter_service_url_setting(self):
        from app.scoring import newsletter_client

        captured_url = []

        async def _fake_get(url):
            captured_url.append(url)
            m = MagicMock()
            m.status_code = 404
            return m

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://newsletter:8002"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_fake_get)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            asyncio.run(
                newsletter_client.fetch_signal("AAPL")
            )

        assert captured_url == ["http://newsletter:8002/signal/AAPL"]

    def test_ticker_is_included_in_url(self):
        from app.scoring import newsletter_client

        captured = []

        async def _fake_get(url):
            captured.append(url)
            m = MagicMock()
            m.status_code = 404
            return m

        with patch("app.scoring.newsletter_client.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.newsletter_service_enabled = True
            mock_settings.newsletter_service_url = "http://agent02"
            mock_settings.newsletter_timeout = 10

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_fake_get)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            asyncio.run(
                newsletter_client.fetch_signal("SCHD")
            )

        assert "SCHD" in captured[0]


# ═══════════════════════════════════════════════════════════════════════════════
# TestSignalConfigAPI
# ═══════════════════════════════════════════════════════════════════════════════

import time
import jwt as _jwt

_AUTH = {"Authorization": f"Bearer {_jwt.encode({'sub': 'test', 'exp': int(time.time()) + 3600}, 'test-secret-for-tests', algorithm='HS256')}"}


def _fake_signal_config(
    version=1,
    bearish_strong=8.0,
    bearish_moderate=5.0,
    bearish_weak=2.0,
    bullish_cap=0.0,
    min_n=1,
    min_dw=0.30,
    bearish_thr=-0.20,
    bullish_thr=0.20,
    notes=None,
    created_by=None,
):
    """Build a mock SignalPenaltyConfig ORM object."""
    m = MagicMock()
    m.id = uuid.uuid4()
    m.version = version
    m.is_active = True
    m.bearish_strong_penalty = Decimal(str(bearish_strong))
    m.bearish_moderate_penalty = Decimal(str(bearish_moderate))
    m.bearish_weak_penalty = Decimal(str(bearish_weak))
    m.bullish_strong_bonus_cap = Decimal(str(bullish_cap))
    m.min_n_analysts = min_n
    m.min_decay_weight = Decimal(str(min_dw))
    m.consensus_bearish_threshold = Decimal(str(bearish_thr))
    m.consensus_bullish_threshold = Decimal(str(bullish_thr))
    m.created_at = datetime.now(timezone.utc)
    m.created_by = created_by
    m.notes = notes
    return m


class TestSignalConfigAPI:
    """Tests for GET /signal-config/ endpoint (mocked DB)."""

    @pytest.fixture(autouse=True)
    def _client(self):
        with patch("app.main.check_database_connection", return_value={"status": "healthy", "schema_exists": True}):
            with patch("app.scoring.data_client.init_pool", return_value=None):
                with patch("app.scoring.data_client.close_pool", return_value=None):
                    from fastapi.testclient import TestClient
                    from app.main import app
                    from app.database import get_db

                    self._mock_db = MagicMock()
                    app.dependency_overrides[get_db] = lambda: self._mock_db

                    with TestClient(app, raise_server_exceptions=False) as c:
                        self.client = c
                        yield
                    app.dependency_overrides.clear()

    def _setup_config(self, config_obj):
        mq = self._mock_db.query.return_value
        mq.filter.return_value = mq
        mq.first.return_value = config_obj

    def test_returns_403_without_auth(self):
        resp = self.client.get("/signal-config/")
        assert resp.status_code == 403

    def test_returns_404_when_no_config(self):
        self._setup_config(None)
        resp = self.client.get("/signal-config/", headers=_AUTH)
        assert resp.status_code == 404

    def test_returns_200_with_active_config(self):
        self._setup_config(_fake_signal_config())
        resp = self.client.get("/signal-config/", headers=_AUTH)
        assert resp.status_code == 200

    def test_response_shape(self):
        self._setup_config(_fake_signal_config(version=2))
        resp = self.client.get("/signal-config/", headers=_AUTH)
        data = resp.json()
        for key in (
            "id", "version", "is_active",
            "bearish_strong_penalty", "bearish_moderate_penalty", "bearish_weak_penalty",
            "bullish_strong_bonus_cap", "min_n_analysts", "min_decay_weight",
            "consensus_bearish_threshold", "consensus_bullish_threshold",
        ):
            assert key in data, f"Missing key: {key}"
        assert data["bearish_strong_penalty"] == 8.0
        assert data["bullish_strong_bonus_cap"] == 0.0

    def test_bullish_bonus_cap_is_zero(self):
        """Architecture constraint: bullish_strong_bonus_cap must always be 0."""
        self._setup_config(_fake_signal_config(bullish_cap=0.0))
        resp = self.client.get("/signal-config/", headers=_AUTH)
        assert resp.json()["bullish_strong_bonus_cap"] == 0.0

    def test_version_field_present(self):
        self._setup_config(_fake_signal_config(version=7))
        resp = self.client.get("/signal-config/", headers=_AUTH)
        assert resp.json()["version"] == 7


# ═══════════════════════════════════════════════════════════════════════════════
# TestScoresEvaluateSignal
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoresEvaluateSignal:
    """Integration tests: signal penalty wired into /scores/evaluate flow."""

    def test_bearish_strong_reduces_score(self):
        """BEARISH strong signal should subtract 8 pts from total_score."""
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=-0.6, n_analysts=3, decay_weight=0.8)
        pr = engine.compute(80.0, sig, cfg)
        assert pr.score_after == 72.0

    def test_bearish_moderate_reduces_score(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("moderate", consensus_score=-0.4, n_analysts=2, decay_weight=0.5)
        pr = engine.compute(85.0, sig, cfg)
        assert pr.score_after == 80.0

    def test_bearish_weak_reduces_score(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("weak", consensus_score=-0.25, n_analysts=1, decay_weight=0.35)
        pr = engine.compute(90.0, sig, cfg)
        assert pr.score_after == 88.0

    def test_grade_updated_after_penalty(self):
        """Score 88 → BEARISH strong (-8) → 80 → grade should be 'B+' not 'A'."""
        from app.scoring.income_scorer import IncomeScorer
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=-0.6, n_analysts=3, decay_weight=0.8)
        pr = engine.compute(88.0, sig, cfg)  # 88 - 8 = 80
        grade = IncomeScorer._grade(pr.score_after)
        assert grade == "B+"

    def test_recommendation_updated_after_penalty(self):
        """Score 90 → BEARISH strong (-8) → 82 → ACCUMULATE not AGGRESSIVE_BUY."""
        from app.scoring.income_scorer import IncomeScorer
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=-0.6, n_analysts=3, decay_weight=0.8)
        pr = engine.compute(90.0, sig, cfg)  # 90 - 8 = 82
        rec = IncomeScorer._recommendation(pr.score_after)
        assert rec == "ACCUMULATE"

    def test_bullish_no_score_change(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=0.7, n_analysts=5, decay_weight=0.9)
        pr = engine.compute(75.0, sig, cfg)
        assert pr.score_after == 75.0
        assert pr.penalty == 0.0

    def test_neutral_no_score_change(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=0.0, n_analysts=5, decay_weight=0.9)
        pr = engine.compute(75.0, sig, cfg)
        assert pr.score_after == 75.0

    def test_unavailable_signal_no_score_change(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        pr = engine.compute(75.0, None, cfg)
        assert pr.score_after == 75.0
        assert pr.penalty == 0.0

    def test_insufficient_n_analysts_no_score_change(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config(min_n=3)
        sig = _make_signal("strong", consensus_score=-0.6, n_analysts=2, decay_weight=0.8)
        pr = engine.compute(80.0, sig, cfg)
        assert pr.score_after == 80.0

    def test_penalty_never_inflates_score(self):
        """Under no circumstances should score_after > score_before."""
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        for signal_type, consensus in [("strong", 0.9), ("moderate", 0.5), ("weak", 0.3)]:
            sig = _make_signal(signal_type, consensus_score=consensus, n_analysts=5, decay_weight=0.9)
            pr = engine.compute(80.0, sig, cfg)
            assert pr.score_after <= pr.score_before

    def test_details_included_in_result(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=-0.6, n_analysts=3, decay_weight=0.8)
        pr = engine.compute(80.0, sig, cfg)
        assert "signal_type" in pr.details
        assert "penalty_applied" in pr.details
        assert "score_before" in pr.details
        assert "score_after" in pr.details

    def test_sequential_penalties_independent(self):
        """Engine is stateless — two calls with same input give same result."""
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=-0.6, n_analysts=3, decay_weight=0.8)
        pr1 = engine.compute(80.0, sig, cfg)
        pr2 = engine.compute(80.0, sig, cfg)
        assert pr1.penalty == pr2.penalty
        assert pr1.score_after == pr2.score_after

    def test_penalty_at_100_score(self):
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = _make_signal("strong", consensus_score=-0.9, n_analysts=5, decay_weight=0.8)
        pr = engine.compute(100.0, sig, cfg)
        assert pr.score_after == 92.0  # 100 - 8

    def test_missing_recommendation_field_graceful(self):
        """Agent 02 response without 'recommendation' key handled gracefully."""
        engine = SignalPenaltyEngine()
        cfg = _make_config()
        sig = {
            "signal_strength": "strong",
            "consensus": {"score": Decimal("-0.6"), "n_analysts": 3},
            # no "recommendation" key
        }
        pr = engine.compute(80.0, sig, cfg)
        # decay_weight will be None → ineligible
        assert pr.eligible is False
        assert pr.penalty == 0.0
