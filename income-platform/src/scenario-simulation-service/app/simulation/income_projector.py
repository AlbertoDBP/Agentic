"""
Agent 06 — Scenario Simulation Service
Income Projector: Monte Carlo projection of portfolio income.
"""
from dataclasses import dataclass, field
from datetime import datetime
from math import sqrt
from typing import Optional

import numpy as np


@dataclass
class IncomeProjection:
    portfolio_id: str
    horizon_months: int
    projected_income_p10: float
    projected_income_p50: float
    projected_income_p90: float
    by_position: list = field(default_factory=list)
    computed_at: Optional[datetime] = None


class IncomeProjector:
    N_SIMULATIONS = 1000
    DEFAULT_YIELD_VOLATILITY = 0.05  # 5% annual yield std dev

    def project(
        self,
        positions: list,
        horizon_months: int = 12,
    ) -> IncomeProjection:
        """Run Monte Carlo simulation to project income over horizon_months."""
        portfolio_id = positions[0].get("portfolio_id", "") if positions else ""

        time_fraction = horizon_months / 12
        yield_vol = self.DEFAULT_YIELD_VOLATILITY * sqrt(time_fraction)

        by_position = []
        # Accumulate per-simulation totals across positions
        portfolio_sims = np.zeros(self.N_SIMULATIONS)

        for pos in positions:
            symbol = pos.get("symbol", "")
            annual_income = float(pos.get("annual_income") or 0)
            base_income = annual_income * time_fraction

            if base_income == 0:
                by_position.append({
                    "symbol": symbol,
                    "base_income": 0.0,
                    "p10": 0.0,
                    "p50": 0.0,
                    "p90": 0.0,
                })
                continue

            # Log-normal GBM: S * exp(N(0, vol) - vol²/2)
            draws = np.random.normal(0, yield_vol, self.N_SIMULATIONS)
            sims = base_income * np.exp(draws - yield_vol ** 2 / 2)

            portfolio_sims += sims

            by_position.append({
                "symbol": symbol,
                "base_income": round(base_income, 2),
                "p10": round(float(np.percentile(sims, 10)), 2),
                "p50": round(float(np.percentile(sims, 50)), 2),
                "p90": round(float(np.percentile(sims, 90)), 2),
            })

        if len(portfolio_sims) == 0 or portfolio_sims.sum() == 0:
            p10, p50, p90 = 0.0, 0.0, 0.0
        else:
            p10 = float(np.percentile(portfolio_sims, 10))
            p50 = float(np.percentile(portfolio_sims, 50))
            p90 = float(np.percentile(portfolio_sims, 90))

        return IncomeProjection(
            portfolio_id=portfolio_id,
            horizon_months=horizon_months,
            projected_income_p10=round(p10, 2),
            projected_income_p50=round(p50, 2),
            projected_income_p90=round(p90, 2),
            by_position=by_position,
            computed_at=datetime.utcnow(),
        )
