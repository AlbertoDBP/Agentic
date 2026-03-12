"""
Agent 06 — Scenario Simulation Service
Stress Engine: applies scenario shocks to portfolio positions.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.simulation.scenario_library import SCENARIO_LIBRARY

# Fallback shocks: DIVIDEND_STOCK values from each scenario
DEFAULT_SHOCKS: dict = {
    scenario_name: entry["shocks"]["DIVIDEND_STOCK"]
    for scenario_name, entry in SCENARIO_LIBRARY.items()
}

# For a generic default when scenario is unknown
_GENERIC_DEFAULT = {"price_pct": -5, "income_pct": -2}


@dataclass
class PositionImpact:
    symbol: str
    asset_class: str
    current_value: float
    stressed_value: float
    current_income: float
    stressed_income: float
    value_change_pct: float
    income_change_pct: float
    vulnerability_rank: int = 0


@dataclass
class StressResult:
    portfolio_id: str
    scenario_name: str
    portfolio_value_before: float
    portfolio_value_after: float
    value_change_pct: float
    annual_income_before: float
    annual_income_after: float
    income_change_pct: float
    position_impacts: list = field(default_factory=list)
    computed_at: Optional[datetime] = None


class StressEngine:
    def run(
        self,
        positions: list,
        asset_classes: dict,
        scenario_shocks: dict,
        portfolio_id: str,
        scenario_name: str,
    ) -> StressResult:
        """Apply scenario shocks to positions and return a StressResult."""
        impacts: list[PositionImpact] = []

        for pos in positions:
            symbol = pos.get("symbol", "")
            current_value = float(pos.get("current_value") or 0)
            annual_income = float(pos.get("annual_income") or 0)

            ac = asset_classes.get(symbol, "DIVIDEND_STOCK")
            shock = scenario_shocks.get(ac, _GENERIC_DEFAULT)

            stressed_value = current_value * (1 + shock["price_pct"] / 100)
            stressed_income = annual_income * (1 + shock["income_pct"] / 100)

            value_change_pct = (
                (stressed_value - current_value) / current_value * 100
                if current_value else 0.0
            )
            income_change_pct = (
                (stressed_income - annual_income) / annual_income * 100
                if annual_income else 0.0
            )

            impacts.append(PositionImpact(
                symbol=symbol,
                asset_class=ac,
                current_value=current_value,
                stressed_value=stressed_value,
                current_income=annual_income,
                stressed_income=stressed_income,
                value_change_pct=value_change_pct,
                income_change_pct=income_change_pct,
            ))

        # Assign vulnerability ranks by absolute value_change_pct descending
        sorted_impacts = sorted(impacts, key=lambda x: abs(x.value_change_pct), reverse=True)
        for rank, impact in enumerate(sorted_impacts, start=1):
            impact.vulnerability_rank = rank

        # Portfolio totals
        total_value_before = sum(i.current_value for i in impacts)
        total_value_after = sum(i.stressed_value for i in impacts)
        total_income_before = sum(i.current_income for i in impacts)
        total_income_after = sum(i.stressed_income for i in impacts)

        portfolio_value_change_pct = (
            (total_value_after - total_value_before) / total_value_before * 100
            if total_value_before else 0.0
        )
        portfolio_income_change_pct = (
            (total_income_after - total_income_before) / total_income_before * 100
            if total_income_before else 0.0
        )

        return StressResult(
            portfolio_id=portfolio_id,
            scenario_name=scenario_name,
            portfolio_value_before=total_value_before,
            portfolio_value_after=total_value_after,
            value_change_pct=portfolio_value_change_pct,
            annual_income_before=total_income_before,
            annual_income_after=total_income_after,
            income_change_pct=portfolio_income_change_pct,
            position_impacts=sorted_impacts,
            computed_at=datetime.now(timezone.utc),
        )
