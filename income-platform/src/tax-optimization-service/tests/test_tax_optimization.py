"""
Agent 05 — Tax Optimization Service
Test suite — covers profiler, calculator, optimizer, harvester, and API routes.

Run from service root:
    pytest tests/ -v
"""
from __future__ import annotations

import os
import time

import jwt as _jwt
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

# Inject JWT_SECRET before any app import so pydantic-settings validation passes
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.main import app
from app.models import (
    AccountType,
    AssetClass,
    FilingStatus,
    HarvestingCandidate,
    HarvestingRequest,
    HoldingInput,
    OptimizationRequest,
    TaxCalculationRequest,
    TaxProfileRequest,
    TaxTreatment,
)
from app.tax.profiler import build_tax_profile, _PROFILE_MAP
from app.tax.calculator import calculate_tax_burden, _ordinary_rate, _qualified_rate
from app.tax.optimizer import optimize_portfolio
from app.tax.harvester import identify_harvesting_opportunities


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_token(secret: str = "test-secret", exp_offset: int = 3600) -> str:
    return _jwt.encode(
        {"sub": "test", "exp": int(time.time()) + exp_offset},
        secret,
        algorithm="HS256",
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    token = _make_token()
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


# ─── Tax Profiler Tests ───────────────────────────────────────────────────────

class TestTaxProfiler:

    @pytest.mark.asyncio
    async def test_covered_call_etf_profile(self):
        req = TaxProfileRequest(symbol="JEPI", asset_class=AssetClass.COVERED_CALL_ETF)
        result = await build_tax_profile(req)
        assert result.symbol == "JEPI"
        assert result.asset_class == AssetClass.COVERED_CALL_ETF
        assert result.primary_tax_treatment == TaxTreatment.ORDINARY_INCOME
        assert result.qualified_dividend_eligible is False
        assert result.section_1256_eligible is True
        assert result.k1_required is False
        assert result.asset_class_fallback is False

    @pytest.mark.asyncio
    async def test_dividend_stock_profile(self):
        req = TaxProfileRequest(symbol="JNJ", asset_class=AssetClass.DIVIDEND_STOCK)
        result = await build_tax_profile(req)
        assert result.primary_tax_treatment == TaxTreatment.QUALIFIED_DIVIDEND
        assert result.qualified_dividend_eligible is True

    @pytest.mark.asyncio
    async def test_reit_profile(self):
        req = TaxProfileRequest(symbol="O", asset_class=AssetClass.REIT)
        result = await build_tax_profile(req)
        assert result.section_199a_eligible is True
        assert result.primary_tax_treatment == TaxTreatment.REIT_DISTRIBUTION

    @pytest.mark.asyncio
    async def test_mlp_profile(self):
        req = TaxProfileRequest(symbol="EPD", asset_class=AssetClass.MLP)
        result = await build_tax_profile(req)
        assert result.k1_required is True

    @pytest.mark.asyncio
    async def test_agent04_fallback_when_unavailable(self):
        """When Agent 04 is down and no asset_class provided, should default to ORDINARY_INCOME."""
        with patch(
            "app.tax.profiler._classify_via_agent04",
            new_callable=AsyncMock,
            return_value=None,
        ):
            req = TaxProfileRequest(symbol="UNKNOWN_TICKER")
            result = await build_tax_profile(req)
            assert result.asset_class == AssetClass.ORDINARY_INCOME
            assert result.asset_class_fallback is True

    @pytest.mark.asyncio
    async def test_agent04_success_path(self):
        """When Agent 04 returns a class, use it."""
        with patch(
            "app.tax.profiler._classify_via_agent04",
            new_callable=AsyncMock,
            return_value=AssetClass.BOND_ETF,
        ):
            req = TaxProfileRequest(symbol="AGG")
            result = await build_tax_profile(req)
            assert result.asset_class == AssetClass.BOND_ETF
            assert result.asset_class_fallback is False

    def test_all_asset_classes_have_mapping(self):
        """Every AssetClass member must have an entry in the profile map."""
        for ac in AssetClass:
            assert ac in _PROFILE_MAP or ac == AssetClass.UNKNOWN, \
                f"Missing profile map entry for {ac}"


# ─── Tax Calculator Tests ─────────────────────────────────────────────────────

class TestTaxCalculator:

    @pytest.mark.asyncio
    async def test_tax_sheltered_account_zero_tax(self):
        req = TaxCalculationRequest(
            symbol="JEPI",
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
            account_type=AccountType.ROTH_IRA,
            distribution_amount=1_000,
            asset_class=AssetClass.COVERED_CALL_ETF,
        )
        result = await calculate_tax_burden(req)
        assert result.total_tax_owed == 0.0
        assert result.net_distribution == 1_000.0
        assert result.effective_tax_rate == 0.0

    @pytest.mark.asyncio
    async def test_ordinary_income_taxed_at_marginal_rate(self):
        req = TaxCalculationRequest(
            symbol="BND",
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
            state_code="FL",          # 0% state
            account_type=AccountType.TAXABLE,
            distribution_amount=1_000,
            asset_class=AssetClass.BOND_ETF,
        )
        result = await calculate_tax_burden(req)
        # $100k single → 22% bracket; FL = 0% state
        assert result.federal_tax_owed == pytest.approx(220.0, rel=0.05)
        assert result.state_tax_owed == 0.0
        assert result.net_distribution < 1_000.0

    @pytest.mark.asyncio
    async def test_qualified_dividend_lower_rate_than_ordinary(self):
        """Qualified dividend rate must be ≤ ordinary rate for same income level."""
        income = 80_000
        filing = FilingStatus.SINGLE
        ordinary = _ordinary_rate(income, filing)
        qualified = _qualified_rate(income, filing)
        assert qualified <= ordinary

    @pytest.mark.asyncio
    async def test_return_of_capital_not_taxed(self):
        """If primary treatment is ROC, federal and state tax owed should be 0."""
        # We can simulate by using a custom mock
        with patch(
            "app.tax.calculator.build_tax_profile",
            new_callable=AsyncMock,
        ) as mock_profile:
            from app.models import TaxProfileResponse
            mock_profile.return_value = TaxProfileResponse(
                symbol="TEST",
                asset_class=AssetClass.CLOSED_END_FUND,
                primary_tax_treatment=TaxTreatment.RETURN_OF_CAPITAL,
                qualified_dividend_eligible=False,
                section_199a_eligible=False,
                section_1256_eligible=False,
                k1_required=False,
            )
            req = TaxCalculationRequest(
                symbol="TEST",
                annual_income=100_000,
                filing_status=FilingStatus.SINGLE,
                account_type=AccountType.TAXABLE,
                distribution_amount=500,
                asset_class=AssetClass.CLOSED_END_FUND,
            )
            result = await calculate_tax_burden(req)
            assert result.federal_tax_owed == 0.0

    @pytest.mark.asyncio
    async def test_niit_applied_high_income(self):
        """NIIT (3.8%) should apply above $200k single."""
        req = TaxCalculationRequest(
            symbol="O",
            annual_income=250_000,
            filing_status=FilingStatus.SINGLE,
            state_code="FL",
            account_type=AccountType.TAXABLE,
            distribution_amount=1_000,
            asset_class=AssetClass.REIT,
        )
        result = await calculate_tax_burden(req)
        assert result.niit_owed > 0

    @pytest.mark.asyncio
    async def test_niit_not_applied_low_income(self):
        req = TaxCalculationRequest(
            symbol="O",
            annual_income=50_000,
            filing_status=FilingStatus.SINGLE,
            state_code="FL",
            account_type=AccountType.TAXABLE,
            distribution_amount=1_000,
            asset_class=AssetClass.REIT,
        )
        result = await calculate_tax_burden(req)
        assert result.niit_owed == 0.0

    @pytest.mark.asyncio
    async def test_state_tax_applied(self):
        """CA (13.3%) should produce meaningful state tax."""
        req = TaxCalculationRequest(
            symbol="JEPI",
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
            state_code="CA",
            account_type=AccountType.TAXABLE,
            distribution_amount=1_000,
            asset_class=AssetClass.COVERED_CALL_ETF,
        )
        result = await calculate_tax_burden(req)
        assert result.state_tax_owed > 50.0


# ─── Tax Optimizer Tests ──────────────────────────────────────────────────────

class TestTaxOptimizer:

    @pytest.mark.asyncio
    async def test_reit_recommended_for_shelter(self):
        req = OptimizationRequest(
            holdings=[
                HoldingInput(
                    symbol="O",
                    asset_class=AssetClass.REIT,
                    account_type=AccountType.TAXABLE,
                    current_value=50_000,
                    annual_yield=0.06,
                )
            ],
            annual_income=120_000,
            filing_status=FilingStatus.SINGLE,
            state_code="NY",
        )
        result = await optimize_portfolio(req)
        if result.placement_recommendations:
            rec = result.placement_recommendations[0]
            assert rec.recommended_account in (AccountType.ROTH_IRA, AccountType.TRAD_IRA)

    @pytest.mark.asyncio
    async def test_mlp_never_in_ira(self):
        req = OptimizationRequest(
            holdings=[
                HoldingInput(
                    symbol="EPD",
                    asset_class=AssetClass.MLP,
                    account_type=AccountType.TAXABLE,
                    current_value=20_000,
                    annual_yield=0.07,
                )
            ],
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        # MLP must stay in TAXABLE
        for rec in result.placement_recommendations:
            if rec.symbol == "EPD":
                assert rec.recommended_account == AccountType.TAXABLE

    @pytest.mark.asyncio
    async def test_savings_non_negative(self):
        req = OptimizationRequest(
            holdings=[
                HoldingInput(
                    symbol="BND",
                    asset_class=AssetClass.BOND_ETF,
                    account_type=AccountType.TAXABLE,
                    current_value=30_000,
                    annual_yield=0.04,
                )
            ],
            annual_income=90_000,
            filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        assert result.estimated_annual_savings >= 0.0


# ─── Tax Harvester Tests ──────────────────────────────────────────────────────

class TestTaxHarvester:

    @pytest.mark.asyncio
    async def test_gain_position_skipped(self):
        req = HarvestingRequest(
            candidates=[
                HarvestingCandidate(
                    symbol="AAPL",
                    current_value=10_000,
                    cost_basis=8_000,        # gain
                    holding_period_days=400,
                    account_type=AccountType.TAXABLE,
                )
            ],
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
        )
        result = await identify_harvesting_opportunities(req)
        # No harvestable losses
        assert result.total_harvestable_losses == 0.0

    @pytest.mark.asyncio
    async def test_qualified_loss_harvested(self):
        req = HarvestingRequest(
            candidates=[
                HarvestingCandidate(
                    symbol="JEPI",
                    current_value=9_000,
                    cost_basis=11_000,       # $2000 loss
                    holding_period_days=400,
                    account_type=AccountType.TAXABLE,
                )
            ],
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
            state_code="FL",
        )
        result = await identify_harvesting_opportunities(req)
        assert result.total_harvestable_losses == 2_000.0
        assert result.total_estimated_tax_savings > 0
        assert any(op.action == "HARVEST_NOW" for op in result.opportunities)

    @pytest.mark.asyncio
    async def test_wash_sale_risk_flagged(self):
        req = HarvestingRequest(
            candidates=[
                HarvestingCandidate(
                    symbol="SPY",
                    current_value=5_000,
                    cost_basis=6_000,
                    holding_period_days=15,  # < 30 days → wash sale risk
                    account_type=AccountType.TAXABLE,
                )
            ],
            annual_income=100_000,
            filing_status=FilingStatus.SINGLE,
            wash_sale_check=True,
        )
        result = await identify_harvesting_opportunities(req)
        assert len(result.wash_sale_warnings) > 0
        assert any(op.wash_sale_risk for op in result.opportunities)

    @pytest.mark.asyncio
    async def test_sheltered_account_no_benefit(self):
        req = HarvestingRequest(
            candidates=[
                HarvestingCandidate(
                    symbol="O",
                    current_value=4_000,
                    cost_basis=5_000,
                    holding_period_days=200,
                    account_type=AccountType.ROTH_IRA,
                )
            ],
            annual_income=80_000,
            filing_status=FilingStatus.SINGLE,
        )
        result = await identify_harvesting_opportunities(req)
        assert result.total_harvestable_losses == 0.0
        assert any(op.action == "HOLD" for op in result.opportunities)

    @pytest.mark.asyncio
    async def test_small_loss_monitored_not_harvested(self):
        req = HarvestingRequest(
            candidates=[
                HarvestingCandidate(
                    symbol="XOM",
                    current_value=9_950,
                    cost_basis=10_000,   # only $50 loss
                    holding_period_days=200,
                    account_type=AccountType.TAXABLE,
                )
            ],
            annual_income=80_000,
            filing_status=FilingStatus.SINGLE,
        )
        result = await identify_harvesting_opportunities(req)
        assert any(op.action == "MONITOR" for op in result.opportunities)


# ─── API Route Tests ──────────────────────────────────────────────────────────

class TestAPIRoutes:

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == 5
        assert data["service"] == "tax-optimization-service"

    @pytest.mark.asyncio
    async def test_profile_get_with_asset_class(self, client):
        resp = await client.get(
            "/tax/profile/JEPI",
            params={"asset_class": "COVERED_CALL_ETF"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "JEPI"
        assert data["asset_class"] == "COVERED_CALL_ETF"

    @pytest.mark.asyncio
    async def test_calculate_post(self, client):
        payload = {
            "symbol": "BND",
            "annual_income": 75000,
            "filing_status": "SINGLE",
            "state_code": "TX",
            "account_type": "TAXABLE",
            "distribution_amount": 500,
            "asset_class": "BOND_ETF",
        }
        resp = await client.post("/tax/calculate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["net_distribution"] < 500

    @pytest.mark.asyncio
    async def test_optimize_post(self, client):
        payload = {
            "holdings": [
                {
                    "symbol": "O",
                    "asset_class": "REIT",
                    "account_type": "TAXABLE",
                    "current_value": 25000,
                    "annual_yield": 0.06,
                }
            ],
            "annual_income": 100000,
            "filing_status": "SINGLE",
            "state_code": "FL",
        }
        resp = await client.post("/tax/optimize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "estimated_annual_savings" in data

    @pytest.mark.asyncio
    async def test_harvest_post(self, client):
        payload = {
            "candidates": [
                {
                    "symbol": "JEPI",
                    "current_value": 8000,
                    "cost_basis": 10000,
                    "holding_period_days": 500,
                    "account_type": "TAXABLE",
                }
            ],
            "annual_income": 90000,
            "filing_status": "SINGLE",
            "state_code": "TX",
            "wash_sale_check": True,
        }
        resp = await client.post("/tax/harvest", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_harvestable_losses"] == 2000.0

    @pytest.mark.asyncio
    async def test_asset_classes_reference_endpoint(self, client):
        resp = await client.get("/tax/asset-classes")
        assert resp.status_code == 200
        data = resp.json()
        assert "COVERED_CALL_ETF" in data
        assert "REIT" in data
        assert "MLP" in data

    @pytest.mark.asyncio
    async def test_optimize_empty_holdings_422(self, client):
        payload = {
            "holdings": [],
            "annual_income": 100000,
            "filing_status": "SINGLE",
        }
        resp = await client.post("/tax/optimize", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_harvest_empty_candidates_422(self, client):
        payload = {
            "candidates": [],
            "annual_income": 80000,
            "filing_status": "SINGLE",
        }
        resp = await client.post("/tax/harvest", json=payload)
        assert resp.status_code == 422


class TestTaxPlacement:
    @pytest.mark.asyncio
    async def test_placement_covered_call_etf_recommends_roth(self, client):
        """COVERED_CALL_ETF with high income should recommend ROTH_IRA."""
        resp = await client.post("/tax/placement", json={
            "ticker": "JEPI",
            "asset_class": "COVERED_CALL_ETF",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommended_account"] in ("ROTH_IRA", "TRAD_IRA")
        assert "reason" in data
        assert "asset_class" in data

    @pytest.mark.asyncio
    async def test_placement_mlp_always_taxable(self, client):
        """MLP must never be sheltered (UBTI issue in IRAs)."""
        resp = await client.post("/tax/placement", json={
            "ticker": "EPD",
            "asset_class": "MLP",
        })
        assert resp.status_code == 200
        assert resp.json()["recommended_account"] == "TAXABLE"

    @pytest.mark.asyncio
    async def test_placement_dividend_stock_taxable_friendly(self, client):
        """DIVIDEND_STOCK with qualified dividends is fine in TAXABLE."""
        resp = await client.post("/tax/placement", json={
            "ticker": "JNJ",
            "asset_class": "DIVIDEND_STOCK",
        })
        assert resp.status_code == 200
        assert resp.json()["recommended_account"] == "TAXABLE"


class TestHoldingsAnalysis:
    @pytest.mark.asyncio
    async def test_portfolio_optimize_returns_holdings_analysis(self, client):
        """POST /tax/optimize must return holdings_analysis for ALL holdings."""
        resp = await client.post("/tax/optimize", json={
            "holdings": [
                {
                    "symbol": "ECC",
                    "asset_class": "CLOSED_END_FUND",
                    "account_type": "TAXABLE",
                    "current_value": 10000.0,
                    "annual_yield": 0.42,
                    "expense_ratio": 0.012,
                },
                {
                    "symbol": "O",
                    "asset_class": "REIT",
                    "account_type": "ROTH_IRA",
                    "current_value": 5000.0,
                    "annual_yield": 0.054,
                    "expense_ratio": None,
                },
            ],
            "annual_income": 150000.0,
            "filing_status": "SINGLE",
            "state_code": "CA",
        })
        assert resp.status_code == 200
        data = resp.json()

        # Both holdings must appear (not just suboptimal ones)
        assert "holdings_analysis" in data
        assert len(data["holdings_analysis"]) == 2

        # portfolio-level NAA fields
        assert "portfolio_nay" in data
        assert "portfolio_gross_yield" in data
        assert "suboptimal_count" in data
        assert isinstance(data["portfolio_nay"], float)

        # Per-holding fields
        ecc = next(h for h in data["holdings_analysis"] if h["symbol"] == "ECC")
        assert ecc["treatment"] is not None
        assert ecc["effective_tax_rate"] > 0
        assert ecc["after_tax_yield"] < ecc["gross_yield"]
        assert ecc["nay"] <= ecc["after_tax_yield"]  # expense drag reduces further
        assert ecc["placement_mismatch"] is True   # CLOSED_END_FUND in TAXABLE

        # Optimally placed holding
        o_holding = next(h for h in data["holdings_analysis"] if h["symbol"] == "O")
        assert o_holding["placement_mismatch"] is False  # REIT in ROTH_IRA is fine
