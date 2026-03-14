"""Portfolio — positions table, totals, asset allocation."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger("admin.portfolio")
router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    positions = []
    summary = {"positions": 0, "total_value": 0, "annual_income": 0, "avg_yoc": 0}
    allocation = []

    try:
        with engine.connect() as conn:
            # Summary
            row = conn.execute(text("""
                SELECT COUNT(*) as positions,
                       COALESCE(SUM(current_value), 0) as total_value,
                       COALESCE(SUM(annual_income), 0) as annual_income,
                       COALESCE(AVG(yield_on_cost), 0) as avg_yoc
                FROM platform_shared.positions
                WHERE status = 'ACTIVE'
            """)).fetchone()
            if row:
                summary = dict(row._mapping)

            # Positions
            rows = conn.execute(text("""
                SELECT p.symbol, p.shares, p.cost_basis, p.current_value,
                       p.annual_income, p.yield_on_cost,
                       COALESCE(s.asset_type, 'Unknown') as asset_type,
                       COALESCE(s.name, p.symbol) as name
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s ON p.symbol = s.symbol
                WHERE p.status = 'ACTIVE'
                ORDER BY p.current_value DESC NULLS LAST
            """)).fetchall()
            positions = [dict(r._mapping) for r in rows]

            # Allocation
            rows = conn.execute(text("""
                SELECT COALESCE(s.asset_type, 'Unknown') as asset_type,
                       COUNT(*) as count,
                       COALESCE(SUM(p.current_value), 0) as value
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s ON p.symbol = s.symbol
                WHERE p.status = 'ACTIVE'
                GROUP BY s.asset_type
                ORDER BY value DESC
            """)).fetchall()
            allocation = [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.warning(f"Portfolio query error: {e}")

    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "page": "portfolio",
        "positions": positions,
        "summary": summary,
        "allocation": allocation,
    })
