"""
Admin Panel — JSON API routes for portfolio + position data.
Reads directly from platform_shared tables.

Routes:
  GET  /api/portfolios                    → list all active portfolios
  GET  /api/portfolios/{id}/positions     → all active positions for a portfolio
  POST /api/portfolios/{id}/recalculate   → recompute portfolio total_value from positions
  GET  /api/positions/{symbol}            → single position by symbol (any portfolio)
  PATCH /api/positions/{id}              → update position qty/cost/income/sector/frequency
  GET  /api/market-data/positions         → market data for all held symbols (cache + fallback from positions)
  POST /api/portfolios/{id}/prices        → update market_data_cache prices (manual entry for bonds etc.)

Notes:
  - yield_on_cost is stored in DB as fraction (0.085) but returned as percentage (8.5) in all endpoints.
  - PATCH endpoint accepts yield_on_cost as percentage and divides by 100 before storing.
  - market-data endpoint uses positions as the base row set (LEFT JOIN cache), so all
    held symbols always appear even if cache is sparse.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger("admin.api_portfolio")
router = APIRouter(prefix="/api")


def _db():
    if not engine:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return engine


# ── Portfolios ────────────────────────────────────────────────────────────────

@router.get("/portfolios")
def list_portfolios():
    """Return all active portfolios with account metadata and position count."""
    try:
        with _db().connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    po.id,
                    po.portfolio_name        AS name,
                    COALESCE(a.account_type, 'Unknown') AS account_type,
                    COALESCE(a.broker, '')   AS broker,
                    COALESCE(po.cash_balance, 0)  AS cash_balance,
                    COALESCE(po.total_value, 0)   AS total_value,
                    COUNT(p.id)              AS position_count,
                    po.updated_at            AS last_updated
                FROM platform_shared.portfolios po
                LEFT JOIN platform_shared.accounts a  ON a.id = po.account_id
                LEFT JOIN platform_shared.positions p
                       ON p.portfolio_id = po.id AND p.status = 'ACTIVE'
                WHERE po.status = 'ACTIVE'
                GROUP BY po.id, po.portfolio_name, a.account_type, a.broker,
                         po.cash_balance, po.total_value, po.updated_at
                ORDER BY po.total_value DESC NULLS LAST
            """)).fetchall()
            portfolios = [dict(r._mapping) for r in rows]
            for p in portfolios:
                p["id"] = str(p["id"])
                for k in ("cash_balance", "total_value"):
                    if p[k] is not None:
                        p[k] = float(p[k])
                p["position_count"] = int(p["position_count"])
                if p.get("last_updated"):
                    p["last_updated"] = p["last_updated"].isoformat()
            return JSONResponse(content=portfolios)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("list_portfolios error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Portfolio recalculate ─────────────────────────────────────────────────────

@router.post("/portfolios/{portfolio_id}/recalculate")
def recalculate_portfolio(portfolio_id: str):
    """
    Recompute portfolio.total_value from sum of active position current_values.
    Also recalculates portfolio_weight_pct for each position.
    Call this after manually editing positions.
    """
    try:
        with _db().connect() as conn:
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0) + COALESCE(
                        (SELECT cash_balance FROM platform_shared.portfolios WHERE id = :pid), 0
                    )
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ),
                updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.execute(text("""
                UPDATE platform_shared.positions p
                SET portfolio_weight_pct = ROUND(
                    100.0 * p.current_value / NULLIF(
                        (SELECT SUM(current_value)
                         FROM platform_shared.positions
                         WHERE portfolio_id = :pid AND status = 'ACTIVE'),
                        0
                    ), 3
                )
                WHERE p.portfolio_id = :pid AND p.status = 'ACTIVE'
            """), {"pid": portfolio_id})
            conn.commit()
            row = conn.execute(text("""
                SELECT total_value, cash_balance FROM platform_shared.portfolios WHERE id = :pid
            """), {"pid": portfolio_id}).fetchone()
            return {"recalculated": True, "portfolio_id": portfolio_id,
                    "total_value": float(row[0]) if row and row[0] else 0,
                    "cash_balance": float(row[1]) if row and row[1] else 0}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("recalculate_portfolio error (%s): %s", portfolio_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Positions ─────────────────────────────────────────────────────────────────

# Helper: ensure extra columns exist on positions / securities tables
_extra_cols_checked = False

# Preferred stock pattern: PSA-H, BAC-PL, GS-PA, WFC/PL (dash or slash + letter(s))
_PREFERRED_RE = re.compile(r'^[A-Z0-9]+([-/\.][A-Z]{1,3})$', re.IGNORECASE)

def _infer_asset_type(symbol: str, asset_type: str) -> str:
    """Infer asset type from symbol pattern when DB returns Unknown."""
    if asset_type and asset_type not in ("Unknown", ""):
        return asset_type
    if _PREFERRED_RE.match(symbol):
        return "Preferred"
    return asset_type or "Unknown"


def _ensure_freq_column(conn):
    """Add dividend_frequency and sector to positions/securities tables if not already present."""
    global _extra_cols_checked
    if _extra_cols_checked:
        return
    for ddl in [
        "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS dividend_frequency VARCHAR(30) DEFAULT NULL",
        "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS dividend_frequency VARCHAR(30) DEFAULT NULL",
        "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS sector VARCHAR(100) DEFAULT NULL",
    ]:
        try:
            conn.execute(text(ddl))
            conn.commit()
        except Exception:
            pass
    _extra_cols_checked = True


def _row_to_position(pos: dict) -> dict:
    """Normalize a position row dict: coerce types, convert yield_on_cost fraction→percent."""
    for k in ("id", "portfolio_id"):
        if pos.get(k) is not None:
            pos[k] = str(pos[k])
    for k in ("shares", "cost_basis", "current_value", "market_price",
              "avg_cost", "annual_income", "score"):
        if pos.get(k) is not None:
            pos[k] = float(pos[k])
    # yield_on_cost stored as fraction → return as percentage
    yoc = pos.get("yield_on_cost")
    pos["yield_on_cost"] = round(float(yoc) * 100, 4) if yoc else 0.0
    # current_yield from market_data_cache is already percentage
    cy = pos.get("current_yield")
    pos["current_yield"] = float(cy) if cy else 0.0
    for k in ("price_updated_at", "updated_at"):
        if pos.get(k):
            pos[k] = pos[k].isoformat()
    # Score component fields
    for k in ("valuation_yield_score", "financial_durability_score",
              "technical_entry_score", "nav_erosion_penalty", "signal_penalty"):
        pos[k] = float(pos[k]) if pos.get(k) is not None else 0.0
    pos.setdefault("recommendation", "")
    # factor_details and nav_erosion_details: keep as-is (already dict/None from JSON)

    # Infer asset_type from symbol if Unknown
    pos["asset_type"] = _infer_asset_type(pos.get("symbol", ""), pos.get("asset_type", "Unknown"))
    return pos


@router.get("/portfolios/{portfolio_id}/positions")
def get_positions(portfolio_id: str):
    """
    Return all active positions for a portfolio, enriched with:
    - securities: name, asset_type, sector, dividend_frequency
    - market_data_cache: current price, dividend_yield
    - income_scores: total_score, grade
    yield_on_cost is returned as percentage (not fraction).
    """
    try:
        with _db().connect() as conn:
            _ensure_freq_column(conn)
            rows = conn.execute(text("""
                SELECT
                    p.id,
                    p.portfolio_id,
                    p.symbol,
                    COALESCE(s.name, p.symbol)          AS name,
                    COALESCE(s.asset_type, 'Unknown')   AS asset_type,
                    COALESCE(p.sector, s.sector, '')     AS sector,
                    p.quantity                           AS shares,
                    COALESCE(p.total_cost_basis, p.avg_cost_basis * p.quantity, 0)
                                                         AS cost_basis,
                    COALESCE(p.current_value, 0)         AS current_value,
                    COALESCE(p.current_price, p.avg_cost_basis, 0)
                                                         AS market_price,
                    COALESCE(p.avg_cost_basis, 0)        AS avg_cost,
                    COALESCE(p.annual_income, 0)         AS annual_income,
                    COALESCE(p.yield_on_cost, 0)         AS yield_on_cost,
                    CASE
                        WHEN COALESCE(m.dividend_yield, 0) > 0 THEN m.dividend_yield
                        WHEN COALESCE(p.current_value, 0) > 0 AND COALESCE(p.annual_income, 0) > 0
                             THEN ROUND((p.annual_income / p.current_value) * 100, 2)
                        ELSE 0
                    END                                  AS current_yield,
                    COALESCE(sc.total_score, 0)               AS score,
                    COALESCE(sc.grade, '')                    AS grade,
                    COALESCE(sc.recommendation, '')           AS recommendation,
                    COALESCE(sc.valuation_yield_score, 0)     AS valuation_yield_score,
                    COALESCE(sc.financial_durability_score, 0) AS financial_durability_score,
                    COALESCE(sc.technical_entry_score, 0)     AS technical_entry_score,
                    COALESCE(sc.nav_erosion_penalty, 0)       AS nav_erosion_penalty,
                    sc.factor_details,
                    sc.nav_erosion_details,
                    COALESCE(sc.signal_penalty, 0)            AS signal_penalty,
                    COALESCE(p.dividend_frequency, s.dividend_frequency, '') AS dividend_frequency,
                    p.price_updated_at,
                    p.updated_at
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s
                       ON s.symbol = p.symbol
                LEFT JOIN platform_shared.market_data_cache m
                       ON m.symbol = p.symbol
                LEFT JOIN LATERAL (
                    SELECT total_score, grade, recommendation,
                           valuation_yield_score, financial_durability_score,
                           technical_entry_score, nav_erosion_penalty,
                           factor_details, nav_erosion_details, signal_penalty
                    FROM platform_shared.income_scores
                    WHERE ticker = p.symbol
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) sc ON TRUE
                WHERE p.portfolio_id = :pid
                  AND p.status = 'ACTIVE'
                ORDER BY p.current_value DESC NULLS LAST
            """), {"pid": portfolio_id}).fetchall()

            if not rows and portfolio_id:
                exists = conn.execute(
                    text("SELECT 1 FROM platform_shared.portfolios WHERE id = :id"),
                    {"id": portfolio_id}
                ).fetchone()
                if not exists:
                    raise HTTPException(status_code=404, detail="Portfolio not found")

            positions = [_row_to_position(dict(r._mapping)) for r in rows]
            return JSONResponse(content=positions)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_positions error (%s): %s", portfolio_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Single position by symbol (searches all portfolios) ───────────────────────

@router.get("/positions/{symbol:path}")
def get_position_by_symbol(symbol: str):
    """Return the first active position matching the symbol across all portfolios.
    yield_on_cost is returned as percentage (not fraction).
    """
    try:
        with _db().connect() as conn:
            _ensure_freq_column(conn)
            row = conn.execute(text("""
                SELECT
                    p.id,
                    p.portfolio_id,
                    p.symbol,
                    COALESCE(s.name, p.symbol)          AS name,
                    COALESCE(s.asset_type, 'Unknown')   AS asset_type,
                    COALESCE(p.sector, s.sector, '')     AS sector,
                    p.quantity                           AS shares,
                    COALESCE(p.total_cost_basis, p.avg_cost_basis * p.quantity, 0)
                                                         AS cost_basis,
                    COALESCE(p.current_value, 0)         AS current_value,
                    COALESCE(p.current_price, p.avg_cost_basis, 0)
                                                         AS market_price,
                    COALESCE(p.avg_cost_basis, 0)        AS avg_cost,
                    COALESCE(p.annual_income, 0)         AS annual_income,
                    COALESCE(p.yield_on_cost, 0)         AS yield_on_cost,
                    CASE
                        WHEN COALESCE(m.dividend_yield, 0) > 0 THEN m.dividend_yield
                        WHEN COALESCE(p.current_value, 0) > 0 AND COALESCE(p.annual_income, 0) > 0
                             THEN ROUND((p.annual_income / p.current_value) * 100, 2)
                        ELSE 0
                    END                                  AS current_yield,
                    COALESCE(sc.total_score, 0)               AS score,
                    COALESCE(sc.grade, '')                    AS grade,
                    COALESCE(sc.recommendation, '')           AS recommendation,
                    COALESCE(sc.valuation_yield_score, 0)     AS valuation_yield_score,
                    COALESCE(sc.financial_durability_score, 0) AS financial_durability_score,
                    COALESCE(sc.technical_entry_score, 0)     AS technical_entry_score,
                    COALESCE(sc.nav_erosion_penalty, 0)       AS nav_erosion_penalty,
                    sc.factor_details,
                    sc.nav_erosion_details,
                    COALESCE(sc.signal_penalty, 0)            AS signal_penalty,
                    COALESCE(p.dividend_frequency, s.dividend_frequency, '') AS dividend_frequency,
                    p.price_updated_at,
                    p.updated_at
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s
                       ON s.symbol = p.symbol
                LEFT JOIN platform_shared.market_data_cache m
                       ON m.symbol = p.symbol
                LEFT JOIN LATERAL (
                    SELECT total_score, grade, recommendation,
                           valuation_yield_score, financial_durability_score,
                           technical_entry_score, nav_erosion_penalty,
                           factor_details, nav_erosion_details, signal_penalty
                    FROM platform_shared.income_scores
                    WHERE ticker = p.symbol
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) sc ON TRUE
                WHERE UPPER(p.symbol) = UPPER(:sym)
                  AND p.status = 'ACTIVE'
                ORDER BY p.current_value DESC NULLS LAST
                LIMIT 1
            """), {"sym": symbol}).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Position not found: {symbol.upper()}")

            pos = _row_to_position(dict(row._mapping))
            return JSONResponse(content=pos)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_position_by_symbol error (%s): %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Update a position (quantity, cost, income, sector, frequency) ─────────────

class PositionUpdate(BaseModel):
    quantity: Optional[float] = None
    avg_cost_basis: Optional[float] = None       # per-share cost basis
    annual_income: Optional[float] = None
    yield_on_cost: Optional[float] = None        # as percentage (e.g. 8.5); stored as fraction
    current_price: Optional[float] = None
    sector: Optional[str] = None                 # updates securities.sector
    dividend_frequency: Optional[str] = None     # stored in positions.dividend_frequency


@router.patch("/positions/{position_id}")
def update_position(position_id: str, update: PositionUpdate):
    """
    Partially update a position's quantity, cost basis, income, price, sector, or frequency.
    - Recalculates total_cost_basis = qty * avg_cost_basis
    - Recalculates current_value = qty * current_price
    - Stores yield_on_cost as fraction (input percentage / 100)
    - Updates securities.sector if sector provided
    - Refreshes parent portfolio's total_value
    """
    try:
        with _db().connect() as conn:
            _ensure_freq_column(conn)
            row = conn.execute(text("""
                SELECT id, portfolio_id, symbol, quantity, avg_cost_basis, current_price
                FROM platform_shared.positions
                WHERE id = :id AND status = 'ACTIVE'
            """), {"id": position_id}).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")

            pos_id, portfolio_id, sym = str(row[0]), str(row[1]), str(row[2])
            qty = update.quantity if update.quantity is not None else float(row[3] or 0)
            avg_cb = update.avg_cost_basis if update.avg_cost_basis is not None else float(row[4] or 0)
            cur_price = update.current_price if update.current_price is not None else float(row[5] or avg_cb)

            # yield_on_cost: receive as percentage, store as fraction
            yoc_frac = (update.yield_on_cost / 100.0) if update.yield_on_cost is not None else None

            conn.execute(text("""
                UPDATE platform_shared.positions SET
                    quantity          = :qty,
                    avg_cost_basis    = :avg_cb,
                    total_cost_basis  = ROUND(:qty * :avg_cb, 2),
                    current_price     = :cur_price,
                    current_value     = ROUND(:qty * :cur_price, 2),
                    annual_income     = COALESCE(:annual_income, annual_income),
                    yield_on_cost     = COALESCE(:yoc, yield_on_cost),
                    dividend_frequency = COALESCE(:freq, dividend_frequency),
                    sector            = COALESCE(:sector, sector),
                    updated_at        = NOW()
                WHERE id = :id AND status = 'ACTIVE'
            """), {
                "qty": qty, "avg_cb": avg_cb, "cur_price": cur_price,
                "annual_income": update.annual_income,
                "yoc": yoc_frac,
                "freq": update.dividend_frequency,
                "sector": update.sector,
                "id": position_id,
            })

            # Update sector and/or dividend_frequency in securities if provided
            if update.sector is not None or update.dividend_frequency is not None:
                conn.execute(text("""
                    UPDATE platform_shared.securities
                    SET sector             = COALESCE(:sector, sector),
                        dividend_frequency = COALESCE(:freq, dividend_frequency),
                        updated_at         = NOW()
                    WHERE symbol = :sym
                """), {"sector": update.sector, "freq": update.dividend_frequency, "sym": sym})

            # Refresh portfolio total
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0) + COALESCE(cash_balance, 0)
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ), updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.commit()
            return {"updated": True, "position_id": position_id, "portfolio_id": portfolio_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_position error (%s): %s", position_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Delete (soft-close) a position ───────────────────────────────────────────

@router.delete("/positions/{position_id}")
def delete_position(position_id: str):
    """
    Soft-delete a position: set status = 'CLOSED' and closed_date = today.
    Refreshes the parent portfolio total_value.
    """
    try:
        with _db().connect() as conn:
            row = conn.execute(text("""
                SELECT portfolio_id FROM platform_shared.positions
                WHERE id = :id AND status = 'ACTIVE'
            """), {"id": position_id}).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")
            portfolio_id = str(row[0])

            conn.execute(text("""
                UPDATE platform_shared.positions
                SET status = 'CLOSED', closed_date = CURRENT_DATE, updated_at = NOW()
                WHERE id = :id
            """), {"id": position_id})

            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0) + COALESCE(cash_balance, 0)
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ), updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.commit()
            return {"deleted": True, "position_id": position_id, "portfolio_id": portfolio_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_position error (%s): %s", position_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Monthly income distribution ────────────────────────────────────────────────

@router.get("/portfolios/{portfolio_id}/income-by-month")
def get_income_by_month(portfolio_id: str):
    """
    Return estimated monthly income distribution for a portfolio.
    Distributes annual_income based on dividend_frequency.
    Monthly: 1/12 each month. Quarterly: months 3,6,9,12.
    Semi-Annual: months 6,12. Annual: month 12.
    """
    FREQ_MONTHS: dict[str, list[int]] = {
        "Monthly":     list(range(1, 13)),
        "Quarterly":   [3, 6, 9, 12],
        "Semi-Annual": [6, 12],
        "Annual":      [12],
    }
    try:
        with _db().connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    p.symbol,
                    COALESCE(s.name, p.symbol)          AS name,
                    COALESCE(p.annual_income, 0)         AS annual_income,
                    COALESCE(p.dividend_frequency, s.dividend_frequency, 'Quarterly') AS frequency
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
                WHERE p.portfolio_id = :pid AND p.status = 'ACTIVE'
                  AND COALESCE(p.annual_income, 0) > 0
                ORDER BY p.annual_income DESC
            """), {"pid": portfolio_id}).fetchall()

            # Build per-month totals (months 1-12)
            monthly: dict[int, float] = {m: 0.0 for m in range(1, 13)}
            positions_by_month: list[dict] = []

            for r in rows:
                row = dict(r._mapping)
                annual = float(row["annual_income"])
                freq_str = (row["frequency"] or "Quarterly").strip()
                pay_months = FREQ_MONTHS.get(freq_str, FREQ_MONTHS["Quarterly"])
                per_payment = round(annual / len(pay_months), 2)

                symbol_months = {m: 0.0 for m in range(1, 13)}
                for m in pay_months:
                    monthly[m] += per_payment
                    symbol_months[m] = per_payment

                positions_by_month.append({
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "annual_income": annual,
                    "frequency": freq_str,
                    "monthly": symbol_months,
                })

            MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            monthly_series = [
                {"month": MONTH_NAMES[m - 1], "month_num": m, "total": round(monthly[m], 2)}
                for m in range(1, 13)
            ]
            return JSONResponse(content={
                "portfolio_id": portfolio_id,
                "monthly_totals": monthly_series,
                "positions": positions_by_month,
                "annual_total": round(sum(monthly.values()), 2),
            })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_income_by_month error (%s): %s", portfolio_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Market data for all held symbols (cache + fallback from positions) ────────

@router.get("/market-data/positions")
def get_market_data_for_positions():
    """
    Return market data for all symbols held in active portfolios.
    Uses positions as the base set so ALL held symbols appear — even those not
    yet in market_data_cache. Cache data is merged where available.
    """
    try:
        with _db().connect() as conn:
            rows = conn.execute(text("""
                WITH pos_agg AS (
                    SELECT symbol,
                           SUM(current_value)  AS current_value,
                           SUM(annual_income)  AS annual_income
                    FROM platform_shared.positions
                    WHERE status = 'ACTIVE'
                    GROUP BY symbol
                )
                SELECT
                    p.symbol,
                    COALESCE(s.name, p.symbol)          AS name,
                    COALESCE(s.asset_type, 'Unknown')   AS asset_type,
                    COALESCE(m.price, p.current_price, 0) AS price,
                    COALESCE(m.price_change_pct, 0)     AS change_pct,
                    COALESCE(m.volume_avg_10d, 0)        AS volume,
                    m.week52_high,
                    m.week52_low,
                    COALESCE(m.market_cap_m, 0)          AS market_cap,
                    m.pe_ratio,
                    CASE
                        WHEN COALESCE(m.dividend_yield, 0) > 0 THEN m.dividend_yield
                        WHEN COALESCE(pa.current_value, 0) > 0 AND COALESCE(pa.annual_income, 0) > 0
                             THEN ROUND((pa.annual_income / pa.current_value) * 100, 2)
                        ELSE 0
                    END                                  AS dividend_yield,
                    m.payout_ratio,
                    m.beta,
                    m.chowder_number,
                    m.nav_value                          AS nav,
                    m.nav_discount_pct                   AS premium_discount,
                    m.ex_div_date                        AS ex_date,
                    COALESCE(m.snapshot_date, p.price_updated_at::date) AS snapshot_date
                FROM (
                    SELECT DISTINCT ON (symbol)
                        symbol, current_price, price_updated_at
                    FROM platform_shared.positions
                    WHERE status = 'ACTIVE'
                    ORDER BY symbol, current_value DESC NULLS LAST
                ) p
                LEFT JOIN platform_shared.market_data_cache m ON m.symbol = p.symbol
                LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
                LEFT JOIN pos_agg pa ON pa.symbol = p.symbol
                ORDER BY p.symbol
            """)).fetchall()

            result = []
            for r in rows:
                item = dict(r._mapping)
                for k in ("price", "change_pct", "dividend_yield"):
                    item[k] = float(item[k]) if item.get(k) is not None else 0.0
                for k in ("week52_high", "week52_low", "pe_ratio", "payout_ratio", "beta", "chowder_number", "nav", "premium_discount"):
                    item[k] = float(item[k]) if item.get(k) is not None else None
                price = item["price"]
                pct = item["change_pct"]
                item["change"] = round(price - price / (1 + pct / 100), 4) if price and pct else 0.0
                mc = item.get("market_cap")
                item["market_cap"] = round(float(mc), 2) if mc else 0.0
                vol = item.get("volume")
                item["volume"] = int(vol) if vol else 0
                # Null-fill fields not in DB
                item["day_high"] = None
                item["day_low"] = None
                item["eps"] = None
                item["dividend_growth_5y"] = None
                item["avg_volume"] = None
                ex = item.get("ex_date")
                item["ex_date"] = ex.isoformat() if ex and hasattr(ex, "isoformat") else (str(ex) if ex else None)
                sd = item.get("snapshot_date")
                if sd:
                    item["snapshot_date"] = sd.isoformat() if hasattr(sd, "isoformat") else str(sd)
                result.append(item)

            return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_market_data_for_positions error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Manual price update (for bonds / unpriced symbols) ────────────────────────

class PriceUpdate(BaseModel):
    symbol: str
    price: float
    dividend_yield: Optional[float] = None


@router.post("/portfolios/{portfolio_id}/prices")
def update_prices(portfolio_id: str, updates: list[PriceUpdate]):
    """
    Manually set prices for symbols that automated feeds can't price (bonds, OTC, etc.).
    Updates market_data_cache and positions.current_price / current_value.
    """
    try:
        with _db().connect() as conn:
            updated = []
            for u in updates:
                conn.execute(text("""
                    UPDATE platform_shared.market_data_cache
                    SET price = :price,
                        dividend_yield = COALESCE(:dy, dividend_yield),
                        fetched_at = NOW(),
                        snapshot_date = CURRENT_DATE
                    WHERE symbol = :sym
                """), {"price": u.price, "dy": u.dividend_yield, "sym": u.symbol})

                conn.execute(text("""
                    UPDATE platform_shared.positions
                    SET current_price = :price,
                        current_value = ROUND(quantity * :price, 2),
                        price_updated_at = NOW(),
                        updated_at = NOW()
                    WHERE symbol = :sym AND portfolio_id = :pid AND status = 'ACTIVE'
                """), {"price": u.price, "sym": u.symbol, "pid": portfolio_id})
                updated.append(u.symbol)

            # Refresh portfolio total
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0) + COALESCE(cash_balance, 0)
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ), updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.commit()
            return {"updated": updated}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_prices error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
