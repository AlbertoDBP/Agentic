"""All data-quality REST endpoints — §8 of the spec."""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.clients.fmp import FMPHealClient
from app.clients.massive import MASSIVEHealClient
from app.config import settings
from app.database import get_db, get_db_context
from app.gate import evaluate_gate, record_scoring_completed
from app.healer import HealerEngine
from app.promoter import run_promotion
from app.scanner import run_scan

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared client instances (stateless HTTP clients)
_fmp = FMPHealClient(
    api_key=settings.fmp_api_key,
    base_url=settings.fmp_base_url,
    timeout=settings.fmp_request_timeout,
)
_massive = MASSIVEHealClient(
    api_key=settings.massive_api_key,
    base_url=settings.massive_base_url,
    timeout=settings.massive_request_timeout,
)
_healer = HealerEngine(fmp_client=_fmp, massive_client=_massive)


# ── Trigger scan ──────────────────────────────────────────────────────────────

class ScanTriggerRequest(BaseModel):
    market_refreshed_at: Optional[str] = None  # ISO timestamp from caller


@router.post("/scan/trigger", status_code=202, dependencies=[Depends(verify_token)])
def trigger_scan(request: ScanTriggerRequest, background: BackgroundTasks):
    """
    Called by scheduler after market data refresh completes.
    Responds immediately with 202; scan runs in background.
    """
    background.add_task(_run_scan_background, request.market_refreshed_at)
    return {"status": "accepted", "message": "Scan queued"}


def _run_scan_background(market_refreshed_at: Optional[str]):
    with get_db_context() as db:
        if market_refreshed_at:
            db.execute(text("""
                INSERT INTO platform_shared.data_refresh_log
                    (portfolio_id, market_data_refreshed_at, updated_at)
                SELECT DISTINCT p.id, :ts::TIMESTAMPTZ, NOW()
                FROM platform_shared.portfolios p
                JOIN platform_shared.positions pos ON pos.portfolio_id = p.id
                WHERE pos.quantity > 0 AND p.is_active = TRUE
                ON CONFLICT (portfolio_id) DO UPDATE SET
                    market_data_refreshed_at = :ts::TIMESTAMPTZ, updated_at = NOW()
            """), {"ts": market_refreshed_at})
            db.commit()

        summary = run_scan(db)
        logger.info(f"Background scan complete: {summary}")
        portfolios = db.execute(text("""
            SELECT DISTINCT p.id FROM platform_shared.portfolios p
            JOIN platform_shared.positions pos ON pos.portfolio_id = p.id
            WHERE pos.quantity > 0 AND p.is_active = TRUE
        """)).fetchall()
        for p in portfolios:
            evaluate_gate(db, str(p.id))


# ── Gate check ────────────────────────────────────────────────────────────────

@router.get("/gate/{portfolio_id}", dependencies=[Depends(verify_token)])
def get_gate(portfolio_id: str, db: Session = Depends(get_db)):
    result = evaluate_gate(db, portfolio_id)
    return {
        "portfolio_id": portfolio_id,
        "status": result.status,
        "blocking_issue_count": result.blocking_issue_count,
        "gate_passed_at": result.gate_passed_at,
    }


@router.post("/gate/{portfolio_id}/scoring-complete", dependencies=[Depends(verify_token)])
def mark_scoring_complete(portfolio_id: str, db: Session = Depends(get_db)):
    record_scoring_completed(db, portfolio_id)
    return {"status": "recorded", "portfolio_id": portfolio_id}


# ── Issues ────────────────────────────────────────────────────────────────────

