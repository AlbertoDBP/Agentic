"""
Admin Panel — JSON API routes for portfolio + position data.
Reads directly from platform_shared tables.

Routes:
  GET    /api/portfolios                  → list all active portfolios
  POST   /api/portfolios                  → create portfolio + account record
  PATCH  /api/portfolios/{id}             → update portfolio name/account_type/broker
  DELETE /api/portfolios/{id}             → soft-delete (ARCHIVED) + close positions
  GET    /api/portfolios/{id}/positions   → all active positions for a portfolio
  POST   /api/portfolios/{id}/recalculate → recompute portfolio total_value from positions
  GET  /api/positions/{symbol}            → single position by symbol (any portfolio)
  PATCH /api/positions/{id}              → update position qty/cost/income/sector/frequency
  GET  /api/market-data/positions         → market data for all held symbols (cache + fallback from positions)
  POST /api/portfolios/{id}/prices        → update market_data_cache prices (manual entry for bonds etc.)
  GET  /api/market-data/quote/{symbol}    → price + yield from DB for any symbol (scanner use)

Notes:
  - yield_on_cost is stored in DB as fraction (0.085) but returned as percentage (8.5) in all endpoints.
  - PATCH endpoint accepts yield_on_cost as percentage and divides by 100 before storing.
  - market-data endpoint uses positions as the base row set (LEFT JOIN cache), so all
    held symbols always appear even if cache is sparse.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import auth_headers
from app.config import settings
from app.database import engine

logger = logging.getLogger("admin.api_portfolio")
router = APIRouter(prefix="/api")

_DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001"

# Dividend frequency by asset class (best-effort heuristic)
_FREQ_BY_CLASS: dict[str, str] = {
    "CEF":              "Monthly",
    "COVERED_CALL_ETF": "Monthly",
    "MORTGAGE_REIT":    "Monthly",
    "BDC":              "Quarterly",
    "MLP":              "Quarterly",
    "PREFERRED":        "Quarterly",
    "DIVIDEND_STOCK":   "Quarterly",
    "REIT":             "Quarterly",
    "BOND":             "Semi-Annual",
}

_ACCOUNT_TYPE_NORM = {
    "taxable": "taxable", "brokerage": "taxable",
    "traditional ira": "traditional_ira", "traditional_ira": "traditional_ira", "ira": "traditional_ira",
    "roth ira": "roth_ira", "roth_ira": "roth_ira", "roth": "roth_ira",
    "401k": "401k", "401(k)": "401k",
    "403b": "403b", "403(b)": "403b",
    "hsa": "hsa", "custodial": "custodial",
}


def _normalize_account_type(raw: str) -> str:
    return _ACCOUNT_TYPE_NORM.get(raw.lower().strip(), "taxable")


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
                    po.updated_at            AS last_updated,
                    po.last_refreshed_at     AS last_refreshed_at
                FROM platform_shared.portfolios po
                LEFT JOIN platform_shared.accounts a  ON a.id = po.account_id
                LEFT JOIN platform_shared.positions p
                       ON p.portfolio_id = po.id AND p.status = 'ACTIVE'
                WHERE po.status = 'ACTIVE'
                GROUP BY po.id, po.portfolio_name, a.account_type, a.broker,
                         po.cash_balance, po.total_value, po.updated_at, po.last_refreshed_at
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
                if p.get("last_refreshed_at"):
                    p["last_refreshed_at"] = p["last_refreshed_at"].isoformat()
                else:
                    p["last_refreshed_at"] = None
            return JSONResponse(content=portfolios)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("list_portfolios error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


class PortfolioCreate(BaseModel):
    name: str
    account_type: str = "taxable"
    broker: str = ""


class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    account_type: Optional[str] = None
    broker: Optional[str] = None


@router.post("/portfolios")
def create_portfolio(body: PortfolioCreate):
    """Create a new portfolio with an associated account record."""
    try:
        pid = str(uuid4())
        acct_id = str(uuid4())
        acct_type = _normalize_account_type(body.account_type)
        with _db().begin() as conn:
            conn.execute(text("""
                INSERT INTO platform_shared.accounts
                    (id, tenant_id, account_name, account_type, broker, currency, is_active, created_at, updated_at)
                VALUES
                    (:id, :tid, :name, :acct_type, :broker, 'USD', TRUE, NOW(), NOW())
            """), {"id": acct_id, "tid": _DEFAULT_TENANT, "name": body.name,
                   "acct_type": acct_type, "broker": body.broker or ""})
            conn.execute(text("""
                INSERT INTO platform_shared.portfolios
                    (id, tenant_id, account_id, portfolio_name, status, cash_balance, total_value, created_at, updated_at)
                VALUES
                    (:id, :tid, :acct_id, :name, 'ACTIVE', 0, 0, NOW(), NOW())
            """), {"id": pid, "tid": _DEFAULT_TENANT, "acct_id": acct_id, "name": body.name})
        return JSONResponse(content={
            "id": pid, "name": body.name, "account_type": acct_type,
            "broker": body.broker or "", "cash_balance": 0.0,
            "total_value": 0.0, "position_count": 0,
        })
    except Exception as exc:
        logger.error("create_portfolio error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: str, body: PortfolioUpdate):
    """Update portfolio name and/or account attributes."""
    try:
        with _db().begin() as conn:
            if body.name:
                conn.execute(text("""
                    UPDATE platform_shared.portfolios
                    SET portfolio_name = :name, updated_at = NOW()
                    WHERE id = :pid
                """), {"name": body.name, "pid": portfolio_id})
            if body.account_type is not None or body.broker is not None:
                updates, params = [], {"pid": portfolio_id}
                if body.account_type is not None:
                    updates.append("account_type = :acct_type")
                    params["acct_type"] = _normalize_account_type(body.account_type)
                if body.broker is not None:
                    updates.append("broker = :broker")
                    params["broker"] = body.broker
                if updates:
                    conn.execute(text(f"""
                        UPDATE platform_shared.accounts a
                        SET {", ".join(updates)}, updated_at = NOW()
                        FROM platform_shared.portfolios p
                        WHERE p.id = :pid AND a.id = p.account_id
                    """), params)
        return JSONResponse(content={"status": "ok"})
    except Exception as exc:
        logger.error("update_portfolio error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/portfolios/{portfolio_id}")
def delete_portfolio(portfolio_id: str):
    """Soft-delete a portfolio and close all its positions."""
    try:
        with _db().begin() as conn:
            conn.execute(text("""
                UPDATE platform_shared.positions
                SET status = 'CLOSED', updated_at = NOW()
                WHERE portfolio_id = :pid AND status = 'ACTIVE'
            """), {"pid": portfolio_id})
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET status = 'ARCHIVED', updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
        return JSONResponse(content={"status": "ok"})
    except Exception as exc:
        logger.error("delete_portfolio error: %s", exc)
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


# ── Portfolio data refresh pipeline ──────────────────────────────────────────

@router.post("/portfolios/{portfolio_id}/refresh")
async def refresh_portfolio_data(portfolio_id: str):
    """
    Trigger full data refresh pipeline for a manually managed portfolio:
      1. Ensure all position symbols exist in platform_shared.securities
      2. Batch-refresh market_data_cache via opportunity-scanner service
      2b. Classify all symbols via asset-classification service; write asset_type to securities
      3. Score all symbols via income-scoring service (asset_class from step 2b + gate_data={})
      4. Recalculate portfolio totals
    Returns a summary of what was processed.
    """
    try:
        # 1. Fetch symbols for this portfolio
        with _db().connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT p.symbol, COALESCE(s.asset_type, 'Unknown') AS asset_type
                FROM platform_shared.positions p
                LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
                WHERE p.portfolio_id = :pid AND p.status = 'ACTIVE'
                ORDER BY p.symbol
            """), {"pid": portfolio_id}).fetchall()

        symbols = [dict(r._mapping) for r in rows]
        if not symbols:
            return JSONResponse(content={"status": "ok", "symbols": [], "message": "No active positions to refresh"})

        ticker_list = [r["symbol"] for r in symbols]
        headers = auth_headers()
        scored, score_errors, cache_refreshed = 0, [], False

        async with httpx.AsyncClient(timeout=120) as client:
            # 2. Refresh market_data_cache for all held symbols — always force=true so previously
            #    stale/NULL entries (e.g. from earlier 401 run today) get re-fetched with real data.
            try:
                scanner_url = f"{settings.agent07_url}/cache/refresh?force=true"
                resp = await client.post(scanner_url, headers=headers,
                                         json={"symbols": ticker_list})
                cache_refreshed = resp.status_code < 400
                if cache_refreshed:
                    logger.info("cache/refresh OK: %s", resp.text[:200])
            except Exception as e:
                logger.warning("cache/refresh failed: %s", e)

            # 2b. Classify all symbols via agent-04 (batch, up to 100 per call)
            #     and write asset_type back to platform_shared.securities.
            asset_class_map: dict[str, str] = {}
            try:
                # Standard symbols only (skip slash-format preferreds and bond CUSIPs)
                classifiable = [t for t in ticker_list if "/" not in t and len(t) <= 8]
                batch_size = 100
                for i in range(0, len(classifiable), batch_size):
                    batch = classifiable[i: i + batch_size]
                    try:
                        r = await client.post(
                            f"{settings.agent04_url}/classify/batch",
                            headers=headers,
                            json={"tickers": batch},
                            timeout=30,
                        )
                        if r.status_code == 200:
                            data = r.json()
                            for item in data.get("results", []):
                                sym = item.get("ticker", "").upper()
                                ac = item.get("asset_class") or item.get("asset_type")
                                if sym and ac:
                                    asset_class_map[sym] = ac
                    except Exception as be:
                        logger.warning("classify/batch failed (batch %d): %s", i, be)

                # Write classifications back to securities table
                if asset_class_map:
                    with _db().connect() as conn:
                        for sym, ac in asset_class_map.items():
                            conn.execute(text("""
                                UPDATE platform_shared.securities
                                SET asset_type = :ac, updated_at = NOW()
                                WHERE symbol = :sym
                            """), {"sym": sym, "ac": ac})
                        conn.commit()
                    logger.info("Wrote %d classifications to securities", len(asset_class_map))
            except Exception as ce:
                logger.warning("Classification step failed: %s", ce)

            # 2c. Fetch sector + industry from FMP company screener and persist to securities.
            #     Runs for all classifiable symbols in batches of 100.
            if settings.fmp_api_key:
                try:
                    screener_map: dict[str, dict] = {}
                    batch_size = 100
                    screener_syms = [t for t in ticker_list if "/" not in t and len(t) <= 8]
                    for i in range(0, len(screener_syms), batch_size):
                        batch = screener_syms[i: i + batch_size]
                        try:
                            r = await client.get(
                                f"{settings.fmp_base_url}/company-screener",
                                params={"symbol": ",".join(batch), "apikey": settings.fmp_api_key},
                                timeout=30,
                            )
                            if r.status_code == 200:
                                for item in r.json() or []:
                                    sym = (item.get("symbol") or "").upper()
                                    if sym:
                                        screener_map[sym] = {
                                            "sector":   item.get("sector"),
                                            "industry": item.get("industry"),
                                            "is_etf":   bool(item.get("isEtf", False)),
                                            "is_fund":  bool(item.get("isFund", False)),
                                        }
                        except Exception as be:
                            logger.warning("screener batch %d failed: %s", i, be)

                    if screener_map:
                        with _db().connect() as conn:
                            for sym, info in screener_map.items():
                                conn.execute(text("""
                                    UPDATE platform_shared.securities
                                    SET sector   = COALESCE(NULLIF(:sector, ''), sector),
                                        industry = COALESCE(NULLIF(:industry, ''), industry),
                                        updated_at = NOW()
                                    WHERE symbol = :sym
                                """), {
                                    "sym":      sym,
                                    "sector":   info.get("sector") or "",
                                    "industry": info.get("industry") or "",
                                })
                            conn.commit()
                        logger.info("Wrote sector/industry for %d symbols from FMP screener", len(screener_map))
                except Exception as se:
                    logger.warning("Sector/industry screener step failed: %s", se)

        # 3. Score symbols in background — fire-and-forget to avoid 4-min timeout on 70+ tickers.
        #    Scoring stores income_scores; does not affect portfolio total_value calculation.
        #    Pass asset_class from classification so agent-03 doesn't re-classify as UNKNOWN.
        async def _score_background(tickers: list, hdrs: dict, ac_map: dict):
            sem = asyncio.Semaphore(5)

            async def _score_one(sym: str):
                async with sem:
                    try:
                        payload: dict = {"ticker": sym, "gate_data": {}}
                        ac = ac_map.get(sym)
                        if ac and ac.upper() != "UNKNOWN":
                            payload["asset_class"] = ac.upper()
                        async with httpx.AsyncClient(timeout=30) as c:
                            r = await c.post(
                                f"{settings.agent03_url}/scores/evaluate",
                                headers=hdrs,
                                json=payload,
                            )
                            if r.status_code >= 400:
                                logger.warning("score %s → %d: %s", sym, r.status_code, r.text[:200])
                    except Exception as ex:
                        logger.warning("score_one %s failed: %s", sym, ex)

            await asyncio.gather(*[_score_one(s) for s in tickers])

        asyncio.create_task(_score_background(ticker_list, headers, asset_class_map))
        scored = len(ticker_list)  # all queued for background scoring

        # 4. Sync positions from market_data_cache: price → value → income → yield → frequency.
        prices_updated = 0
        with _db().connect() as conn:
            # 4a. Update current_price for all positions with market data (even quantity=0)
            result = conn.execute(text("""
                UPDATE platform_shared.positions p
                SET current_price = c.price,
                    updated_at    = NOW()
                FROM platform_shared.market_data_cache c
                WHERE p.symbol        = c.symbol
                  AND p.portfolio_id  = :pid
                  AND p.status        = 'ACTIVE'
                  AND c.price         IS NOT NULL
                  AND c.price         > 0
            """), {"pid": portfolio_id})
            prices_updated = result.rowcount if hasattr(result, 'rowcount') else 0

            # 4b. Update current_value = quantity × current_price
            conn.execute(text("""
                UPDATE platform_shared.positions p
                SET current_value = ROUND((p.quantity * p.current_price)::numeric, 2)
                WHERE p.portfolio_id = :pid
                  AND p.status       = 'ACTIVE'
                  AND p.quantity     > 0
                  AND p.current_price > 0
            """), {"pid": portfolio_id})

            # 4c. Compute annual_income = quantity × price × (dividend_yield / 100)
            #     Only overwrite when cache has a real dividend_yield for this symbol.
            conn.execute(text("""
                UPDATE platform_shared.positions p
                SET annual_income = ROUND(
                        (p.quantity * c.price * c.dividend_yield / 100.0)::numeric, 2),
                    updated_at    = NOW()
                FROM platform_shared.market_data_cache c
                WHERE p.symbol       = c.symbol
                  AND p.portfolio_id = :pid
                  AND p.status       = 'ACTIVE'
                  AND c.dividend_yield > 0
                  AND c.price         > 0
                  AND p.quantity      > 0
            """), {"pid": portfolio_id})

            # 4d. Recompute yield_on_cost = annual_income / total_cost_basis
            conn.execute(text("""
                UPDATE platform_shared.positions p
                SET yield_on_cost = ROUND(
                        (p.annual_income / NULLIF(p.total_cost_basis, 0))::numeric, 6)
                WHERE p.portfolio_id = :pid
                  AND p.status       = 'ACTIVE'
                  AND p.annual_income > 0
                  AND p.total_cost_basis > 0
            """), {"pid": portfolio_id})

            # 4e. Set dividend_frequency from asset class heuristic (only when blank/null)
            if asset_class_map:
                for sym, ac in asset_class_map.items():
                    freq = _FREQ_BY_CLASS.get(ac.upper(), "Quarterly")
                    conn.execute(text("""
                        UPDATE platform_shared.positions
                        SET dividend_frequency = :freq, updated_at = NOW()
                        WHERE symbol       = :sym
                          AND portfolio_id = :pid
                          AND status       = 'ACTIVE'
                    """), {"freq": freq, "sym": sym, "pid": portfolio_id})
                    # Mirror to securities so future positions inherit the right value
                    conn.execute(text("""
                        UPDATE platform_shared.securities
                        SET dividend_frequency = :freq, updated_at = NOW()
                        WHERE symbol = :sym
                    """), {"freq": freq, "sym": sym})

            # 4f. Recalculate portfolio total_value
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0)
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ),
                last_refreshed_at = NOW(),
                updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.commit()

        import datetime as _dt
        return JSONResponse(content={
            "status": "ok",
            "symbols": ticker_list,
            "total": len(ticker_list),
            "cache_refreshed": cache_refreshed,
            "prices_updated": prices_updated,
            "scored": scored,
            "score_errors": [],
            "scoring": "background",
            "refreshed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("refresh_portfolio_data error (%s): %s", portfolio_id, exc)
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
        "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS sector VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE platform_shared.securities ADD COLUMN IF NOT EXISTS industry VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE platform_shared.portfolios ADD COLUMN IF NOT EXISTS last_refreshed_at TIMESTAMPTZ DEFAULT NULL",
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

    # Optional market intelligence fields — coerce to float or None
    for k in ("daily_change_pct", "week52_high", "week52_low", "market_cap",
              "pe_ratio", "payout_ratio", "beta", "chowder_number",
              "nav_value", "nav_discount_pct"):
        v = pos.get(k)
        pos[k] = float(v) if v is not None else None
    for k in ("ex_div_date", "pay_date"):
        v = pos.get(k)
        if v and hasattr(v, "isoformat"):
            pos[k] = v.isoformat()
        elif not v:
            pos[k] = None
    avg_vol = pos.get("avg_volume")
    pos["avg_volume"] = int(avg_vol) if avg_vol is not None else None
    # Derive dividend_growth_5y from chowder_number - dividend_yield
    chowder = pos.get("chowder_number")
    cy = pos.get("current_yield")
    pos["dividend_growth_5y"] = round(float(chowder) - float(cy), 2) if chowder and cy else None
    # EPS from price / PE
    price = pos.get("market_price") or 0
    pe = pos.get("pe_ratio")
    pos["eps"] = round(price / pe, 2) if pe and pe != 0 and price else None

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
                    COALESCE(s.industry, '')             AS industry,
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


# ── Create / bulk-upsert positions ────────────────────────────────────────────

class PositionUpsertItem(BaseModel):
    symbol: str
    name: str = ""
    asset_type: str = ""           # left blank — classification fills it in during refresh
    shares: float = 0
    cost_basis: float = 0          # total cost basis (shares × avg_cost)
    current_value: float = 0
    annual_income: float = 0
    yield_on_cost: float = 0       # percentage, e.g. 5.0 for 5%
    sector: str = ""
    dividend_frequency: str = ""   # left blank — derived from asset class during refresh


def _upsert_position(conn, portfolio_id: str, item: PositionUpsertItem) -> str:
    """Upsert one position row; returns the position id."""
    sym = item.symbol.strip().upper()
    avg_cb = round(item.cost_basis / item.shares, 6) if item.shares else 0.0
    cur_price = round(item.current_value / item.shares, 4) if item.shares else avg_cb
    yoc_fraction = item.yield_on_cost / 100.0

    # Ensure security record exists — NULLIF('', '') so empty strings don't overwrite existing data
    conn.execute(text("""
        INSERT INTO platform_shared.securities
            (symbol, name, asset_type, is_active, created_at, updated_at)
        VALUES (:sym, :name, NULLIF(:at, ''), TRUE, NOW(), NOW())
        ON CONFLICT (symbol) DO UPDATE SET
            name       = COALESCE(NULLIF(EXCLUDED.name, ''), platform_shared.securities.name),
            asset_type = COALESCE(NULLIF(EXCLUDED.asset_type, ''), platform_shared.securities.asset_type),
            updated_at = NOW()
    """), {"sym": sym, "name": item.name or sym, "at": item.asset_type})

    # Check if a position already exists (ON CONFLICT on portfolio_id + symbol + status)
    existing = conn.execute(text("""
        SELECT id FROM platform_shared.positions
        WHERE portfolio_id = :pid AND symbol = :sym AND status = 'ACTIVE'
        LIMIT 1
    """), {"pid": portfolio_id, "sym": sym}).fetchone()

    pos_id = str(existing[0]) if existing else str(uuid4())

    conn.execute(text("""
        INSERT INTO platform_shared.positions
            (id, portfolio_id, symbol, status, quantity, avg_cost_basis, total_cost_basis,
             current_price, current_value, annual_income, yield_on_cost,
             dividend_frequency, sector, created_at, updated_at)
        VALUES
            (:id, :pid, :sym, 'ACTIVE', :qty, :avg_cb, :total_cb,
             :cur_price, :cur_val, :annual_income, :yoc,
             :freq, :sector, NOW(), NOW())
        ON CONFLICT (portfolio_id, symbol, status) DO UPDATE SET
            quantity         = EXCLUDED.quantity,
            avg_cost_basis   = EXCLUDED.avg_cost_basis,
            total_cost_basis = EXCLUDED.total_cost_basis,
            current_price    = EXCLUDED.current_price,
            current_value    = EXCLUDED.current_value,
            annual_income    = EXCLUDED.annual_income,
            yield_on_cost    = EXCLUDED.yield_on_cost,
            dividend_frequency = COALESCE(NULLIF(EXCLUDED.dividend_frequency, ''), platform_shared.positions.dividend_frequency),
            sector           = COALESCE(NULLIF(EXCLUDED.sector, ''), platform_shared.positions.sector),
            updated_at       = NOW()
    """), {
        "id": pos_id,
        "pid": portfolio_id,
        "sym": sym,
        "qty": item.shares,
        "avg_cb": avg_cb,
        "total_cb": item.cost_basis,
        "cur_price": cur_price,
        "cur_val": item.current_value or item.cost_basis,
        "annual_income": item.annual_income,
        "yoc": yoc_fraction,
        "freq": item.dividend_frequency or None,
        "sector": item.sector,
    })
    return pos_id


@router.post("/portfolios/{portfolio_id}/positions")
def create_position(portfolio_id: str, item: PositionUpsertItem):
    """Create or update a single position in a portfolio."""
    try:
        with _db().connect() as conn:
            _ensure_freq_column(conn)
            pos_id = _upsert_position(conn, portfolio_id, item)
            # Recalculate portfolio total_value
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0)
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ), updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.commit()
        return JSONResponse(content={"id": pos_id, "status": "ok"})
    except Exception as exc:
        logger.error("create_position error (%s): %s", portfolio_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


from typing import List as _List  # noqa: E402

@router.post("/portfolios/{portfolio_id}/positions/bulk")
def bulk_create_positions(portfolio_id: str, items: _List[PositionUpsertItem]):
    """Upsert a batch of positions for a portfolio (CSV upload path)."""
    if not items:
        return JSONResponse(content={"upserted": 0})
    try:
        with _db().connect() as conn:
            _ensure_freq_column(conn)
            count = 0
            for item in items:
                if not item.symbol.strip():
                    continue
                _upsert_position(conn, portfolio_id, item)
                count += 1
            # Recalculate portfolio total_value
            conn.execute(text("""
                UPDATE platform_shared.portfolios
                SET total_value = (
                    SELECT COALESCE(SUM(current_value), 0)
                    FROM platform_shared.positions
                    WHERE portfolio_id = :pid AND status = 'ACTIVE'
                ), updated_at = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id})
            conn.commit()
        return JSONResponse(content={"upserted": count, "status": "ok"})
    except Exception as exc:
        logger.error("bulk_create_positions error (%s): %s", portfolio_id, exc)
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
                    COALESCE(s.industry, '')             AS industry,
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
                    p.updated_at,
                    -- Market intelligence from cache
                    m.price_change_pct           AS daily_change_pct,
                    m.week52_high,
                    m.week52_low,
                    m.market_cap_m               AS market_cap,
                    m.pe_ratio,
                    m.payout_ratio,
                    m.beta,
                    m.chowder_number,
                    m.nav_value,
                    m.nav_discount_pct,
                    m.ex_div_date,
                    m.pay_date,
                    m.volume_avg_10d             AS avg_volume
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
    asset_type: Optional[str] = None             # updates securities.asset_type
    sector: Optional[str] = None                 # updates securities.sector
    industry: Optional[str] = None               # updates securities.industry
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

            # Update asset_type, sector, industry, and/or dividend_frequency in securities if provided
            if any(v is not None for v in [update.asset_type, update.sector, update.industry, update.dividend_frequency]):
                conn.execute(text("""
                    UPDATE platform_shared.securities
                    SET asset_type         = COALESCE(NULLIF(:asset_type, ''), asset_type),
                        sector             = COALESCE(:sector, sector),
                        industry           = COALESCE(NULLIF(:industry, ''), industry),
                        dividend_frequency = COALESCE(:freq, dividend_frequency),
                        updated_at         = NOW()
                    WHERE symbol = :sym
                """), {
                    "asset_type": update.asset_type, "sector": update.sector,
                    "industry": update.industry, "freq": update.dividend_frequency, "sym": sym,
                })

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
def get_market_data_for_positions(portfolio_id: Optional[str] = None):
    """
    Return market data for symbols held in a specific portfolio (or all portfolios).
    Uses positions as the base set so ALL held symbols appear — even those not
    yet in market_data_cache. Cache data is merged where available.
    """
    try:
        with _db().connect() as conn:
            portfolio_filter = "AND portfolio_id = :pid" if portfolio_id else ""
            rows = conn.execute(text(f"""
                WITH pos_agg AS (
                    SELECT symbol,
                           SUM(current_value)  AS current_value,
                           SUM(annual_income)  AS annual_income
                    FROM platform_shared.positions
                    WHERE status = 'ACTIVE' {portfolio_filter}
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
                    m.pay_date,
                    m.div_frequency,
                    m.volume_avg_10d                     AS avg_volume,
                    COALESCE(m.snapshot_date, p.price_updated_at::date) AS snapshot_date
                FROM (
                    SELECT DISTINCT ON (symbol)
                        symbol, current_price, price_updated_at
                    FROM platform_shared.positions
                    WHERE status = 'ACTIVE' {portfolio_filter}
                    ORDER BY symbol, current_value DESC NULLS LAST
                ) p
                LEFT JOIN platform_shared.market_data_cache m ON m.symbol = p.symbol
                LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
                LEFT JOIN pos_agg pa ON pa.symbol = p.symbol
                ORDER BY p.symbol
            """), {"pid": portfolio_id} if portfolio_id else {}).fetchall()

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
                pe = item.get("pe_ratio")
                item["eps"] = round(price / pe, 2) if pe and pe != 0 and price else None
                chowder = item.get("chowder_number")
                div_yield = item.get("dividend_yield")
                item["dividend_growth_5y"] = round(float(chowder) - float(div_yield), 2) if chowder and div_yield else None
                avg_vol = item.get("avg_volume")
                item["avg_volume"] = int(avg_vol) if avg_vol else None
                pay = item.get("pay_date")
                item["pay_date"] = pay.isoformat() if pay and hasattr(pay, "isoformat") else (str(pay) if pay else None)
                item["div_frequency"] = item.get("div_frequency")
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


# ── Direct market quote (price + yield from DB) ───────────────────────────────

@router.get("/market-data/quote/{symbol:path}")
def get_market_quote(symbol: str):
    """
    Return price, name, asset_type, dividend_yield for a symbol.
    Reads directly from market_data_cache + securities — no external API call.
    Used by the frontend scanner to populate proposal yield estimates.
    """
    try:
        with _db().connect() as conn:
            row = conn.execute(text("""
                SELECT
                    COALESCE(s.name, :sym)           AS name,
                    COALESCE(s.asset_type, 'Unknown') AS asset_type,
                    COALESCE(m.price, 0)             AS price,
                    COALESCE(m.dividend_yield, 0)    AS dividend_yield,
                    m.snapshot_date
                FROM (SELECT :sym::text AS symbol) base
                LEFT JOIN platform_shared.securities s ON UPPER(s.symbol) = UPPER(:sym)
                LEFT JOIN platform_shared.market_data_cache m ON UPPER(m.symbol) = UPPER(:sym)
                LIMIT 1
            """), {"sym": symbol.upper()}).fetchone()

            if row:
                item = dict(row._mapping)
                return JSONResponse(content={
                    "symbol": symbol.upper(),
                    "name": item.get("name") or symbol.upper(),
                    "asset_type": item.get("asset_type") or "Unknown",
                    "price": float(item.get("price") or 0),
                    "dividend_yield": float(item.get("dividend_yield") or 0),
                })
            return JSONResponse(content={
                "symbol": symbol.upper(),
                "name": symbol.upper(),
                "asset_type": "Unknown",
                "price": 0.0,
                "dividend_yield": 0.0,
            })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_market_quote error (%s): %s", symbol, exc)
        raise HTTPException(status_code=500, detail=str(exc))
