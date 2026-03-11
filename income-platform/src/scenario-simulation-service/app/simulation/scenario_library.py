"""
Agent 06 — Scenario Simulation Service
Scenario Library: predefined stress scenarios and custom scenario builder.
"""
from typing import Dict

# ── Predefined scenario shock tables ──────────────────────────────────────────
# Each entry: {asset_class: {price_pct: float, income_pct: float}}

SCENARIO_LIBRARY: Dict[str, Dict] = {
    "RATE_HIKE_200BPS": {
        "description": "Federal Reserve hikes rates by 200 basis points",
        "shocks": {
            "EQUITY_REIT":      {"price_pct": -15, "income_pct": -5},
            "MORTGAGE_REIT":    {"price_pct": -20, "income_pct": -12},
            "BDC":              {"price_pct": -10, "income_pct": -8},
            "COVERED_CALL_ETF": {"price_pct": -8,  "income_pct": -3},
            "DIVIDEND_STOCK":   {"price_pct": -5,  "income_pct": -2},
            "BOND":             {"price_pct": -12, "income_pct": 0},
            "PREFERRED_STOCK":  {"price_pct": -8,  "income_pct": 0},
        },
    },
    "MARKET_CORRECTION_20": {
        "description": "Broad equity market correction of 20%",
        "shocks": {
            "EQUITY_REIT":      {"price_pct": -22, "income_pct": -8},
            "MORTGAGE_REIT":    {"price_pct": -28, "income_pct": -15},
            "BDC":              {"price_pct": -18, "income_pct": -10},
            "COVERED_CALL_ETF": {"price_pct": -15, "income_pct": -5},
            "DIVIDEND_STOCK":   {"price_pct": -20, "income_pct": -5},
            "BOND":             {"price_pct": -5,  "income_pct": 0},
            "PREFERRED_STOCK":  {"price_pct": -12, "income_pct": 0},
        },
    },
    "RECESSION_MILD": {
        "description": "Mild recession with moderate economic contraction",
        "shocks": {
            "EQUITY_REIT":      {"price_pct": -18, "income_pct": -10},
            "MORTGAGE_REIT":    {"price_pct": -25, "income_pct": -20},
            "BDC":              {"price_pct": -20, "income_pct": -15},
            "COVERED_CALL_ETF": {"price_pct": -18, "income_pct": -8},
            "DIVIDEND_STOCK":   {"price_pct": -15, "income_pct": -5},
            "BOND":             {"price_pct": 3,   "income_pct": 0},
            "PREFERRED_STOCK":  {"price_pct": -10, "income_pct": 0},
        },
    },
    "INFLATION_SPIKE": {
        "description": "Persistent inflation spike above 6%",
        "shocks": {
            "EQUITY_REIT":      {"price_pct": -12, "income_pct": 5},
            "MORTGAGE_REIT":    {"price_pct": -18, "income_pct": -8},
            "BDC":              {"price_pct": -5,  "income_pct": 3},
            "COVERED_CALL_ETF": {"price_pct": -8,  "income_pct": -2},
            "DIVIDEND_STOCK":   {"price_pct": -5,  "income_pct": 2},
            "BOND":             {"price_pct": -15, "income_pct": 0},
            "PREFERRED_STOCK":  {"price_pct": -10, "income_pct": 0},
        },
    },
    "CREDIT_STRESS": {
        "description": "Credit market stress with widening spreads and defaults",
        "shocks": {
            "EQUITY_REIT":      {"price_pct": -10, "income_pct": -5},
            "MORTGAGE_REIT":    {"price_pct": -30, "income_pct": -20},
            "BDC":              {"price_pct": -25, "income_pct": -18},
            "COVERED_CALL_ETF": {"price_pct": -8,  "income_pct": -3},
            "DIVIDEND_STOCK":   {"price_pct": -8,  "income_pct": -3},
            "BOND":             {"price_pct": -18, "income_pct": 0},
            "PREFERRED_STOCK":  {"price_pct": -15, "income_pct": 0},
        },
    },
}

ASSET_CLASSES = [
    "EQUITY_REIT", "MORTGAGE_REIT", "BDC", "COVERED_CALL_ETF",
    "DIVIDEND_STOCK", "BOND", "PREFERRED_STOCK",
]


def get_scenario(name: str) -> dict:
    """Return shock table for a predefined scenario. Raises ValueError if not found."""
    if name not in SCENARIO_LIBRARY:
        raise ValueError(
            f"Unknown scenario '{name}'. Available: {list(SCENARIO_LIBRARY.keys())}"
        )
    return SCENARIO_LIBRARY[name]["shocks"]


def list_scenarios() -> list:
    """Return all predefined scenarios with name, description, and shock table."""
    return [
        {
            "name": name,
            "description": entry["description"],
            "shocks": entry["shocks"],
        }
        for name, entry in SCENARIO_LIBRARY.items()
    ]


def build_custom_scenario(shocks: dict) -> dict:
    """Validate and return a custom shock table.

    shocks must contain at least one recognized asset class key.
    Each entry must have price_pct and income_pct numeric values.
    """
    if not shocks:
        raise ValueError("Custom scenario shocks cannot be empty")

    validated: dict = {}
    for ac, shock in shocks.items():
        if not isinstance(shock, dict):
            raise ValueError(f"Shock for '{ac}' must be a dict with price_pct and income_pct")
        if "price_pct" not in shock or "income_pct" not in shock:
            raise ValueError(f"Shock for '{ac}' must contain 'price_pct' and 'income_pct'")
        validated[ac] = {
            "price_pct": float(shock["price_pct"]),
            "income_pct": float(shock["income_pct"]),
        }

    return validated
