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
