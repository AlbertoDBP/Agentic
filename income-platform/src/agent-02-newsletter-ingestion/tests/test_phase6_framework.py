"""
Agent 02 — Phase 6 tests: Framework extractor (Pass 2)
"""
import pytest
from unittest.mock import patch, MagicMock


class TestFrameworkExtractor:
    def test_extract_frameworks_returns_list_for_valid_response(self):
        from app.processors.framework_extractor import extract_frameworks
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='[{"ticker":"ARCC","valuation_metrics_cited":["FFO_coverage"],"thresholds_identified":{},"reasoning_structure":"bottom_up","conviction_level":"high","catalysts":[],"price_guidance_type":"none","price_guidance_value":null,"risk_factors_cited":[],"macro_factors":[],"evaluation_narrative":"Test narrative"}]')]
        with patch("app.processors.framework_extractor._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = extract_frameworks("article markdown", {"tickers": []}, "art_001")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["ticker"] == "ARCC"

    def test_extract_frameworks_returns_empty_list_on_api_failure(self):
        from app.processors.framework_extractor import extract_frameworks
        with patch("app.processors.framework_extractor._client") as mock_client:
            mock_client.messages.create.side_effect = Exception("API timeout")
            result = extract_frameworks("article markdown", {}, "art_002")
        assert result == []

    def test_extract_frameworks_returns_empty_list_on_invalid_json(self):
        from app.processors.framework_extractor import extract_frameworks
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not json")]
        with patch("app.processors.framework_extractor._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = extract_frameworks("article markdown", {}, "art_003")
        assert result == []

    def test_extract_frameworks_validates_required_fields(self):
        from app.processors.framework_extractor import validate_framework
        good = {
            "ticker": "JNJ", "valuation_metrics_cited": [],
            "thresholds_identified": {}, "reasoning_structure": "bottom_up",
            "conviction_level": "high", "catalysts": [],
            "price_guidance_type": "none", "price_guidance_value": None,
            "risk_factors_cited": [], "macro_factors": [],
            "evaluation_narrative": "narrative"
        }
        assert validate_framework(good) == good

    def test_validate_framework_returns_none_for_missing_ticker(self):
        from app.processors.framework_extractor import validate_framework
        bad = {"valuation_metrics_cited": [], "reasoning_structure": "bottom_up"}
        assert validate_framework(bad) is None

    def test_price_guidance_type_defaults_to_none_string(self):
        from app.processors.framework_extractor import validate_framework
        fw = {
            "ticker": "T", "valuation_metrics_cited": [],
            "thresholds_identified": {}, "reasoning_structure": "bottom_up",
            "conviction_level": "low", "catalysts": [],
            "risk_factors_cited": [], "macro_factors": [],
            "evaluation_narrative": "x"
            # price_guidance_type intentionally missing
        }
        result = validate_framework(fw)
        assert result["price_guidance_type"] == "none"

    def test_extract_frameworks_returns_empty_list_when_client_is_none(self):
        from app.processors.framework_extractor import extract_frameworks
        with patch("app.processors.framework_extractor._client", None):
            result = extract_frameworks("article markdown", {}, "art_004")
        assert result == []

    def test_extract_frameworks_returns_empty_list_when_response_is_dict_not_list(self):
        from app.processors.framework_extractor import extract_frameworks
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"ticker": "ARCC"}')]
        with patch("app.processors.framework_extractor._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = extract_frameworks("article markdown", {}, "art_005")
        assert result == []

    def test_validate_framework_uppercases_ticker(self):
        from app.processors.framework_extractor import validate_framework
        fw = {
            "ticker": "arcc", "valuation_metrics_cited": [],
            "thresholds_identified": {}, "reasoning_structure": "bottom_up",
            "conviction_level": "high", "catalysts": [],
            "price_guidance_type": "none", "price_guidance_value": None,
            "risk_factors_cited": [], "macro_factors": [],
            "evaluation_narrative": "x"
        }
        result = validate_framework(fw)
        assert result["ticker"] == "ARCC"


class TestSuggestionStore:
    def test_compute_expires_at_bdc(self):
        from app.processors.suggestion_store import compute_expires_at
        from datetime import datetime, timezone, timedelta
        sourced = datetime(2026, 3, 26, tzinfo=timezone.utc)
        expires = compute_expires_at(sourced, "BDC")
        assert expires == sourced + timedelta(days=45)

    def test_compute_expires_at_dividend_stock(self):
        from app.processors.suggestion_store import compute_expires_at
        from datetime import datetime, timezone, timedelta
        sourced = datetime(2026, 3, 26, tzinfo=timezone.utc)
        expires = compute_expires_at(sourced, "DIVIDEND_STOCK")
        assert expires == sourced + timedelta(days=60)

    def test_compute_expires_at_defaults_to_45_days(self):
        from app.processors.suggestion_store import compute_expires_at
        from datetime import datetime, timezone, timedelta
        sourced = datetime(2026, 3, 26, tzinfo=timezone.utc)
        expires = compute_expires_at(sourced, "UNKNOWN_CLASS")
        assert expires == sourced + timedelta(days=45)

    def test_upsert_suggestion_calls_db_with_correct_params(self):
        from app.processors.suggestion_store import upsert_suggestion
        mock_db = MagicMock()
        mock_db.execute = MagicMock()
        from datetime import datetime, timezone
        upsert_suggestion(
            db=mock_db,
            analyst_id=1,
            article_framework_id=10,
            ticker="ARCC",
            asset_class="BDC",
            recommendation="BUY",
            sentiment_score=0.75,
            price_guidance_type="none",
            price_guidance_value=None,
            sourced_at=datetime(2026, 3, 26, tzinfo=timezone.utc),
        )
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        # Verify params dict passed to execute
        params = call_args[0][1]
        assert params["ticker"] == "ARCC"
        assert params["recommendation"] == "BUY"
        assert params["analyst_id"] == 1

    def test_should_write_suggestion_true_for_buy(self):
        from app.processors.suggestion_store import should_write_suggestion
        assert should_write_suggestion("StrongBuy") is True
        assert should_write_suggestion("Buy") is True

    def test_should_write_suggestion_true_for_sell(self):
        from app.processors.suggestion_store import should_write_suggestion
        assert should_write_suggestion("StrongSell") is True
        assert should_write_suggestion("Sell") is True

    def test_should_write_suggestion_false_for_hold(self):
        from app.processors.suggestion_store import should_write_suggestion
        assert should_write_suggestion("Hold") is False
        assert should_write_suggestion(None) is False
