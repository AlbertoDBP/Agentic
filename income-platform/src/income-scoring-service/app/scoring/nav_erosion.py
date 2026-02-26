"""
Agent 03 — Income Scoring Service
NAV Erosion Analyzer: Monte Carlo simulation for covered call ETFs.

Only applied to COVERED_CALL_ETF asset class. The covered call strategy
caps upside and generates premium income, but introduces NAV drag over time
due to opportunity cost and option-pricing dynamics.

Simulation:
    Annual NAV change ~ N(mu=-0.03, sigma=volatility/100)
    mu = -0.03 is the assumed covered-call strategy drag per year.

Risk classification → score penalty:
    prob(<-5%)  < 0.30  → LOW      (penalty  0)
    prob(<-5%)  < 0.50  → MODERATE (penalty 10)
    prob(<-5%)  < 0.70  → HIGH     (penalty 20)
    prob(<-5%) >= 0.70  → SEVERE   (penalty 30)
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_COVERED_CALL_MU = -0.03   # annual covered-call NAV drag assumption


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class NAVErosionResult:
    prob_erosion_gt_5pct: float
    median_annual_nav_change_pct: float
    risk_classification: str   # LOW | MODERATE | HIGH | SEVERE | UNKNOWN
    penalty: int               # 0 | 10 | 20 | 30
    n_simulations: int


# ── Analyzer ──────────────────────────────────────────────────────────────────

class NAVErosionAnalyzer:
    """Monte Carlo NAV erosion analysis for covered call ETFs.

    Simulates ``n_simulations`` annual NAV-change paths and computes:
      - prob_erosion_gt_5pct : fraction of paths where annual change < -5%
      - median_annual_nav_change_pct : median of simulated paths × 100

    The result is used to apply a score penalty (0–30) to the final score.
    """

    def analyze(
        self,
        ticker: str,
        price_history_stats: dict,
        n_simulations: int = None,
    ) -> NAVErosionResult:
        """Run Monte Carlo NAV erosion simulation.

        Args:
            ticker:              Ticker symbol (for log messages).
            price_history_stats: Dict from /history/stats containing 'volatility'
                                 (price standard-deviation in price units).
            n_simulations:       Number of Monte Carlo paths.
                                 Defaults to settings.nav_erosion_simulations.

        Returns:
            NAVErosionResult.  If volatility is None or 0 returns penalty=0,
            risk=UNKNOWN without running the simulation.
        """
        if n_simulations is None:
            n_simulations = settings.nav_erosion_simulations

        volatility: Optional[float] = None
        if price_history_stats:
            raw = price_history_stats.get("volatility")
            if raw is not None:
                try:
                    volatility = float(raw)
                except (TypeError, ValueError):
                    pass

        if not volatility:
            logger.info(
                "No volatility data for %s — skipping NAV erosion (penalty=0)", ticker
            )
            return NAVErosionResult(
                prob_erosion_gt_5pct=0.0,
                median_annual_nav_change_pct=0.0,
                risk_classification="UNKNOWN",
                penalty=0,
                n_simulations=n_simulations,
            )

        mu    = _COVERED_CALL_MU
        sigma = volatility / 100.0  # convert price-unit std-dev to decimal

        simulated = np.random.normal(mu, sigma, n_simulations)

        prob_erosion_gt_5pct       = float(np.mean(simulated < -0.05))
        median_annual_nav_change   = float(np.median(simulated) * 100)

        risk, penalty = self._classify(prob_erosion_gt_5pct)

        logger.info(
            "NAV erosion %s: σ=%.4f prob_erosion=%.3f risk=%s penalty=%d",
            ticker, sigma, prob_erosion_gt_5pct, risk, penalty,
        )

        return NAVErosionResult(
            prob_erosion_gt_5pct=prob_erosion_gt_5pct,
            median_annual_nav_change_pct=median_annual_nav_change,
            risk_classification=risk,
            penalty=penalty,
            n_simulations=n_simulations,
        )

    @staticmethod
    def _classify(prob: float) -> tuple[str, int]:
        """Map erosion probability to (risk_classification, penalty)."""
        if prob < 0.30:
            return "LOW", 0
        elif prob < 0.50:
            return "MODERATE", 10
        elif prob < 0.70:
            return "HIGH", 20
        else:
            return "SEVERE", 30
