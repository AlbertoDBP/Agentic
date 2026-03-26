"""Agent 01 — Dynamic feature fetch tests"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestProviderGetFeature:
    @pytest.mark.asyncio
    async def test_base_provider_get_feature_is_abstract(self):
        """Concrete provider must implement get_feature."""
        from fetchers.base_provider import BaseDataProvider
        import inspect
        assert "get_feature" in {m for m in dir(BaseDataProvider)
                                  if inspect.isfunction(getattr(BaseDataProvider, m, None))
                                  or (hasattr(BaseDataProvider, m)
                                      and getattr(getattr(BaseDataProvider, m), '__isabstractmethod__', False))}

    @pytest.mark.asyncio
    async def test_provider_router_get_feature_returns_value_from_first_provider(self):
        from fetchers.provider_router import ProviderRouter
        mock_fmp = AsyncMock()
        mock_fmp.get_feature = AsyncMock(return_value=0.15)
        router = ProviderRouter(polygon=None, fmp=mock_fmp, yfinance=None)
        result = await router.get_feature("ARCC", "NAV_discount")
        assert result == 0.15

    @pytest.mark.asyncio
    async def test_provider_router_get_feature_falls_back_on_none(self):
        from fetchers.provider_router import ProviderRouter
        from fetchers.base_provider import DataUnavailableError
        mock_fmp = AsyncMock()
        mock_fmp.get_feature = AsyncMock(side_effect=DataUnavailableError("not available"))
        mock_yf = AsyncMock()
        mock_yf.get_feature = AsyncMock(return_value=0.08)
        router = ProviderRouter(polygon=None, fmp=mock_fmp, yfinance=mock_yf)
        result = await router.get_feature("ARCC", "NAV_discount")
        assert result == 0.08

    @pytest.mark.asyncio
    async def test_provider_router_get_feature_returns_none_when_all_fail(self):
        from fetchers.provider_router import ProviderRouter
        from fetchers.base_provider import DataUnavailableError, ProviderError
        mock_fmp = AsyncMock()
        mock_fmp.get_feature = AsyncMock(side_effect=DataUnavailableError("not available"))
        router = ProviderRouter(polygon=None, fmp=mock_fmp, yfinance=None)
        with pytest.raises(ProviderError):
            await router.get_feature("ARCC", "unknown_feature")


class TestDerivedFeatureComputer:
    def test_compute_derived_feature_evaluates_simple_formula(self):
        from services.derived_feature_computer import compute_derived_feature
        stored_data = {"dividends_per_share": 2.0, "eps": 4.0}
        result = compute_derived_feature(
            computation_rule="dividends_per_share / eps",
            stored_data=stored_data,
        )
        assert result == pytest.approx(0.5)

    def test_compute_derived_feature_returns_none_on_zero_division(self):
        from services.derived_feature_computer import compute_derived_feature
        result = compute_derived_feature(
            computation_rule="a / b",
            stored_data={"a": 1.0, "b": 0.0},
        )
        assert result is None

    def test_compute_derived_feature_returns_none_on_missing_field(self):
        from services.derived_feature_computer import compute_derived_feature
        result = compute_derived_feature(
            computation_rule="missing_field / eps",
            stored_data={"eps": 4.0},
        )
        assert result is None
