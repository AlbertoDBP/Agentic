"""
Agent 05 — Tax Optimization Service
Extended test suite — deep coverage of internals and edge cases.
Target: 115+ tests covering calculator internals, profiler completeness,
optimizer heuristics, harvester boundary conditions, and API auth.
"""
from __future__ import annotations

import os
import time

import jwt as _jwt
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

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
from app.tax.calculator import (
    calculate_tax_burden,
    _ordinary_rate,
    _qualified_rate,
    _marginal_rate,
    _niit_applicable,
    _state_rate,
    _is_tax_sheltered,
    _ORDINARY_BRACKETS,
    _QUALIFIED_BRACKETS,
    _NIIT_THRESHOLD,
    _STATE_RATES,
)
from app.tax.harvester import (
    identify_harvesting_opportunities,
    _tax_value_of_loss,
    _wash_sale_risk,
    _MIN_HARVEST_LOSS,
    _WASH_SALE_WINDOW,
)
from app.tax.optimizer import (
    optimize_portfolio,
    _best_shelter_account,
    _SHELTER_PRIORITY,
    _TAXABLE_FRIENDLY,
    _NEVER_SHELTER,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_token(secret: str = "test-secret", exp_offset: int = 3600) -> str:
    return _jwt.encode(
        {"sub": "test", "exp": int(time.time()) + exp_offset},
        secret,
        algorithm="HS256",
    )


@pytest_asyncio.fixture
async def client():
    headers = {"Authorization": f"Bearer {_make_token()}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def unauth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_calc_req(**kw) -> TaxCalculationRequest:
    defaults = dict(
        symbol="JEPI",
        annual_income=100_000,
        filing_status=FilingStatus.SINGLE,
        state_code="FL",
        account_type=AccountType.TAXABLE,
        distribution_amount=1_000,
        asset_class=AssetClass.COVERED_CALL_ETF,
    )
    defaults.update(kw)
    return TaxCalculationRequest(**defaults)


def _make_harvest_req(candidates, **kw) -> HarvestingRequest:
    defaults = dict(
        annual_income=100_000,
        filing_status=FilingStatus.SINGLE,
        state_code="FL",
        wash_sale_check=False,
    )
    defaults.update(kw)
    return HarvestingRequest(candidates=candidates, **defaults)


def _candidate(symbol="JEPI", current=9_000, basis=10_000, days=400,
               account=AccountType.TAXABLE) -> HarvestingCandidate:
    return HarvestingCandidate(
        symbol=symbol,
        current_value=current,
        cost_basis=basis,
        holding_period_days=days,
        account_type=account,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Calculator — internal helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestMarginalRate:
    def test_zero_income_lowest_bracket(self):
        brackets = [(10_000, 0.10), (float("inf"), 0.22)]
        assert _marginal_rate(0, brackets) == 0.10

    def test_income_at_boundary(self):
        brackets = [(10_000, 0.10), (float("inf"), 0.22)]
        assert _marginal_rate(10_000, brackets) == 0.10

    def test_income_above_boundary(self):
        brackets = [(10_000, 0.10), (float("inf"), 0.22)]
        assert _marginal_rate(10_001, brackets) == 0.22

    def test_very_high_income_top_bracket(self):
        rate = _ordinary_rate(10_000_000, FilingStatus.SINGLE)
        assert rate == 0.37


class TestOrdinaryRate:
    @pytest.mark.parametrize("filing", list(FilingStatus))
    def test_all_filing_statuses_return_rate(self, filing):
        rate = _ordinary_rate(100_000, filing)
        assert 0 < rate <= 0.37

    def test_married_joint_higher_threshold_than_single(self):
        # At $80k, single is in 22% bracket; married joint is in 12%
        single = _ordinary_rate(80_000, FilingStatus.SINGLE)
        mj     = _ordinary_rate(80_000, FilingStatus.MARRIED_JOINT)
        assert mj <= single

    def test_low_income_10pct(self):
        assert _ordinary_rate(5_000, FilingStatus.SINGLE) == 0.10

    def test_high_income_37pct(self):
        assert _ordinary_rate(700_000, FilingStatus.SINGLE) == 0.37


class TestQualifiedRate:
    @pytest.mark.parametrize("filing", list(FilingStatus))
    def test_all_filing_statuses_return_rate(self, filing):
        rate = _qualified_rate(100_000, filing)
        assert 0 <= rate <= 0.20

    def test_low_income_zero_pct_qualified(self):
        assert _qualified_rate(20_000, FilingStatus.SINGLE) == 0.00

    def test_high_income_20pct_qualified(self):
        assert _qualified_rate(600_000, FilingStatus.SINGLE) == 0.20

    def test_always_le_ordinary(self):
        for filing in FilingStatus:
            for income in [30_000, 80_000, 200_000, 500_000]:
                assert _qualified_rate(income, filing) <= _ordinary_rate(income, filing)


class TestNIIT:
    def test_above_threshold_single(self):
        assert _niit_applicable(250_000, FilingStatus.SINGLE) is True

    def test_below_threshold_single(self):
        assert _niit_applicable(150_000, FilingStatus.SINGLE) is False

    def test_married_joint_threshold_higher(self):
        # At $220k, single triggers NIIT but married joint does not
        assert _niit_applicable(220_000, FilingStatus.SINGLE) is True
        assert _niit_applicable(220_000, FilingStatus.MARRIED_JOINT) is False

    def test_married_separate_lower_threshold(self):
        assert _niit_applicable(130_000, FilingStatus.MARRIED_SEPARATE) is True

    def test_exactly_at_threshold_not_triggered(self):
        # $200k exactly — not above threshold
        assert _niit_applicable(200_000, FilingStatus.SINGLE) is False


class TestStateRate:
    def test_florida_zero(self):
        assert _state_rate("FL") == 0.00

    def test_texas_zero(self):
        assert _state_rate("TX") == 0.00

    def test_california_high(self):
        assert _state_rate("CA") == pytest.approx(0.133)

    def test_none_returns_zero(self):
        assert _state_rate(None) == 0.00

    def test_unknown_state_returns_default(self):
        # Default is 5% for unknown states
        assert _state_rate("ZZ") == 0.05

    def test_case_insensitive(self):
        assert _state_rate("fl") == _state_rate("FL")

    def test_all_50_states_plus_dc_in_table(self):
        # 50 states + DC = 51 entries
        assert len(_STATE_RATES) == 51


class TestIsTaxSheltered:
    @pytest.mark.parametrize("sheltered", [
        AccountType.TRAD_IRA, AccountType.ROTH_IRA,
        AccountType.HSA, AccountType.FOUR01K,
    ])
    def test_sheltered_accounts(self, sheltered):
        assert _is_tax_sheltered(sheltered) is True

    def test_taxable_not_sheltered(self):
        assert _is_tax_sheltered(AccountType.TAXABLE) is False


# ─────────────────────────────────────────────────────────────────────────────
# Calculator — calculate_tax_burden edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateTaxBurdenEdgeCases:
    @pytest.mark.asyncio
    async def test_all_sheltered_account_types_zero_tax(self):
        for acct in [AccountType.TRAD_IRA, AccountType.ROTH_IRA, AccountType.HSA, AccountType.FOUR01K]:
            req = _make_calc_req(account_type=acct)
            result = await calculate_tax_burden(req)
            assert result.total_tax_owed == 0.0
            assert result.net_distribution == 1_000.0

    @pytest.mark.asyncio
    async def test_zero_distribution_no_division_error(self):
        req = _make_calc_req(distribution_amount=0)
        result = await calculate_tax_burden(req)
        assert result.effective_tax_rate == 0.0

    @pytest.mark.asyncio
    async def test_tax_exempt_treatment_zero_federal(self):
        # BOND_ETF secondary includes TAX_EXEMPT; mock build_tax_profile to return TAX_EXEMPT
        from app.models import TaxProfileResponse
        with patch(
            "app.tax.calculator.build_tax_profile",
            new_callable=AsyncMock,
            return_value=TaxProfileResponse(
                symbol="MUB",
                asset_class=AssetClass.BOND_ETF,
                primary_tax_treatment=TaxTreatment.TAX_EXEMPT,
                qualified_dividend_eligible=False,
                section_199a_eligible=False,
                section_1256_eligible=False,
                k1_required=False,
            ),
        ):
            req = _make_calc_req(symbol="MUB", asset_class=AssetClass.BOND_ETF)
            result = await calculate_tax_burden(req)
            assert result.federal_tax_owed == 0.0

    @pytest.mark.asyncio
    async def test_section_1256_blended_rate(self):
        """60/40 rate must be between qualified and ordinary rates."""
        req = _make_calc_req(
            asset_class=AssetClass.COVERED_CALL_ETF,
            annual_income=100_000,
        )
        from app.models import TaxProfileResponse
        with patch(
            "app.tax.calculator.build_tax_profile",
            new_callable=AsyncMock,
            return_value=TaxProfileResponse(
                symbol="JEPI",
                asset_class=AssetClass.COVERED_CALL_ETF,
                primary_tax_treatment=TaxTreatment.SECTION_1256_60_40,
                qualified_dividend_eligible=False,
                section_199a_eligible=False,
                section_1256_eligible=True,
                k1_required=False,
            ),
        ):
            result = await calculate_tax_burden(req)
            ord_rate = _ordinary_rate(100_000, FilingStatus.SINGLE)
            qua_rate = _qualified_rate(100_000, FilingStatus.SINGLE)
            blended_upper = 1_000 * ord_rate
            blended_lower = 1_000 * qua_rate
            assert blended_lower <= result.federal_tax_owed <= blended_upper

    @pytest.mark.asyncio
    async def test_reit_distribution_uses_taxable_fraction(self):
        req = _make_calc_req(asset_class=AssetClass.REIT, state_code="FL")
        result = await calculate_tax_burden(req)
        # REIT: ~30% of ordinary rate → much less than full ordinary
        full_ordinary = 1_000 * _ordinary_rate(100_000, FilingStatus.SINGLE)
        assert result.federal_tax_owed < full_ordinary

    @pytest.mark.asyncio
    async def test_net_distribution_plus_tax_equals_gross(self):
        req = _make_calc_req(state_code="TX", asset_class=AssetClass.BOND_ETF)
        result = await calculate_tax_burden(req)
        assert abs(result.net_distribution + result.total_tax_owed - result.gross_distribution) < 0.01

    @pytest.mark.asyncio
    async def test_married_joint_lower_rate_than_single_same_income(self):
        req_s = _make_calc_req(filing_status=FilingStatus.SINGLE,
                               asset_class=AssetClass.BOND_ETF, state_code="TX")
        req_mj = _make_calc_req(filing_status=FilingStatus.MARRIED_JOINT,
                                asset_class=AssetClass.BOND_ETF, state_code="TX")
        s  = await calculate_tax_burden(req_s)
        mj = await calculate_tax_burden(req_mj)
        assert mj.federal_tax_owed <= s.federal_tax_owed

    @pytest.mark.asyncio
    async def test_bracket_detail_populated(self):
        req = _make_calc_req(state_code="TX")
        result = await calculate_tax_burden(req)
        assert len(result.bracket_detail) > 0

    @pytest.mark.asyncio
    async def test_niit_not_applied_ordinary_100k(self):
        req = _make_calc_req(annual_income=100_000, state_code="TX")
        result = await calculate_tax_burden(req)
        assert result.niit_owed == 0.0

    @pytest.mark.asyncio
    async def test_after_tax_yield_uplift_non_negative_qualified(self):
        # Qualified dividend should show positive uplift vs ordinary baseline
        req = _make_calc_req(asset_class=AssetClass.DIVIDEND_STOCK, state_code="TX",
                             annual_income=200_000)
        result = await calculate_tax_burden(req)
        assert result.after_tax_yield_uplift >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Profiler — all asset classes and field coverage
# ─────────────────────────────────────────────────────────────────────────────

class TestProfilerAllClasses:
    ALL_CLASSES_WITH_FIELDS = [
        (AssetClass.BOND_ETF,          TaxTreatment.ORDINARY_INCOME,  False, False, False, False),
        (AssetClass.PREFERRED_STOCK,   TaxTreatment.QUALIFIED_DIVIDEND, True, False, False, False),
        (AssetClass.MLP,               TaxTreatment.MLP_DISTRIBUTION,  False, True,  False, True),
        (AssetClass.BDC,               TaxTreatment.ORDINARY_INCOME,   False, False, False, False),
        (AssetClass.CLOSED_END_FUND,   TaxTreatment.ORDINARY_INCOME,   False, False, False, False),
        (AssetClass.ORDINARY_INCOME,   TaxTreatment.ORDINARY_INCOME,   False, False, False, False),
        (AssetClass.UNKNOWN,           TaxTreatment.ORDINARY_INCOME,   False, False, False, False),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ac,treatment,qualified,s199a,s1256,k1",
                             ALL_CLASSES_WITH_FIELDS)
    async def test_class_profile_fields(self, ac, treatment, qualified, s199a, s1256, k1):
        req = TaxProfileRequest(symbol="TEST", asset_class=ac)
        result = await build_tax_profile(req)
        assert result.primary_tax_treatment == treatment
        assert result.qualified_dividend_eligible is qualified
        assert result.section_199a_eligible is s199a
        assert result.section_1256_eligible is s1256
        assert result.k1_required is k1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ac", [e for e in AssetClass if e != AssetClass.UNKNOWN])
    async def test_all_classes_return_notes(self, ac):
        req = TaxProfileRequest(symbol="TEST", asset_class=ac)
        result = await build_tax_profile(req)
        assert isinstance(result.notes, list)
        assert len(result.notes) > 0

    @pytest.mark.asyncio
    async def test_mlp_k1_and_s199a(self):
        req = TaxProfileRequest(symbol="EPD", asset_class=AssetClass.MLP)
        result = await build_tax_profile(req)
        assert result.k1_required is True
        assert result.section_199a_eligible is True

    @pytest.mark.asyncio
    async def test_reit_s199a_no_k1(self):
        req = TaxProfileRequest(symbol="O", asset_class=AssetClass.REIT)
        result = await build_tax_profile(req)
        assert result.section_199a_eligible is True
        assert result.k1_required is False

    @pytest.mark.asyncio
    async def test_covered_call_etf_s1256(self):
        req = TaxProfileRequest(symbol="JEPI", asset_class=AssetClass.COVERED_CALL_ETF)
        result = await build_tax_profile(req)
        assert result.section_1256_eligible is True

    @pytest.mark.asyncio
    async def test_secondary_treatments_list(self):
        req = TaxProfileRequest(symbol="O", asset_class=AssetClass.REIT)
        result = await build_tax_profile(req)
        assert isinstance(result.secondary_treatments, list)

    def test_profile_map_covers_all_asset_classes_except_unknown(self):
        for ac in AssetClass:
            if ac != AssetClass.UNKNOWN:
                assert ac in _PROFILE_MAP, f"Missing _PROFILE_MAP entry for {ac}"

    def test_every_profile_has_required_keys(self):
        for ac, profile in _PROFILE_MAP.items():
            for key in ("primary", "secondary", "qualified", "s199a", "s1256", "k1", "notes"):
                assert key in profile, f"Missing key '{key}' in _PROFILE_MAP[{ac}]"


# ─────────────────────────────────────────────────────────────────────────────
# Optimizer — extended placement heuristics
# ─────────────────────────────────────────────────────────────────────────────

class TestOptimizerHeuristics:
    def _holding(self, symbol, ac, account=AccountType.TAXABLE, value=50_000, yield_=0.06):
        return HoldingInput(symbol=symbol, asset_class=ac,
                            account_type=account, current_value=value, annual_yield=yield_)

    @pytest.mark.asyncio
    async def test_bond_etf_recommended_for_sheltering(self):
        req = OptimizationRequest(
            holdings=[self._holding("BND", AssetClass.BOND_ETF)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE, state_code="FL",
        )
        result = await optimize_portfolio(req)
        recs = [r for r in result.placement_recommendations if r.symbol == "BND"]
        if recs:
            assert recs[0].recommended_account in (AccountType.ROTH_IRA, AccountType.TRAD_IRA)

    @pytest.mark.asyncio
    async def test_covered_call_etf_sheltered(self):
        req = OptimizationRequest(
            holdings=[self._holding("JEPI", AssetClass.COVERED_CALL_ETF)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE, state_code="FL",
        )
        result = await optimize_portfolio(req)
        recs = [r for r in result.placement_recommendations if r.symbol == "JEPI"]
        if recs:
            assert recs[0].recommended_account in (AccountType.ROTH_IRA, AccountType.TRAD_IRA)

    @pytest.mark.asyncio
    async def test_preferred_stock_stays_taxable(self):
        req = OptimizationRequest(
            holdings=[self._holding("PSA-A", AssetClass.PREFERRED_STOCK)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        # Preferred stock is taxable-friendly — no recommendation to move
        for rec in result.placement_recommendations:
            if rec.symbol == "PSA-A":
                assert rec.recommended_account == AccountType.TAXABLE

    @pytest.mark.asyncio
    async def test_dividend_stock_stays_taxable(self):
        req = OptimizationRequest(
            holdings=[self._holding("JNJ", AssetClass.DIVIDEND_STOCK)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        for rec in result.placement_recommendations:
            if rec.symbol == "JNJ":
                assert rec.recommended_account == AccountType.TAXABLE

    @pytest.mark.asyncio
    async def test_response_has_total_portfolio_value(self):
        req = OptimizationRequest(
            holdings=[self._holding("O", AssetClass.REIT, value=40_000)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        assert result.total_portfolio_value == pytest.approx(40_000)

    @pytest.mark.asyncio
    async def test_savings_non_negative_multiple_holdings(self):
        req = OptimizationRequest(
            holdings=[
                self._holding("O",    AssetClass.REIT,           value=20_000),
                self._holding("JNJ",  AssetClass.DIVIDEND_STOCK, value=20_000),
                self._holding("JEPI", AssetClass.COVERED_CALL_ETF, value=20_000),
            ],
            annual_income=100_000, filing_status=FilingStatus.SINGLE, state_code="FL",
        )
        result = await optimize_portfolio(req)
        assert result.estimated_annual_savings >= 0.0

    @pytest.mark.asyncio
    async def test_summary_string_populated(self):
        req = OptimizationRequest(
            holdings=[self._holding("BND", AssetClass.BOND_ETF)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.asyncio
    async def test_notes_list_in_response(self):
        req = OptimizationRequest(
            holdings=[self._holding("BND", AssetClass.BOND_ETF)],
            annual_income=100_000, filing_status=FilingStatus.SINGLE,
        )
        result = await optimize_portfolio(req)
        assert isinstance(result.notes, list)

    def test_best_shelter_high_income_recommends_roth(self):
        # $50k * 8% yield = $4k annual income → above $2k threshold → ROTH
        result = _best_shelter_account(50_000, 0.08)
        assert result == AccountType.ROTH_IRA

    def test_best_shelter_low_income_recommends_trad(self):
        # $10k * 5% = $500 → below $2k → TRAD_IRA
        result = _best_shelter_account(10_000, 0.05)
        assert result == AccountType.TRAD_IRA

    def test_shelter_priority_set_contains_expected_classes(self):
        for ac in [AssetClass.BOND_ETF, AssetClass.REIT, AssetClass.BDC,
                   AssetClass.COVERED_CALL_ETF, AssetClass.CLOSED_END_FUND]:
            assert ac in _SHELTER_PRIORITY

    def test_never_shelter_contains_mlp(self):
        assert AssetClass.MLP in _NEVER_SHELTER

    def test_taxable_friendly_contains_dividend_stock(self):
        assert AssetClass.DIVIDEND_STOCK in _TAXABLE_FRIENDLY
        assert AssetClass.PREFERRED_STOCK in _TAXABLE_FRIENDLY


# ─────────────────────────────────────────────────────────────────────────────
# Harvester — boundary and edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestHarvesterBoundaries:
    @pytest.mark.asyncio
    async def test_loss_exactly_at_minimum_threshold_is_monitored(self):
        req = _make_harvest_req([
            _candidate(current=10_000 - _MIN_HARVEST_LOSS + 1,
                       basis=10_000, days=400)
        ])
        result = await identify_harvesting_opportunities(req)
        # Loss = $99.99 < $100 → MONITOR
        ops = [o for o in result.opportunities if o.symbol == "JEPI"]
        assert ops[0].action == "MONITOR"

    @pytest.mark.asyncio
    async def test_loss_just_above_threshold_is_harvested(self):
        req = _make_harvest_req([
            _candidate(current=9_899, basis=10_000, days=400)
        ])
        result = await identify_harvesting_opportunities(req)
        ops = result.opportunities
        assert ops[0].action == "HARVEST_NOW"

    @pytest.mark.asyncio
    async def test_wash_sale_check_false_skips_flag(self):
        req = _make_harvest_req(
            [_candidate(current=9_000, basis=10_000, days=10)],
            wash_sale_check=False,
        )
        result = await identify_harvesting_opportunities(req)
        assert len(result.wash_sale_warnings) == 0

    @pytest.mark.asyncio
    async def test_wash_sale_window_boundary_exactly_30_days(self):
        # 30 days exactly is NOT within wash sale window (< 30 required)
        cand = _candidate(days=_WASH_SALE_WINDOW)
        assert _wash_sale_risk(cand) is False

    @pytest.mark.asyncio
    async def test_wash_sale_window_29_days_triggers(self):
        cand = _candidate(days=_WASH_SALE_WINDOW - 1)
        assert _wash_sale_risk(cand) is True

    @pytest.mark.asyncio
    async def test_long_term_loss_flagged_correctly(self):
        req = _make_harvest_req([_candidate(days=400)])
        result = await identify_harvesting_opportunities(req)
        ops = [o for o in result.opportunities if o.symbol == "JEPI"]
        assert ops[0].long_term is True

    @pytest.mark.asyncio
    async def test_short_term_loss_flagged_correctly(self):
        req = _make_harvest_req([_candidate(days=200)])
        result = await identify_harvesting_opportunities(req)
        ops = [o for o in result.opportunities if o.symbol == "JEPI"]
        assert ops[0].long_term is False

    @pytest.mark.asyncio
    async def test_multiple_losses_sum_correctly(self):
        req = _make_harvest_req([
            _candidate("JEPI", current=9_000, basis=10_000, days=400),
            _candidate("BND",  current=8_000, basis=10_000, days=400),
        ])
        result = await identify_harvesting_opportunities(req)
        assert result.total_harvestable_losses == pytest.approx(3_000.0)

    @pytest.mark.asyncio
    async def test_gain_position_excluded_from_total(self):
        req = _make_harvest_req([
            _candidate("AAPL", current=12_000, basis=10_000, days=400),  # gain
            _candidate("BND",  current=9_000,  basis=10_000, days=400),  # loss
        ])
        result = await identify_harvesting_opportunities(req)
        assert result.total_harvestable_losses == pytest.approx(1_000.0)

    @pytest.mark.asyncio
    async def test_response_notes_non_empty(self):
        req = _make_harvest_req([_candidate()])
        result = await identify_harvesting_opportunities(req)
        assert len(result.notes) > 0

    def test_tax_value_short_term_higher_than_long_term(self):
        income = 100_000
        filing = FilingStatus.SINGLE
        state  = 0.0
        st_value = _tax_value_of_loss(1_000, 200, income, filing, state)
        lt_value = _tax_value_of_loss(1_000, 400, income, filing, state)
        assert st_value >= lt_value

    def test_tax_value_with_state_rate_higher(self):
        income = 100_000
        filing = FilingStatus.SINGLE
        no_state = _tax_value_of_loss(1_000, 400, income, filing, 0.0)
        ca_state  = _tax_value_of_loss(1_000, 400, income, filing, 0.133)
        assert ca_state > no_state


# ─────────────────────────────────────────────────────────────────────────────
# API — authentication and additional routes
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIAuthAndRoutes:
    @pytest.mark.asyncio
    async def test_no_auth_profile_returns_403(self, unauth_client):
        resp = await unauth_client.get("/tax/profile/JEPI", params={"asset_class": "COVERED_CALL_ETF"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_no_auth_calculate_returns_403(self, unauth_client):
        resp = await unauth_client.post("/tax/calculate", json={
            "symbol": "BND", "annual_income": 75000, "filing_status": "SINGLE",
            "account_type": "TAXABLE", "distribution_amount": 500, "asset_class": "BOND_ETF",
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_no_auth_optimize_returns_403(self, unauth_client):
        resp = await unauth_client.post("/tax/optimize", json={
            "holdings": [{"symbol": "O", "asset_class": "REIT", "account_type": "TAXABLE",
                          "current_value": 10000, "annual_yield": 0.06}],
            "annual_income": 100000, "filing_status": "SINGLE",
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_no_auth_harvest_returns_403(self, unauth_client):
        resp = await unauth_client.post("/tax/harvest", json={
            "candidates": [{"symbol": "JEPI", "current_value": 9000, "cost_basis": 10000,
                            "holding_period_days": 400, "account_type": "TAXABLE"}],
            "annual_income": 100000, "filing_status": "SINGLE",
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, unauth_client):
        expired = _jwt.encode({"sub": "t", "exp": int(time.time()) - 10}, "test-secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {expired}"}
        resp = await unauth_client.get("/tax/profile/JEPI",
                                       headers=headers,
                                       params={"asset_class": "COVERED_CALL_ETF"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_health_returns_agent_id_5(self, client):
        resp = await client.get("/health")
        assert resp.json()["agent_id"] == 5

    @pytest.mark.asyncio
    async def test_health_service_name(self, client):
        resp = await client.get("/health")
        assert "tax" in resp.json()["service"].lower()

    @pytest.mark.asyncio
    async def test_asset_classes_endpoint_has_mlp(self, client):
        resp = await client.get("/tax/asset-classes")
        assert "MLP" in resp.json()

    @pytest.mark.asyncio
    async def test_asset_classes_endpoint_has_bdc(self, client):
        resp = await client.get("/tax/asset-classes")
        assert "BDC" in resp.json()

    @pytest.mark.asyncio
    async def test_profile_all_classes_via_api(self, client):
        for ac in ["COVERED_CALL_ETF", "DIVIDEND_STOCK", "REIT", "BOND_ETF",
                   "PREFERRED_STOCK", "MLP", "BDC"]:
            resp = await client.get("/tax/profile/TEST", params={"asset_class": ac})
            assert resp.status_code == 200, f"Failed for {ac}"

    @pytest.mark.asyncio
    async def test_calculate_returns_net_distribution(self, client):
        payload = {
            "symbol": "BND", "annual_income": 75_000,
            "filing_status": "SINGLE", "state_code": "TX",
            "account_type": "TAXABLE", "distribution_amount": 1_000,
            "asset_class": "BOND_ETF",
        }
        resp = await client.post("/tax/calculate", json=payload)
        assert "net_distribution" in resp.json()

    @pytest.mark.asyncio
    async def test_calculate_roth_ira_zero_tax(self, client):
        payload = {
            "symbol": "JEPI", "annual_income": 100_000,
            "filing_status": "SINGLE", "state_code": "FL",
            "account_type": "ROTH_IRA", "distribution_amount": 1_000,
            "asset_class": "COVERED_CALL_ETF",
        }
        resp = await client.post("/tax/calculate", json=payload)
        assert resp.json()["total_tax_owed"] == 0.0

    @pytest.mark.asyncio
    async def test_harvest_action_in_response(self, client):
        payload = {
            "candidates": [{
                "symbol": "JEPI", "current_value": 8_000,
                "cost_basis": 10_000, "holding_period_days": 500,
                "account_type": "TAXABLE",
            }],
            "annual_income": 90_000, "filing_status": "SINGLE",
            "state_code": "TX", "wash_sale_check": False,
        }
        resp = await client.post("/tax/harvest", json=payload)
        ops = resp.json()["opportunities"]
        assert ops[0]["action"] == "HARVEST_NOW"
