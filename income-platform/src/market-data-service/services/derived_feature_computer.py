"""
Agent 01 — Market Data Service
DerivedFeatureComputer: evaluates computation_rule formulas against stored feature data.
"""
import ast
import logging
import operator
from typing import Optional

logger = logging.getLogger(__name__)

# Safe eval context — only basic math operators
_SAFE_OPS = {
    "Add": operator.add,
    "Sub": operator.sub,
    "Mult": operator.mul,
    "Div": operator.truediv,
}


def compute_derived_feature(
    computation_rule: str,
    stored_data: dict,
) -> Optional[float]:
    """
    Safely evaluate a simple arithmetic computation_rule against stored_data.
    Supports: field_a / field_b, field_a - field_b, field_a * field_b, field_a + field_b
    Returns None on any error (missing field, division by zero, etc.).
    """
    try:
        local_ns = {k: float(v) for k, v in stored_data.items() if v is not None}
        tree = ast.parse(computation_rule, mode="eval")

        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            elif isinstance(node, ast.BinOp):
                op_name = type(node.op).__name__
                if op_name not in _SAFE_OPS:
                    raise ValueError(f"Unsupported operator: {op_name}")
                left = _eval(node.left)
                right = _eval(node.right)
                if op_name == "Div" and right == 0:
                    raise ZeroDivisionError
                return _SAFE_OPS[op_name](left, right)
            elif isinstance(node, ast.Name):
                if node.id not in local_ns:
                    raise KeyError(f"Missing field: {node.id}")
                return local_ns[node.id]
            elif isinstance(node, ast.Constant):
                return float(node.value)
            else:
                raise ValueError(f"Unsupported node type: {type(node).__name__}")

        return _eval(tree)
    except (ZeroDivisionError, KeyError, ValueError, SyntaxError):
        return None
    except Exception as e:
        logger.warning(f"Derived feature computation failed for '{computation_rule}': {e}")
        return None
