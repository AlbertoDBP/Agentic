"""
Admin Panel — JSON API for user tax preferences.

Routes:
  GET /api/user/preferences   → returns tax preference keys as flat JSON
  PUT /api/user/preferences   → upserts annual_income, filing_status, state_code
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger("admin.api_preferences")
router = APIRouter(prefix="/api")

# Single-tenant deployment: all prefs live under this tenant_id
_DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001"

_TAX_KEYS = {"annual_income", "filing_status", "state_code"}


def _db():
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return engine


@router.get("/user/preferences")
def get_preferences():
    """Return tax-profile preferences as a flat JSON object."""
    try:
        with _db().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT preference_key, preference_value, value_type
                    FROM platform_shared.user_preferences
                    WHERE tenant_id = :tid
                      AND preference_key = ANY(:keys)
                """),
                {"tid": _DEFAULT_TENANT, "keys": list(_TAX_KEYS)},
            ).mappings().all()
    except Exception as exc:
        logger.error("Failed to read user_preferences: %s", exc)
        return JSONResponse({})

    result: Dict[str, Any] = {}
    for row in rows:
        key = row["preference_key"]
        raw = row["preference_value"]
        vtype = row["value_type"] or "string"
        if vtype == "decimal":
            try:
                result[key] = float(raw)
            except (ValueError, TypeError):
                result[key] = raw
        elif vtype == "integer":
            try:
                result[key] = int(raw)
            except (ValueError, TypeError):
                result[key] = raw
        else:
            result[key] = raw

    return JSONResponse(result)


class TaxPrefsUpdate(BaseModel):
    annual_income: Optional[float] = None
    filing_status: Optional[str] = None
    state_code: Optional[str] = None


@router.put("/user/preferences")
def update_preferences(body: TaxPrefsUpdate):
    """Upsert tax-profile preference keys."""
    updates: list[tuple[str, str, str]] = []

    if body.annual_income is not None:
        updates.append(("annual_income", str(body.annual_income), "decimal"))
    if body.filing_status is not None:
        updates.append(("filing_status", body.filing_status.upper(), "string"))
    if body.state_code is not None:
        updates.append(("state_code", body.state_code.upper() if body.state_code else "", "string"))

    if not updates:
        return JSONResponse({"ok": True, "updated": 0})

    try:
        with _db().begin() as conn:
            for pref_key, pref_val, vtype in updates:
                conn.execute(
                    text("""
                        INSERT INTO platform_shared.user_preferences
                            (tenant_id, preference_key, preference_value, value_type, updated_at)
                        VALUES (:tid, :key, :val, :vtype, NOW())
                        ON CONFLICT (tenant_id, preference_key)
                        DO UPDATE SET
                            preference_value = EXCLUDED.preference_value,
                            value_type       = EXCLUDED.value_type,
                            updated_at       = NOW()
                    """),
                    {"tid": _DEFAULT_TENANT, "key": pref_key, "val": pref_val, "vtype": vtype},
                )
    except Exception as exc:
        logger.error("Failed to upsert user_preferences: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save preferences")

    return JSONResponse({"ok": True, "updated": len(updates)})
