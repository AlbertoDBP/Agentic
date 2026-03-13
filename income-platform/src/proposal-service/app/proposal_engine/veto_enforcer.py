"""VETO flag detection from Agent 03 response."""
from typing import Optional


def detect_veto_flags(agent03_response: Optional[dict]) -> Optional[dict]:
    """Inspect Agent 03 score response and return veto_flags dict or None.

    VETO is triggered when:
      - nav_erosion_penalty > 15, OR
      - grade == "F"

    Returns a dict with flag reasons if veto applies, None otherwise.
    """
    if agent03_response is None:
        return None

    flags = {}

    # Check nav_erosion_penalty
    nav_erosion = agent03_response.get("nav_erosion_penalty")
    if nav_erosion is not None:
        try:
            if float(nav_erosion) > 15:
                flags["nav_erosion_penalty"] = float(nav_erosion)
        except (TypeError, ValueError):
            pass

    # Check income grade == "F"
    grade = agent03_response.get("grade") or agent03_response.get("income_grade")
    if grade and str(grade).upper() == "F":
        flags["grade"] = str(grade)

    # Also check nested factor_details for nav_erosion
    factor_details = agent03_response.get("factor_details") or {}
    if isinstance(factor_details, dict):
        nav_factor = factor_details.get("nav_erosion_penalty")
        if nav_factor is not None and "nav_erosion_penalty" not in flags:
            try:
                if float(nav_factor) > 15:
                    flags["nav_erosion_penalty"] = float(nav_factor)
            except (TypeError, ValueError):
                pass

    return flags if flags else None
