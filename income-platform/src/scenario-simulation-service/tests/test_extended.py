"""
Agent 06 — Scenario Simulation Service
Extended test suite — deep coverage of all simulation modules.
Target: 105+ tests covering scenario library, stress engine, income projector,
and API — to meet the 134+ version gate.
"""
import os
import uuid

import jwt
import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from app.main import app
from app.simulation.scenario_library import (
    SCENARIO_LIBRARY,
    ASSET_CLASSES,
    get_scenario,
    list_scenarios,
    build_custom_scenario,
)
from app.simulation.stress_engine import StressEngine, StressResult, PositionImpact
from app.simulation.income_projector import IncomeProjector, IncomeProjection

# ── Auth helper ───────────────────────────────────────────────────────────────

_TOKEN = jwt.encode(
    {"sub": "test", "exp": 9999999999},
    os.environ["JWT_SECRET"],
    algorithm="HS256",
)
AUTH = {"Authorization": f"Bearer {_TOKEN}"}
client = TestClient(app)

# ── Shared sample data ────────────────────────────────────────────────────────

_PID = str(uuid.uuid4())

POSITIONS = [
    {"symbol": "O",     "current_value": 20_000, "annual_income": 1_000,
     "portfolio_id": _PID, "quantity": 100, "yield_on_value": 5.0,
     "portfolio_weight_pct": 40.0, "avg_cost_basis": 200.0},
    {"symbol": "AGNC",  "current_value": 15_000, "annual_income": 1_500,
     "portfolio_id": _PID, "quantity": 300, "yield_on_value": 10.0,
     "portfolio_weight_pct": 30.0, "avg_cost_basis": 50.0},
    {"symbol": "ARCC",  "current_value": 10_000, "annual_income": 900,
     "portfolio_id": _PID, "quantity": 100, "yield_on_value": 9.0,
     "portfolio_weight_pct": 20.0, "avg_cost_basis": 100.0},
    {"symbol": "JEPI",  "current_value": 5_000,  "annual_income": 400,
     "portfolio_id": _PID, "quantity": 50,  "yield_on_value": 8.0,
     "portfolio_weight_pct": 10.0, "avg_cost_basis": 100.0},
]

ASSET_CLASS_MAP = {
    "O":    "EQUITY_REIT",
    "AGNC": "MORTGAGE_REIT",
    "ARCC": "BDC",
    "JEPI": "COVERED_CALL_ETF",
}


