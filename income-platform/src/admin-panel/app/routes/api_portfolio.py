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

import logging
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

# Helper: ensure dividend_frequency column exists on positions table
_freq_col_checked = False

def _ensure_freq_column(conn):
    """Add dividend_frequency to positions and securities tables if not already present."""
    global _freq_col_checked
    if _freq_col_checked:
        return
    for ddl in [
        "ALTER TABLE platform_shared.positions ADD COLUMN IF NOT EXISTS dividend_frequency VARCHAR(30) DEFAULT NULL",
        "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS dividend_frequency VARCHAR(30) DEFAULT NULL",
    ]:
        try:
            conn.execute(text(ddl))
            conn.commit()
        except Exception:
            pass
    _freq_col_checked = True


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
                    COALESCE(s.sector, '')               AS sector,
                    p.quantity                           AS shares,
                    COALESCE(p.total_cost_basis, p.avg_cost_basis * p.quantity, 0)
                                                         AS cost_basis,
                    COALESCE(p.current_value, 0)         AS current_value,
                    COALESCE(p.current_price, p.avg_cost_basis, 0)
                                                         AS market_price,
                    COALESCE(p.avg_cost_basis, 0)        AS avg_cost,
                    COALESCE(p.annual_income, 0)         AS annual_income,
                    COALESCE(p.yield_on_cost, 0)         AS yield_on_cost,
                    COALESCE(m.dividend_yield, 0)        AS current_yield,
                    COALESCE(sc.total_score, 0)          AS score,
                    COALESCE(sc.grade, '')               AS grade,
                    COALESCE(p.dividend_frequency, s.dividend_frequency, '') AS dividend_frequency,
                    p.price_updated_at,
                    p.updated_at
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s
                       ON s.symbol = p.symbol
                LEFT JOIN platform_shared.market_data_cache m
                       ON m.symbol = p.symbol
                LEFT JOIN LATERAL (
                    SELECT total_score, grade
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

@router.get("/positions/{symbol}")
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
                    COALESCE(s.sector, '')               AS sector,
                    p.quantity                           AS shares,
                    COALESCE(p.total_cost_basis, p.avg_cost_basis * p.quantity, 0)
                                                         AS cost_basis,
                    COALESCE(p.current_value, 0)         AS current_value,
                    COALESCE(p.current_price, p.avg_cost_basis, 0)
                                                         AS market_price,
                    COALESCE(p.avg_cost_basis, 0)        AS avg_cost,
                    COALESCE(p.annual_income, 0)         AS annual_income,
                    COALESCE(p.yield_on_cost, 0)         AS yield_on_cost,
                    COALESCE(m.dividend_yield, 0)        AS current_yield,
                    COALESCE(sc.total_score, 0)          AS score,
                    COALESCE(sc.grade, '')               AS grade,
                    COALESCE(p.dividend_frequency, s.dividend_frequency, '') AS dividend_frequency,
                    p.price_updated_at,
                    p.updated_at
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s
                       ON s.symbol = p.symbol
                LEFT JOIN platform_shared.market_data_cache m
                       ON m.symbol = p.symbol
                LEFT JOIN LATERAL (
                    SELECT total_score, grade
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
                    updated_at        = NOW()
                WHERE id = :id AND status = 'ACTIVE'
            """), {
                "qty": qty, "avg_cb": avg_cb, "cur_price": cur_price,
                "annual_income": update.annual_income,
                "yoc": yoc_frac,
                "freq": update.dividend_frequency,
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
                    COALESCE(m.dividend_yield, 0)        AS dividend_yield,
                    m.payout_ratio,
                    m.beta,
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
                ORDER BY p.symbol
            """)).fetchall()

            result = []
            for r in rows:
                item = dict(r._mapping)
                for k in ("price", "change_pct", "dividend_yield"):
                    item[k] = float(item[k]) if item.get(k) is not None else 0.0
                for k in ("week52_high", "week52_low", "pe_ratio", "payout_ratio", "beta"):
                    item[k] = float(item[k]) if item.get(k) is not None else None
                price = item["price"]
                pct = item["change_pct"]
                item["change"] = round(price - price / (1 + pct / 100), 4) if price and pct else 0.0
                mc = item.get("market_cap")
                item["market_cap"] = round(float(mc), 2) if mc else 0.0
                vol = item.get("volume")
                item["volume"] = int(vol) if vol else 0
                # Null-fill fields not available from cache
                item["day_high"] = None
                item["day_low"] = None
                item["eps"] = None
                item["dividend_growth_5y"] = None
                item["nav"] = None
                item["premium_discount"] = None
                item["avg_volume"] = None
                item["ex_date"] = None
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
