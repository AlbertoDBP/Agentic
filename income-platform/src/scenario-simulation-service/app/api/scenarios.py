"""
Agent 06 — Scenario Simulation Service
API: Scenario stress test, income projection, and vulnerability endpoints.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import SessionLocal
from app.models import ScenarioResult
from app.simulation.scenario_library import (
    get_scenario,
    list_scenarios,
    build_custom_scenario,
)
from app.simulation.stress_engine import StressEngine
from app.simulation.income_projector import IncomeProjector
from app.simulation import portfolio_reader

router = APIRouter()

# ── Request / Response Models ─────────────────────────────────────────────────


class StressTestRequest(BaseModel):
    portfolio_id: str
    scenario_type: str                          # predefined name or "CUSTOM"
    scenario_params: Optional[dict] = None      # required if CUSTOM
    as_of_date: Optional[date] = None
    save: bool = False
    label: Optional[str] = None


class PositionImpactOut(BaseModel):
    symbol: str
    asset_class: str
    current_value: float
    stressed_value: float
    current_income: float
    stressed_income: float
    value_change_pct: float
    income_change_pct: float
    vulnerability_rank: int


class StressTestResponse(BaseModel):
    portfolio_id: str
    scenario_name: str
    portfolio_value_before: float
    portfolio_value_after: float
    value_change_pct: float
    annual_income_before: float
    annual_income_after: float
    income_change_pct: float
    position_impacts: list[PositionImpactOut]
    computed_at: str
    saved: bool = False
    result_id: Optional[str] = None


class IncomeProjectionRequest(BaseModel):
    portfolio_id: str
    horizon_months: int = Field(default=12, ge=1, le=60)


class IncomeProjectionResponse(BaseModel):
    portfolio_id: str
    horizon_months: int
    projected_income_p10: float
    projected_income_p50: float
    projected_income_p90: float
    by_position: list[dict]
    computed_at: str


class VulnerabilityRequest(BaseModel):
    portfolio_id: str
    scenario_types: list[str] = ["RATE_HIKE_200BPS", "MARKET_CORRECTION_20"]


class VulnerabilityResponse(BaseModel):
    portfolio_id: str
    rankings: list[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _load_positions_and_classes(portfolio_id: str, as_of_date: Optional[date] = None):
    positions = await portfolio_reader.get_positions(portfolio_id, as_of_date)
    if not positions:
        raise HTTPException(
            status_code=422,
            detail=f"No open positions found for portfolio_id={portfolio_id}",
        )
    symbols = [p["symbol"] for p in positions]
    asset_classes = await portfolio_reader.get_asset_classes(symbols)
    return positions, asset_classes


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/scenarios/stress-test", response_model=StressTestResponse)
async def stress_test(req: StressTestRequest):
    positions, asset_classes = await _load_positions_and_classes(
        req.portfolio_id, req.as_of_date
    )

    scenario_name = req.scenario_type
    if req.scenario_type == "CUSTOM":
        if not req.scenario_params:
            raise HTTPException(
                status_code=422,
                detail="scenario_params is required when scenario_type is CUSTOM",
            )
        try:
            shocks = build_custom_scenario(req.scenario_params)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        scenario_name = "CUSTOM"
    else:
        try:
            shocks = get_scenario(req.scenario_type)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    engine = StressEngine()
    result = engine.run(
        positions=positions,
        asset_classes=asset_classes,
        scenario_shocks=shocks,
        portfolio_id=req.portfolio_id,
        scenario_name=scenario_name,
    )

    saved = False
    result_id = None

    if req.save:
        result_summary = {
            "portfolio_value_before": result.portfolio_value_before,
            "portfolio_value_after": result.portfolio_value_after,
            "value_change_pct": result.value_change_pct,
            "annual_income_before": result.annual_income_before,
            "annual_income_after": result.annual_income_after,
            "income_change_pct": result.income_change_pct,
            "position_impacts": [
                {
                    "symbol": p.symbol,
                    "asset_class": p.asset_class,
                    "current_value": p.current_value,
                    "stressed_value": p.stressed_value,
                    "current_income": p.current_income,
                    "stressed_income": p.stressed_income,
                    "value_change_pct": p.value_change_pct,
                    "income_change_pct": p.income_change_pct,
                    "vulnerability_rank": p.vulnerability_rank,
                }
                for p in result.position_impacts
            ],
        }
        vulnerability_ranking = [
            {"symbol": p.symbol, "rank": p.vulnerability_rank, "value_change_pct": p.value_change_pct}
            for p in result.position_impacts
        ]
        record = ScenarioResult(
            portfolio_id=uuid.UUID(req.portfolio_id),
            scenario_name=scenario_name,
            scenario_type="CUSTOM" if req.scenario_type == "CUSTOM" else "PREDEFINED",
            scenario_params=req.scenario_params if req.scenario_type == "CUSTOM" else None,
            result_summary=result_summary,
            vulnerability_ranking=vulnerability_ranking,
            label=req.label,
        )
        db = SessionLocal()
        try:
            db.add(record)
            db.commit()
            db.refresh(record)
        finally:
            db.close()
        saved = True
        result_id = str(record.id)

    return StressTestResponse(
        portfolio_id=result.portfolio_id,
        scenario_name=result.scenario_name,
        portfolio_value_before=result.portfolio_value_before,
        portfolio_value_after=result.portfolio_value_after,
        value_change_pct=result.value_change_pct,
        annual_income_before=result.annual_income_before,
        annual_income_after=result.annual_income_after,
        income_change_pct=result.income_change_pct,
        position_impacts=[
            PositionImpactOut(
                symbol=p.symbol,
                asset_class=p.asset_class,
                current_value=p.current_value,
                stressed_value=p.stressed_value,
                current_income=p.current_income,
                stressed_income=p.stressed_income,
                value_change_pct=p.value_change_pct,
                income_change_pct=p.income_change_pct,
                vulnerability_rank=p.vulnerability_rank,
            )
            for p in result.position_impacts
        ],
        computed_at=result.computed_at.isoformat(),
        saved=saved,
        result_id=result_id,
    )


@router.post("/scenarios/income-projection", response_model=IncomeProjectionResponse)
async def income_projection(req: IncomeProjectionRequest):
    positions = await portfolio_reader.get_positions(req.portfolio_id)
    if not positions:
        raise HTTPException(
            status_code=422,
            detail=f"No open positions found for portfolio_id={req.portfolio_id}",
        )

    # Attach portfolio_id so projector can reference it
    for p in positions:
        p["portfolio_id"] = req.portfolio_id

    projector = IncomeProjector()
    result = projector.project(positions=positions, horizon_months=req.horizon_months)

    return IncomeProjectionResponse(
        portfolio_id=req.portfolio_id,
        horizon_months=result.horizon_months,
        projected_income_p10=result.projected_income_p10,
        projected_income_p50=result.projected_income_p50,
        projected_income_p90=result.projected_income_p90,
        by_position=result.by_position,
        computed_at=result.computed_at.isoformat(),
    )


@router.post("/scenarios/vulnerability", response_model=VulnerabilityResponse)
async def vulnerability(req: VulnerabilityRequest):
    positions, asset_classes = await _load_positions_and_classes(req.portfolio_id)

    engine = StressEngine()
    # {symbol: {scenario: value_change_pct}}
    symbol_worst: dict[str, dict] = {}

    for scenario_name in req.scenario_types:
        try:
            shocks = get_scenario(scenario_name)
        except ValueError:
            continue

        result = engine.run(
            positions=positions,
            asset_classes=asset_classes,
            scenario_shocks=shocks,
            portfolio_id=req.portfolio_id,
            scenario_name=scenario_name,
        )

        for impact in result.position_impacts:
            if impact.symbol not in symbol_worst:
                symbol_worst[impact.symbol] = {
                    "symbol": impact.symbol,
                    "worst_scenario": scenario_name,
                    "max_value_loss_pct": impact.value_change_pct,
                }
            else:
                if impact.value_change_pct < symbol_worst[impact.symbol]["max_value_loss_pct"]:
                    symbol_worst[impact.symbol]["worst_scenario"] = scenario_name
                    symbol_worst[impact.symbol]["max_value_loss_pct"] = impact.value_change_pct

    # Rank by worst loss (most negative first)
    ranked = sorted(symbol_worst.values(), key=lambda x: x["max_value_loss_pct"])
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    return VulnerabilityResponse(
        portfolio_id=req.portfolio_id,
        rankings=ranked,
    )


@router.get("/scenarios/library")
def scenario_library():
    return {"scenarios": list_scenarios()}