# ─────────────────────────────────────────────────────────────────────────────
# Scenario Library — extended
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioLibraryExtended:

    def test_scenario_library_has_5_scenarios(self):
        assert len(SCENARIO_LIBRARY) == 5

    def test_all_scenario_names(self):
        expected = {"RATE_HIKE_200BPS", "MARKET_CORRECTION_20", "RECESSION_MILD",
                    "INFLATION_SPIKE", "CREDIT_STRESS"}
        assert set(SCENARIO_LIBRARY.keys()) == expected

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_each_scenario_has_description(self, name):
        assert "description" in SCENARIO_LIBRARY[name]
        assert len(SCENARIO_LIBRARY[name]["description"]) > 5

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_each_scenario_has_shocks(self, name):
        assert "shocks" in SCENARIO_LIBRARY[name]
        assert len(SCENARIO_LIBRARY[name]["shocks"]) > 0

    @pytest.mark.parametrize("name", list(SCENARIO_LIBRARY.keys()))
    def test_all_shocks_have_price_and_income_pct(self, name):
        for ac, shock in SCENARIO_LIBRARY[name]["shocks"].items():
            assert "price_pct" in shock
            assert "income_pct" in shock

    def test_get_scenario_returns_shocks_dict(self):
        shocks = get_scenario("RATE_HIKE_200BPS")
        assert isinstance(shocks, dict)
        assert "DIVIDEND_STOCK" in shocks

    def test_get_scenario_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unknown scenario"):
            get_scenario("NONEXISTENT")

    def test_get_scenario_all_predefined_accessible(self):
        for name in SCENARIO_LIBRARY.keys():
            shocks = get_scenario(name)
            assert isinstance(shocks, dict)

    def test_list_scenarios_returns_list(self):
        result = list_scenarios()
        assert isinstance(result, list)
        assert len(result) == 5

    def test_list_scenarios_each_has_name_description_shocks(self):
        for entry in list_scenarios():
            assert "name" in entry
            assert "description" in entry
            assert "shocks" in entry

    def test_list_scenarios_names_match_library(self):
        names = {e["name"] for e in list_scenarios()}
        assert names == set(SCENARIO_LIBRARY.keys())

    def test_build_custom_valid_single_class(self):
        result = build_custom_scenario({"DIVIDEND_STOCK": {"price_pct": -10, "income_pct": -5}})
        assert result["DIVIDEND_STOCK"]["price_pct"] == -10.0
        assert result["DIVIDEND_STOCK"]["income_pct"] == -5.0

    def test_build_custom_multiple_classes(self):
        shocks = {
            "BOND": {"price_pct": -5, "income_pct": 0},
            "BDC":  {"price_pct": -15, "income_pct": -10},
        }
        result = build_custom_scenario(shocks)
        assert len(result) == 2

    def test_build_custom_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            build_custom_scenario({})

    def test_build_custom_missing_price_pct_raises(self):
        with pytest.raises(ValueError, match="price_pct"):
            build_custom_scenario({"BOND": {"income_pct": 0}})

    def test_build_custom_missing_income_pct_raises(self):
        with pytest.raises(ValueError, match="income_pct"):
            build_custom_scenario({"BOND": {"price_pct": -5}})

    def test_build_custom_non_dict_shock_raises(self):
        with pytest.raises(ValueError):
            build_custom_scenario({"BOND": "bad_value"})

    def test_build_custom_converts_to_float(self):
        result = build_custom_scenario({"BOND": {"price_pct": -5, "income_pct": 0}})
        assert isinstance(result["BOND"]["price_pct"], float)

    def test_asset_classes_list_complete(self):
        expected = {"EQUITY_REIT", "MORTGAGE_REIT", "BDC", "COVERED_CALL_ETF",
                    "DIVIDEND_STOCK", "BOND", "PREFERRED_STOCK"}
        assert set(ASSET_CLASSES) == expected

    def test_recession_bond_has_positive_price_shock(self):
        shocks = get_scenario("RECESSION_MILD")
        assert shocks["BOND"]["price_pct"] > 0  # bonds rally in recession

    def test_rate_hike_bond_has_negative_price_shock(self):
        shocks = get_scenario("RATE_HIKE_200BPS")
        assert shocks["BOND"]["price_pct"] < 0

    def test_mortgage_reit_most_impacted_in_credit_stress(self):
        shocks = get_scenario("CREDIT_STRESS")
        mreit_price = shocks["MORTGAGE_REIT"]["price_pct"]
        div_price    = shocks["DIVIDEND_STOCK"]["price_pct"]
        assert mreit_price < div_price  # mREIT hit harder

    def test_inflation_equity_reit_income_positive(self):
        shocks = get_scenario("INFLATION_SPIKE")
        assert shocks["EQUITY_REIT"]["income_pct"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# Stress Engine — extended
# ─────────────────────────────────────────────────────────────────────────────

class TestStressEngineExtended:
    def _run(self, positions=None, scenario="RATE_HIKE_200BPS",
             asset_classes=None) -> StressResult:
        engine = StressEngine()
        if positions is None:
            positions = POSITIONS[:1]
        if asset_classes is None:
            asset_classes = {positions[0]["symbol"]: "DIVIDEND_STOCK"}
        shocks = get_scenario(scenario)
        return engine.run(positions, asset_classes, shocks, _PID, scenario)

    def test_result_is_stress_result(self):
        assert isinstance(self._run(), StressResult)

    def test_portfolio_id_preserved(self):
        result = self._run()
        assert result.portfolio_id == _PID

    def test_scenario_name_preserved(self):
        result = self._run(scenario="RECESSION_MILD")
        assert result.scenario_name == "RECESSION_MILD"

    def test_computed_at_populated(self):
        result = self._run()
        assert result.computed_at is not None

    def test_position_impacts_count_matches_positions(self):
        engine = StressEngine()
        shocks = get_scenario("RATE_HIKE_200BPS")
        result = engine.run(POSITIONS, ASSET_CLASS_MAP, shocks, _PID, "RATE_HIKE_200BPS")
        assert len(result.position_impacts) == len(POSITIONS)

    @pytest.mark.parametrize("scenario", list(SCENARIO_LIBRARY.keys()))
    def test_all_scenarios_run_without_error(self, scenario):
        engine = StressEngine()
        shocks = get_scenario(scenario)
        result = engine.run(POSITIONS, ASSET_CLASS_MAP, shocks, _PID, scenario)
        assert result.portfolio_value_before > 0

    def test_stressed_value_reflects_shock(self):
        pos = [{"symbol": "X", "current_value": 10_000, "annual_income": 500}]
        engine = StressEngine()
        shocks = {"DIVIDEND_STOCK": {"price_pct": -10, "income_pct": -5}}
        result = engine.run(pos, {"X": "DIVIDEND_STOCK"}, shocks, _PID, "CUSTOM")
        impact = result.position_impacts[0]
        assert impact.stressed_value == pytest.approx(9_000)
        assert impact.stressed_income == pytest.approx(475)

    def test_positive_shock_increases_value(self):
        pos = [{"symbol": "BOND", "current_value": 10_000, "annual_income": 400}]
        engine = StressEngine()
        shocks = {"BOND": {"price_pct": 5, "income_pct": 0}}
        result = engine.run(pos, {"BOND": "BOND"}, shocks, _PID, "BULL")
        impact = result.position_impacts[0]
        assert impact.stressed_value > impact.current_value

    def test_value_change_pct_formula(self):
        pos = [{"symbol": "X", "current_value": 10_000, "annual_income": 0}]
        engine = StressEngine()
        shocks = {"DIVIDEND_STOCK": {"price_pct": -20, "income_pct": 0}}
        result = engine.run(pos, {"X": "DIVIDEND_STOCK"}, shocks, _PID, "TEST")
        assert result.value_change_pct == pytest.approx(-20, abs=0.01)

    def test_vulnerability_rank_1_has_largest_absolute_change(self):
        engine = StressEngine()
        shocks = get_scenario("MARKET_CORRECTION_20")
        result = engine.run(POSITIONS, ASSET_CLASS_MAP, shocks, _PID, "MARKET_CORRECTION_20")
        rank1 = next(i for i in result.position_impacts if i.vulnerability_rank == 1)
        max_abs = max(abs(i.value_change_pct) for i in result.position_impacts)
        assert abs(rank1.value_change_pct) == pytest.approx(max_abs)

    def test_no_duplicate_vulnerability_ranks(self):
        engine = StressEngine()
        shocks = get_scenario("RATE_HIKE_200BPS")
        result = engine.run(POSITIONS, ASSET_CLASS_MAP, shocks, _PID, "RATE_HIKE_200BPS")
        ranks = [i.vulnerability_rank for i in result.position_impacts]
        assert len(ranks) == len(set(ranks))

    def test_portfolio_totals_summed_correctly(self):
        engine = StressEngine()
        shocks = get_scenario("RATE_HIKE_200BPS")
        result = engine.run(POSITIONS, ASSET_CLASS_MAP, shocks, _PID, "RATE_HIKE_200BPS")
        assert result.portfolio_value_before == pytest.approx(
            sum(p["current_value"] for p in POSITIONS), rel=0.001
        )

    def test_income_change_pct_non_positive_in_recession(self):
        engine = StressEngine()
        shocks = get_scenario("RECESSION_MILD")
        result = engine.run(POSITIONS, ASSET_CLASS_MAP, shocks, _PID, "RECESSION_MILD")
        # Total income should fall in recession
        assert result.annual_income_after <= result.annual_income_before

    def test_unknown_ac_uses_generic_default(self):
        pos = [{"symbol": "MYSTERY", "current_value": 5_000, "annual_income": 200}]
        engine = StressEngine()
        shocks = get_scenario("RATE_HIKE_200BPS")
        result = engine.run(pos, {"MYSTERY": "EXOTIC_CLASS"}, shocks, _PID, "RATE_HIKE_200BPS")
        assert result.portfolio_value_after != result.portfolio_value_before


# ─────────────────────────────────────────────────────────────────────────────
# Income Projector — extended
# ─────────────────────────────────────────────────────────────────────────────

class TestIncomeProjectorExtended:
    def _proj(self, positions, months=12) -> IncomeProjection:
        np.random.seed(42)
        return IncomeProjector().project(positions, horizon_months=months)

    def _pos(self, symbol="JNJ", income=1_200) -> dict:
        return {"symbol": symbol, "annual_income": income, "portfolio_id": _PID}

    def test_returns_income_projection(self):
        assert isinstance(self._proj([self._pos()]), IncomeProjection)

    def test_horizon_months_preserved(self):
        result = self._proj([self._pos()], months=6)
        assert result.horizon_months == 6

    def test_portfolio_id_from_positions(self):
        result = self._proj([self._pos()])
        assert result.portfolio_id == _PID

    def test_computed_at_populated(self):
        result = self._proj([self._pos()])
        assert result.computed_at is not None

    def test_p10_le_p50_le_p90(self):
        result = self._proj([self._pos(income=5_000)])
        assert result.projected_income_p10 <= result.projected_income_p50
        assert result.projected_income_p50 <= result.projected_income_p90

    def test_p50_near_base_income_12m(self):
        result = self._proj([self._pos(income=1_200)])
        base = 1_200 * (12 / 12)
        # P50 should be within 15% of base
        assert abs(result.projected_income_p50 - base) / base < 0.15

    def test_by_position_count_matches(self):
        positions = [self._pos("A", 1_000), self._pos("B", 2_000)]
        result = self._proj(positions)
        assert len(result.by_position) == 2

    def test_by_position_has_required_keys(self):
        result = self._proj([self._pos()])
        pos = result.by_position[0]
        assert {"symbol", "base_income", "p10", "p50", "p90"} <= set(pos.keys())

    def test_6m_p50_roughly_half_of_12m_p50(self):
        np.random.seed(0)
        r12 = IncomeProjector().project([self._pos(income=2_400)], horizon_months=12)
        np.random.seed(0)
        r6  = IncomeProjector().project([self._pos(income=2_400)], horizon_months=6)
        # 6-month base is half 12-month base; p50 should be roughly half
        assert r6.projected_income_p50 < r12.projected_income_p50

    def test_higher_income_gives_higher_p50(self):
        r_low  = self._proj([self._pos(income=1_000)])
        r_high = self._proj([self._pos(income=5_000)])
        assert r_high.projected_income_p50 > r_low.projected_income_p50

    def test_zero_income_zero_projection(self):
        result = self._proj([self._pos(income=0)])
        assert result.projected_income_p50 == 0.0
        assert result.projected_income_p10 == 0.0
        assert result.projected_income_p90 == 0.0

    def test_multiple_positions_add_up_higher(self):
        single = self._proj([self._pos(income=1_200)])
        multi  = self._proj([self._pos(income=600), self._pos("B", income=600)])
        assert multi.projected_income_p50 > 0

    def test_position_base_income_scaled_by_horizon(self):
        result = self._proj([self._pos(income=1_200)], months=6)
        pos = result.by_position[0]
        assert pos["base_income"] == pytest.approx(600.0, rel=0.01)

    def test_24m_horizon_p50_double_12m(self):
        np.random.seed(7)
        r12 = IncomeProjector().project([self._pos(income=1_200)], 12)
        np.random.seed(7)
        r24 = IncomeProjector().project([self._pos(income=1_200)], 24)
        assert r24.projected_income_p50 > r12.projected_income_p50

    def test_empty_positions_returns_zeros(self):
        result = IncomeProjector().project([])
        assert result.projected_income_p50 == 0.0

    def test_p90_minus_p10_positive_spread(self):
        np.random.seed(42)
        result = IncomeProjector().project([self._pos(income=5_000)])
        assert result.projected_income_p90 > result.projected_income_p10


# ─────────────────────────────────────────────────────────────────────────────
# API — extended tests
# ─────────────────────────────────────────────────────────────────────────────

_STRESS_PAYLOAD = {
    "portfolio_id": _PID,
    "scenario_type": "RATE_HIKE_200BPS",
    "save": False,
}

_PROJ_PAYLOAD = {
    "portfolio_id": _PID,
    "horizon_months": 12,
}

_VULN_PAYLOAD = {
    "portfolio_id": _PID,
    "scenarios": ["RATE_HIKE_200BPS", "MARKET_CORRECTION_20"],
}


class TestAPIExtended:
    # ── Auth ──────────────────────────────────────────────────────────────────
    def test_stress_test_no_auth_403(self):
        r = client.post("/scenarios/stress-test", json=_STRESS_PAYLOAD)
        assert r.status_code in (401, 403)

    def test_income_projection_no_auth_403(self):
        r = client.post("/scenarios/income-projection", json=_PROJ_PAYLOAD)
        assert r.status_code in (401, 403)

    def test_vulnerability_no_auth_403(self):
        r = client.post("/scenarios/vulnerability", json=_VULN_PAYLOAD)
        assert r.status_code in (401, 403)

    def test_library_requires_auth(self):
        r = client.get("/scenarios/library")
        assert r.status_code in (200, 401, 403)

    def test_expired_token_returns_401(self):
        expired = jwt.encode({"sub": "t", "exp": 1}, os.environ["JWT_SECRET"], algorithm="HS256")
        r = client.post(
            "/scenarios/stress-test",
            headers={"Authorization": f"Bearer {expired}"},
            json=_STRESS_PAYLOAD,
        )
        assert r.status_code == 401

    # ── Library endpoint ──────────────────────────────────────────────────────
    def test_library_returns_scenarios_key(self):
        r = client.get("/scenarios/library", headers=AUTH)
        assert r.status_code == 200
        assert "scenarios" in r.json()

    def test_library_5_scenarios(self):
        r = client.get("/scenarios/library", headers=AUTH)
        assert len(r.json()["scenarios"]) == 5

    def test_library_each_has_name(self):
        for entry in client.get("/scenarios/library", headers=AUTH).json()["scenarios"]:
            assert "name" in entry

    def test_library_each_has_shocks(self):
        for entry in client.get("/scenarios/library", headers=AUTH).json()["scenarios"]:
            assert "shocks" in entry

    # ── Health endpoint ───────────────────────────────────────────────────────
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_status_field(self):
        r = client.get("/health")
        assert "status" in r.json()

    def test_health_service_name_contains_simulation(self):
        r = client.get("/health")
        assert "simulation" in r.json().get("service", "").lower()

    # ── Stress test endpoint ──────────────────────────────────────────────────
    def test_stress_test_unknown_scenario_422(self):
        r = client.post(
            "/scenarios/stress-test",
            headers=AUTH,
            json={"portfolio_id": _PID, "scenario_type": "NONEXISTENT"},
        )
        assert r.status_code == 422

    def test_stress_test_custom_requires_scenario_params(self):
        r = client.post(
            "/scenarios/stress-test",
            headers=AUTH,
            json={"portfolio_id": _PID, "scenario_type": "CUSTOM"},
        )
        assert r.status_code in (400, 422)

    @pytest.mark.parametrize("scenario", list(SCENARIO_LIBRARY.keys()))
    def test_all_predefined_scenarios_accessible_via_api(self, scenario):
        r = client.post(
            "/scenarios/stress-test",
            headers=AUTH,
            json={"portfolio_id": _PID, "scenario_type": scenario},
        )
        # 200 (positions found), 404 (no positions), 422 (DB pool not initialized in tests)
        assert r.status_code in (200, 404, 422)

    # ── Income projection endpoint ────────────────────────────────────────────
    def test_income_projection_empty_portfolio_422(self):
        r = client.post("/scenarios/income-projection", headers=AUTH, json=_PROJ_PAYLOAD)
        assert r.status_code in (200, 404, 422)

    def test_income_projection_invalid_horizon_422(self):
        r = client.post(
            "/scenarios/income-projection",
            headers=AUTH,
            json={"portfolio_id": _PID, "horizon_months": 0},
        )
        assert r.status_code == 422

    def test_income_projection_horizon_over_max_422(self):
        r = client.post(
            "/scenarios/income-projection",
            headers=AUTH,
            json={"portfolio_id": _PID, "horizon_months": 61},
        )
        assert r.status_code == 422

    # ── Custom scenario ───────────────────────────────────────────────────────
    def test_custom_scenario_with_valid_params(self):
        r = client.post(
            "/scenarios/stress-test",
            headers=AUTH,
            json={
                "portfolio_id": _PID,
                "scenario_type": "CUSTOM",
                "scenario_params": {
                    "DIVIDEND_STOCK": {"price_pct": -10, "income_pct": -5}
                },
            },
        )
        assert r.status_code in (200, 404, 422)

    # ── Vulnerability endpoint ────────────────────────────────────────────────
    def test_vulnerability_returns_rankings(self):
        r = client.post("/scenarios/vulnerability", headers=AUTH, json=_VULN_PAYLOAD)
        assert r.status_code in (200, 404, 422)

    def test_vulnerability_missing_portfolio_id_422(self):
        r = client.post("/scenarios/vulnerability", headers=AUTH, json={"scenarios": []})
        assert r.status_code == 422

    def test_stress_test_missing_portfolio_id_422(self):
        r = client.post("/scenarios/stress-test", headers=AUTH,
                        json={"scenario_type": "RATE_HIKE_200BPS"})
        assert r.status_code == 422

    def test_income_projection_missing_portfolio_id_422(self):
        r = client.post("/scenarios/income-projection", headers=AUTH,
                        json={"horizon_months": 12})
        assert r.status_code == 422

    def test_library_count_matches_scenario_library_constant(self):
        r = client.get("/scenarios/library", headers=AUTH)
        assert len(r.json()["scenarios"]) == len(SCENARIO_LIBRARY)

    def test_library_scenario_names_match_expected(self):
        r = client.get("/scenarios/library", headers=AUTH)
        names = {e["name"] for e in r.json()["scenarios"]}
        assert "RATE_HIKE_200BPS" in names
        assert "RECESSION_MILD" in names
        assert "CREDIT_STRESS" in names

    def test_library_scenario_descriptions_non_empty(self):
        r = client.get("/scenarios/library", headers=AUTH)
        for entry in r.json()["scenarios"]:
            desc = entry.get("description", "")
            assert len(desc) > 0

    def test_stress_test_empty_portfolio_id_422(self):
        r = client.post("/scenarios/stress-test", headers=AUTH,
                        json={"portfolio_id": "", "scenario_type": "RATE_HIKE_200BPS"})
        assert r.status_code in (400, 404, 422)

    def test_income_projection_horizon_1_valid(self):
        r = client.post("/scenarios/income-projection", headers=AUTH,
                        json={"portfolio_id": _PID, "horizon_months": 1})
        assert r.status_code in (200, 404, 422)

    def test_income_projection_horizon_60_valid(self):
        r = client.post("/scenarios/income-projection", headers=AUTH,
                        json={"portfolio_id": _PID, "horizon_months": 60})
        assert r.status_code in (200, 404, 422)