@router.get("/issues", dependencies=[Depends(verify_token)])
def list_issues(
    symbol: Optional[str] = Query(None),
    asset_class: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = "WHERE 1=1"
    params: dict = {}
    if symbol:
        filters += " AND i.symbol = :symbol"
        params["symbol"] = symbol
    if asset_class:
        filters += " AND i.asset_class = :asset_class"
        params["asset_class"] = asset_class
    if severity:
        filters += " AND i.severity = :severity"
        params["severity"] = severity
    if status:
        filters += " AND i.status = :status"
        params["status"] = status

    rows = db.execute(
        text(f"SELECT * FROM platform_shared.data_quality_issues i {filters} ORDER BY created_at DESC LIMIT 500"),
        params,
    ).fetchall()
    return {"issues": [dict(r._mapping) for r in rows]}


@router.get("/issues/{symbol}", dependencies=[Depends(verify_token)])
def get_issues_for_symbol(symbol: str, db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT * FROM platform_shared.data_quality_issues WHERE symbol=:s ORDER BY created_at DESC"),
        {"s": symbol},
    ).fetchall()
    return {"symbol": symbol, "issues": [dict(r._mapping) for r in rows]}


@router.post("/issues/{issue_id}/retry", dependencies=[Depends(verify_token)])
def retry_issue(issue_id: int, background: BackgroundTasks):
    background.add_task(_retry_single, issue_id)
    return {"status": "accepted", "issue_id": issue_id}


def _retry_single(issue_id: int):
    with get_db_context() as db:
        issue = db.execute(
            text("""
                SELECT i.*, r.fetch_source_primary, r.fetch_source_fallback
                FROM platform_shared.data_quality_issues i
                LEFT JOIN platform_shared.field_requirements r
                       ON r.asset_class = i.asset_class AND r.field_name = i.field_name
                WHERE i.id = :id
            """),
            {"id": issue_id},
        ).fetchone()
        if not issue:
            return
        db.execute(
            text("UPDATE platform_shared.data_quality_issues SET attempt_count=0, status='missing' WHERE id=:id"),
            {"id": issue_id},
        )
        db.commit()
        _healer.run_retry_pass(db)


@router.post("/issues/{issue_id}/mark-na", dependencies=[Depends(verify_token)])
def mark_na(issue_id: int, reason: Optional[str] = Query(None), db: Session = Depends(get_db)):
    issue = db.execute(
        text("SELECT * FROM platform_shared.data_quality_issues WHERE id=:id"),
        {"id": issue_id},
    ).fetchone()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    db.execute(
        text("""
            INSERT INTO platform_shared.data_quality_exemptions
                (symbol, field_name, asset_class, reason)
            VALUES (:s, :f, :ac, :r)
            ON CONFLICT (symbol, field_name) DO NOTHING
        """),
        {"s": issue.symbol, "f": issue.field_name, "ac": issue.asset_class, "r": reason},
    )
    db.execute(
        text("UPDATE platform_shared.data_quality_issues SET status='resolved', resolved_at=NOW() WHERE id=:id"),
        {"id": issue_id},
    )
    db.commit()
    return {"status": "exempted", "symbol": issue.symbol, "field_name": issue.field_name}


@router.post("/issues/{issue_id}/reclassify", dependencies=[Depends(verify_token)])
def reclassify(issue_id: int, db: Session = Depends(get_db)):
    """Placeholder — triggers asset re-classification via agent-04."""
    issue = db.execute(
        text("SELECT symbol FROM platform_shared.data_quality_issues WHERE id=:id"),
        {"id": issue_id},
    ).fetchone()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"status": "reclassify_queued", "symbol": issue.symbol,
            "note": "Integrate with agent-04 classify endpoint as needed"}


# ── Refresh log ───────────────────────────────────────────────────────────────

@router.get("/refresh-log/{portfolio_id}", dependencies=[Depends(verify_token)])
def get_refresh_log(portfolio_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM platform_shared.data_refresh_log WHERE portfolio_id=:pid"),
        {"pid": portfolio_id},
    ).fetchone()
    if not row:
        return {"portfolio_id": portfolio_id, "market_data_refreshed_at": None,
                "scores_recalculated_at": None, "market_staleness_hrs": None}
    return dict(row._mapping)


# ── Field requirements (admin) ────────────────────────────────────────────────

@router.get("/field-requirements", dependencies=[Depends(verify_token)])
def list_field_requirements(db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT * FROM platform_shared.field_requirements ORDER BY asset_class, field_name")
    ).fetchall()
    return {"requirements": [dict(r._mapping) for r in rows]}


class FieldRequirementPatch(BaseModel):
    fetch_source_primary: Optional[str] = None
    fetch_source_fallback: Optional[str] = None
    required: Optional[bool] = None


@router.patch("/field-requirements/{req_id}", dependencies=[Depends(verify_token)])
def patch_field_requirement(req_id: int, body: FieldRequirementPatch, db: Session = Depends(get_db)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["id"] = req_id
    db.execute(text(f"UPDATE platform_shared.field_requirements SET {set_clause} WHERE id=:id"), updates)
    db.commit()
    return {"status": "updated", "id": req_id}


# ── Retry loop endpoint (called by scheduler every 15 min) ────────────────────

@router.post("/retry-open", status_code=202, dependencies=[Depends(verify_token)])
def retry_open(background: BackgroundTasks):
    """Trigger a retry pass for all open issues."""
    background.add_task(_retry_all)
    return {"status": "accepted"}


def _retry_all():
    with get_db_context() as db:
        result = _healer.run_retry_pass(db)
        logger.info(f"Retry pass complete: {result}")


# ── Promoter endpoint (called by scheduler nightly) ───────────────────────────

@router.post("/promote", status_code=202, dependencies=[Depends(verify_token)])
def promote(background: BackgroundTasks):
    background.add_task(_run_promote)
    return {"status": "accepted"}


def _run_promote():
    with get_db_context() as db:
        result = run_promotion(db)
        logger.info(f"Promotion pass complete: {result}")
