"""
Broker Service — API routes.

POST /broker/sync              Sync account info + positions from broker → DB
POST /broker/orders            Place an order at the broker
GET  /broker/orders/{id}       Get order status
DELETE /broker/orders/{id}     Cancel a pending order
GET  /broker/connection        Test broker connection + return account summary
GET  /broker/providers         List supported broker providers
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.providers.alpaca import AlpacaProvider
from app.providers.base import BaseBrokerProvider, OrderRequest
from app.services.portfolio_aggregator import aggregate_portfolio, fetch_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/broker")


# ── Provider registry ─────────────────────────────────────────────────────────

def _get_provider(broker: str) -> BaseBrokerProvider:
    """Instantiate the right provider for a given broker name."""
    broker = broker.lower()
    if broker == "alpaca":
        return AlpacaProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
        )
    raise HTTPException(status_code=422, detail=f"Unsupported broker: '{broker}'")


# ── Request / Response models ─────────────────────────────────────────────────

class CredentialsRequest(BaseModel):
    broker: str = "alpaca"
    api_key: str
    api_secret: str


class SyncRequest(BaseModel):
    broker: str = "alpaca"
    portfolio_id: Optional[str] = None   # if provided, link sync to this portfolio


class OrderPlaceRequest(BaseModel):
    broker: str = "alpaca"
    portfolio_id: str
    symbol: str
    side: str                           # buy | sell
    qty: float
    order_type: str = "market"          # market | limit | stop | stop_limit
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"
    proposal_id: Optional[str] = None   # link back to the originating proposal


class SyncFillRequest(BaseModel):
    portfolio_id: str
    ticker: str
    filled_qty: float
    avg_fill_price: float
    filled_at: str                      # ISO datetime — acquisition_date for new positions
    proposal_id: Optional[str] = None
    order_id: Optional[str] = None
    broker_ref: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    """Return supported broker providers and their configuration status."""
    return {
        "providers": [
            {
                "name": "alpaca",
                "label": "Alpaca Markets",
                "configured": bool(settings.alpaca_api_key and settings.alpaca_secret_key),
                "base_url": settings.alpaca_base_url,
                "mode": "paper" if "paper" in settings.alpaca_base_url else "live",
            },
            # Future: schwab, fidelity, interactive_brokers, ...
        ]
    }


# ── In-memory credentials override store ──────────────────────────────────────
# Keys are broker name (lowercase); values are (api_key, api_secret) tuples.
# These override env-configured values for the lifetime of the process.
_credentials_store: dict[str, tuple[str, str]] = {}


def _get_provider_with_override(broker: str) -> "BaseBrokerProvider":
    """Like _get_provider but checks the runtime credentials store first."""
    broker_lower = broker.lower()
    if broker_lower == "alpaca":
        override = _credentials_store.get("alpaca")
        api_key = override[0] if override else settings.alpaca_api_key
        secret_key = override[1] if override else settings.alpaca_secret_key
        return AlpacaProvider(
            api_key=api_key,
            secret_key=secret_key,
            base_url=settings.alpaca_base_url,
        )
    raise HTTPException(status_code=422, detail=f"Unsupported broker: '{broker}'")


@router.post("/credentials")
async def set_credentials(req: CredentialsRequest):
    """
    Accept broker credentials, test the connection, and store them in-memory
    if valid. Returns the account summary on success.
    """
    broker_lower = req.broker.lower()
    if broker_lower == "alpaca":
        provider = AlpacaProvider(
            api_key=req.api_key,
            secret_key=req.api_secret,
            base_url=settings.alpaca_base_url,
        )
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported broker: '{req.broker}'")

    status = await provider.test_connection()
    if not status.connected:
        raise HTTPException(
            status_code=400,
            detail=f"Credential test failed: {status.error or 'Could not connect to broker'}",
        )

    # Store credentials in memory for this process lifetime
    _credentials_store[broker_lower] = (req.api_key, req.api_secret)

    account = await provider.get_account()
    return {
        "ok": True,
        "broker": req.broker,
        "account_id": status.account_id,
        "account_label": status.account_label,
        "buying_power": account.buying_power,
        "cash_balance": account.cash_balance,
        "message": "Credentials validated and stored for this session.",
    }


@router.get("/connection")
async def test_connection(broker: str = "alpaca"):
    """Test broker connection and return live account summary."""
    provider = _get_provider_with_override(broker)
    status = await provider.test_connection()
    if not status.connected:
        raise HTTPException(status_code=502, detail=f"Broker connection failed: {status.error}")
    account = await provider.get_account()
    return {
        "connected": True,
        "broker": broker,
        "account_id": status.account_id,
        "account_label": status.account_label,
        "cash_balance": account.cash_balance,
        "buying_power": account.buying_power,
        "portfolio_value": account.portfolio_value,
        "currency": account.currency,
    }


@router.post("/sync")
async def sync_broker(req: SyncRequest, db: Session = Depends(get_db)):
    """
    Pull account info + all positions from the broker and upsert into
    platform_shared tables. Returns a summary of what was synced.

    DB writes:
      - platform_shared.accounts         → upsert with broker_account_id, cash balance
      - platform_shared.portfolios       → update cash_balance, total_value
      - platform_shared.securities       → upsert symbol + name (from position data)
      - platform_shared.positions        → upsert all open positions
      - platform_shared.market_data_cache → update current prices
    """
    provider = _get_provider_with_override(req.broker)

    # 1. Verify connection
    status = await provider.test_connection()
    if not status.connected:
        raise HTTPException(status_code=502, detail=f"Broker connection failed: {status.error}")

    # 2. Fetch account + positions
    account = await provider.get_account()
    positions = await provider.get_positions()

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # 3. Upsert account record
    db.execute(text("""
        INSERT INTO platform_shared.accounts
            (id, tenant_id, account_name, account_type, broker, broker_account_id,
             currency, is_active, created_at, updated_at)
        VALUES
            (:id, :tenant_id, :account_name, :account_type, :broker, :broker_account_id,
             :currency, TRUE, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            broker_account_id = EXCLUDED.broker_account_id,
            account_type      = EXCLUDED.account_type,
            updated_at        = NOW()
    """), {
        "id": _broker_account_uuid(req.broker, account.account_id),
        "tenant_id": _default_tenant(),
        "account_name": f"{req.broker.title()} — {account.account_label}",
        "account_type": account.account_type,
        "broker": req.broker,
        "broker_account_id": account.account_id,
        "currency": account.currency,
    })

    # 4. Resolve / upsert portfolio (link to account if portfolio_id provided)
    portfolio_id = req.portfolio_id or _resolve_or_create_portfolio(
        db, req.broker, account, today, now
    )

    # 5. Update portfolio cash + total value
    db.execute(text("""
        UPDATE platform_shared.portfolios
        SET cash_balance = :cash,
            total_value  = :total,
            updated_at   = NOW()
        WHERE id = :pid
    """), {
        "cash": account.cash_balance,
        "total": account.portfolio_value,
        "pid": portfolio_id,
    })

    # 6. Upsert positions
    upserted_positions = 0
    for pos in positions:
        # Ensure security record exists
        db.execute(text("""
            INSERT INTO platform_shared.securities (symbol, asset_type, is_active, created_at, updated_at)
            VALUES (:sym, :at, TRUE, NOW(), NOW())
            ON CONFLICT (symbol) DO UPDATE SET
                is_active = TRUE,
                updated_at = NOW(),
                asset_type = CASE
                    WHEN platform_shared.securities.asset_type IS NULL
                      OR platform_shared.securities.asset_type = 'UNKNOWN'
                    THEN EXCLUDED.asset_type
                    ELSE platform_shared.securities.asset_type
                END
        """), {"sym": pos.symbol, "at": pos.asset_type})

        annual_income = None  # will be populated by income-scoring service
        yield_on_cost = None
        if pos.avg_cost_basis and pos.avg_cost_basis > 0:
            # Attempt yield from market_data_cache
            row = db.execute(text(
                "SELECT dividend_yield FROM platform_shared.market_data_cache WHERE symbol = :s"
            ), {"s": pos.symbol}).fetchone()
            if row and row[0]:
                yield_pct = float(row[0]) / 100.0
                annual_income = round(pos.current_value * yield_pct, 2)
                total_cb = pos.avg_cost_basis * pos.quantity
                yield_on_cost = yield_pct if total_cb > 0 else None

        db.execute(text("""
            INSERT INTO platform_shared.positions
                (id, portfolio_id, symbol, status, quantity, avg_cost_basis, total_cost_basis,
                 current_price, current_value, price_updated_at, annual_income, yield_on_cost,
                 portfolio_weight_pct, created_at, updated_at)
            VALUES
                (:id, :pid, :sym, 'ACTIVE', :qty, :avg_cb, :total_cb,
                 :cur_price, :cur_val, NOW(), :annual_income, :yield_on_cost,
                 :weight_pct, NOW(), NOW())
            ON CONFLICT (portfolio_id, symbol, status) DO UPDATE SET
                quantity            = EXCLUDED.quantity,
                avg_cost_basis      = EXCLUDED.avg_cost_basis,
                total_cost_basis    = EXCLUDED.total_cost_basis,
                current_price       = EXCLUDED.current_price,
                current_value       = EXCLUDED.current_value,
                price_updated_at    = NOW(),
                annual_income       = COALESCE(EXCLUDED.annual_income, platform_shared.positions.annual_income),
                yield_on_cost       = COALESCE(EXCLUDED.yield_on_cost, platform_shared.positions.yield_on_cost),
                portfolio_weight_pct = EXCLUDED.portfolio_weight_pct,
                updated_at          = NOW()
        """), {
            "id": str(uuid4()),
            "pid": portfolio_id,
            "sym": pos.symbol,
            "qty": pos.quantity,
            "avg_cb": pos.avg_cost_basis,
            "total_cb": round(pos.avg_cost_basis * pos.quantity, 2),
            "cur_price": pos.current_price,
            "cur_val": pos.current_value,
            "annual_income": annual_income,
            "yield_on_cost": yield_on_cost,
            "weight_pct": round(
                (pos.current_value / account.portfolio_value * 100)
                if account.portfolio_value > 0 else 0, 3
            ),
        })

        # Update market_data_cache price
        db.execute(text("""
            INSERT INTO platform_shared.market_data_cache
                (symbol, price, snapshot_date, fetched_at, is_tracked, track_reason)
            VALUES (:sym, :price, :today, :now, TRUE, 'broker_sync')
            ON CONFLICT (symbol) DO UPDATE SET
                price         = EXCLUDED.price,
                snapshot_date = EXCLUDED.snapshot_date,
                fetched_at    = EXCLUDED.fetched_at
        """), {"sym": pos.symbol, "price": pos.current_price, "today": today, "now": now})

        upserted_positions += 1

    # 7. Mark positions NOT returned by broker as CLOSED.
    # Only do this for auto-resolved portfolios (no explicit portfolio_id in request).
    # If the user explicitly targeted a portfolio (e.g. a manual HDO portfolio),
    # we upsert broker positions into it without wiping the existing holdings.
    auto_resolved = req.portfolio_id is None
    if positions and auto_resolved:
        live_symbols = [p.symbol for p in positions]
        placeholders = ", ".join(f":s{i}" for i in range(len(live_symbols)))
        params = {f"s{i}": s for i, s in enumerate(live_symbols)}
        params["pid"] = portfolio_id
        db.execute(text(f"""
            UPDATE platform_shared.positions
            SET status = 'CLOSED', updated_at = NOW()
            WHERE portfolio_id = :pid
              AND status = 'ACTIVE'
              AND symbol NOT IN ({placeholders})
        """), params)

    db.commit()

    return {
        "synced": True,
        "broker": req.broker,
        "account_id": account.account_id,
        "portfolio_id": portfolio_id,
        "cash_balance": account.cash_balance,
        "buying_power": account.buying_power,
        "portfolio_value": account.portfolio_value,
        "positions_synced": upserted_positions,
        "synced_at": now,
    }


@router.post("/orders")
async def place_order(req: OrderPlaceRequest, db: Session = Depends(get_db)):
    """
    Submit an order to the broker and record the transaction in the DB.
    On success, returns the broker order ID and status.
    """
    provider = _get_provider(req.broker)

    order_req = OrderRequest(
        symbol=req.symbol.upper(),
        side=req.side.lower(),
        qty=req.qty,
        order_type=req.order_type.lower(),
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        time_in_force=req.time_in_force,
        client_order_id=f"plat-{req.proposal_id or uuid4().hex[:8]}",
    )

    try:
        result = await provider.place_order(order_req)
    except Exception as exc:
        logger.error("Order placement failed (%s %s): %s", req.side, req.symbol, exc)
        raise HTTPException(status_code=502, detail=f"Broker rejected order: {exc}")

    # Record in transactions table
    tx_type = "buy" if req.side.lower() == "buy" else "sell"
    price = result.filled_avg_price or req.limit_price or 0
    db.execute(text("""
        INSERT INTO platform_shared.transactions
            (id, portfolio_id, symbol, transaction_type, quantity, price,
             total_amount, transaction_date, source, external_ref, created_at)
        VALUES
            (:id, :pid, :sym, :ttype, :qty, :price,
             :total, :tdate, :source, :ext_ref, NOW())
    """), {
        "id": str(uuid4()),
        "pid": req.portfolio_id,
        "sym": req.symbol.upper(),
        "ttype": tx_type,
        "qty": req.qty,
        "price": price,
        "total": round(req.qty * price, 2) if price else None,
        "tdate": date.today().isoformat(),
        "source": req.broker.lower(),
        "ext_ref": result.order_id,
    })
    db.commit()

    return {
        "order_id": result.order_id,
        "client_order_id": result.client_order_id,
        "symbol": result.symbol,
        "side": result.side,
        "qty": result.qty,
        "order_type": result.order_type,
        "status": result.status,
        "filled_qty": result.filled_qty,
        "filled_avg_price": result.filled_avg_price,
        "limit_price": result.limit_price,
        "submitted_at": result.submitted_at,
        "broker": req.broker,
    }


@router.get("/orders/{order_id}")
async def get_order(order_id: str, broker: str = "alpaca"):
    """Get current status of an order from the broker."""
    provider = _get_provider(broker)
    try:
        result = await provider.get_order(order_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "order_id": result.order_id,
        "symbol": result.symbol,
        "side": result.side,
        "qty": result.qty,
        "status": result.status,
        "filled_qty": result.filled_qty,
        "filled_avg_price": result.filled_avg_price,
        "submitted_at": result.submitted_at,
        "filled_at": result.filled_at,
        "broker": broker,
    }


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, broker: str = "alpaca"):
    """Cancel a pending order."""
    provider = _get_provider(broker)
    try:
        cancelled = await provider.cancel_order(order_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"cancelled": cancelled, "order_id": order_id, "broker": broker}


@router.post("/portfolios/{portfolio_id}/refresh")
async def refresh_portfolio_data(portfolio_id: str, db: Session = Depends(get_db)):
    """Sequential data refresh: market data → classification → scoring → stamp last_refreshed_at."""
    row = db.execute(text("SELECT id FROM platform_shared.portfolios WHERE id = :id"), {"id": portfolio_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    ticker_rows = db.execute(text("""
        SELECT DISTINCT symbol FROM platform_shared.positions
        WHERE portfolio_id = :pid AND status = 'ACTIVE' ORDER BY symbol
    """), {"pid": portfolio_id}).fetchall()
    tickers = [r[0] for r in ticker_rows]

    hdrs = {"Authorization": f"Bearer {settings.service_token}"} if settings.service_token else {}
    steps: dict = {}

    async def _post(url: str, payload=None, timeout: int = 120) -> dict:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=hdrs, json=payload)
            ok = resp.status_code < 300
            try:
                return {"ok": ok, "status": resp.status_code, "data": resp.json()}
            except Exception:
                return {"ok": ok, "status": resp.status_code}
        except httpx.TimeoutException:
            return {"ok": False, "status": 504, "error": "timed out"}
        except Exception as exc:
            return {"ok": False, "status": 502, "error": str(exc)}

    # Do NOT force=true — that re-fetches all tickers from FMP every click (~500 API calls).
    # The daily scheduler owns the full force-refresh. On-demand refresh only fetches
    # tickers whose cache entry is stale/missing (today's date not yet set).
    steps["market_data"] = await _post(f"{settings.scanner_url}/cache/refresh", timeout=180)
    # Propagate fresh prices from market_data_cache → positions.current_price / price_updated_at
    try:
        price_rows = db.execute(text("""
            UPDATE platform_shared.positions p
            SET current_price    = c.price,
                current_value    = ROUND((p.quantity * c.price)::numeric, 2),
                price_updated_at = NOW(),
                updated_at       = NOW()
            FROM platform_shared.market_data_cache c
            WHERE p.symbol       = c.symbol
              AND p.portfolio_id = :pid
              AND p.status       = 'ACTIVE'
              AND c.price        IS NOT NULL
              AND c.price        > 0
        """), {"pid": portfolio_id})
        db.execute(text("""
            UPDATE platform_shared.portfolios
            SET total_value = (
                SELECT COALESCE(SUM(current_value), 0) + COALESCE(cash_balance, 0)
                FROM platform_shared.positions
                WHERE portfolio_id = :pid AND status = 'ACTIVE'
            ), updated_at = NOW()
            WHERE id = :pid
        """), {"pid": portfolio_id})
        db.commit()
        steps["price_sync"] = {"ok": True, "prices_updated": price_rows.rowcount}
    except Exception as exc:
        steps["price_sync"] = {"ok": False, "error": str(exc)}
    steps["classification"] = await _post(
        f"{settings.classification_url}/classify/batch",
        payload={"tickers": tickers},
    ) if tickers else {"ok": True, "data": {"skipped": "no tickers"}}
    steps["scoring"] = await _post(f"{settings.scoring_service_url}/scores/refresh-portfolio")

    # Portfolio health score: value-weighted average HHS from income_scores
    try:
        ph_row = db.execute(text("""
            WITH latest_scores AS (
                SELECT DISTINCT ON (ticker) ticker, hhs_score, unsafe_flag
                FROM platform_shared.income_scores
                ORDER BY ticker, scored_at DESC
            )
            SELECT
                SUM(p.current_value * ls.hhs_score) / NULLIF(SUM(p.current_value), 0) AS agg_hhs,
                SUM(p.current_value)                                                    AS total_val,
                SUM(p.annual_income)                                                    AS total_income,
                COUNT(p.id)                                                             AS pos_count,
                COUNT(CASE WHEN ls.unsafe_flag THEN 1 END)                             AS unsafe_count,
                ARRAY_AGG(CASE WHEN ls.unsafe_flag THEN p.symbol END)
                    FILTER (WHERE ls.unsafe_flag)                                       AS unsafe_tickers
            FROM platform_shared.positions p
            JOIN latest_scores ls ON ls.ticker = p.symbol
            WHERE p.portfolio_id = :pid AND p.status = 'ACTIVE'
              AND p.current_value > 0 AND ls.hhs_score IS NOT NULL
        """), {"pid": portfolio_id}).fetchone()

        if ph_row and ph_row[0] is not None:
            score = round(float(ph_row[0]), 2)
            total_val = float(ph_row[1] or 0)
            total_inc = float(ph_row[2] or 0)
            pos_count = int(ph_row[3] or 0)
            unsafe_count = int(ph_row[4] or 0)
            unsafe_tickers = [t for t in (ph_row[5] or []) if t]
            yield_pct = round((total_inc / total_val * 100), 4) if total_val > 0 else 0
            grade = ("A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60
                     else "D" if score >= 50 else "F")
            flags = unsafe_tickers
            db.execute(text("""
                INSERT INTO platform_shared.portfolio_health_scores
                    (id, portfolio_id, computed_at, score, grade,
                     flags, position_count, total_value, actual_yield_pct, created_at)
                VALUES
                    (gen_random_uuid(), :pid, NOW(), :score, :grade,
                     :flags, :pos_count, :total_value, :yield_pct, NOW())
            """), {
                "pid": portfolio_id, "score": score, "grade": grade,
                "flags": flags, "pos_count": pos_count,
                "total_value": total_val, "yield_pct": yield_pct,
            })
            db.execute(text("""
                UPDATE platform_shared.portfolios
                SET health_score             = :score,
                    health_score_computed_at = NOW(),
                    updated_at               = NOW()
                WHERE id = :pid
            """), {"pid": portfolio_id, "score": score})
            steps["portfolio_health"] = {
                "ok": True,
                "aggregate_hhs": score,
                "grade": grade,
                "scored_positions": pos_count,
                "unsafe_count": unsafe_count,
            }
        else:
            steps["portfolio_health"] = {"ok": True, "aggregate_hhs": None,
                                          "note": "no scored positions with value"}
    except Exception as exc:
        steps["portfolio_health"] = {"ok": False, "error": str(exc)}

    if any(v["ok"] for v in steps.values()):
        db.execute(text("UPDATE platform_shared.portfolios SET last_refreshed_at = NOW(), updated_at = NOW() WHERE id = :pid"), {"pid": portfolio_id})
        db.commit()

    return {"ok": all(v["ok"] for v in steps.values()), "portfolio_id": portfolio_id, "tickers_count": len(tickers), "steps": steps}


async def _fetch_tax_prefs() -> dict | None:
    """Fetch user tax preferences from admin panel. Returns None on failure."""
    try:
        hdrs = {"Authorization": f"Bearer {settings.service_token}"} if settings.service_token else {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.admin_panel_url}/api/user/preferences",
                headers=hdrs,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data
    except Exception as exc:
        logger.warning("Could not fetch tax prefs from admin panel: %s", exc)
    return None


@router.get("/portfolios")
async def list_portfolios(db: Session = Depends(get_db)):
    """List all portfolios with aggregate KPIs."""
    rows = db.execute(text("""
        SELECT p.id, p.portfolio_name AS name, a.account_type AS tax_status, a.broker,
               COUNT(pos.id) AS holding_count, p.last_refreshed_at,
               p.cash_balance,
               SUM(pos.current_value) AS total_value,
               SUM(pos.annual_income) AS annual_income
        FROM platform_shared.portfolios p
        LEFT JOIN platform_shared.accounts a ON a.id = p.account_id
        LEFT JOIN platform_shared.positions pos ON pos.portfolio_id = p.id AND pos.status = 'ACTIVE'
        GROUP BY p.id, p.portfolio_name, a.account_type, a.broker, p.last_refreshed_at, p.cash_balance
        ORDER BY p.portfolio_name
    """)).mappings().all()

    tax_prefs = await _fetch_tax_prefs()
    results = []
    for row in rows:
        # Fetch positions for this portfolio
        positions = _get_positions_for_portfolio(db, str(row["id"]))
        # Read scores directly from DB (bypasses HTTP + staleness issues)
        scores = _get_scores_from_db(db, str(row["id"]))
        agg = await aggregate_portfolio(str(row["id"]), positions, scores, tax_prefs=tax_prefs, service_token=settings.service_token)
        results.append({
            "id": str(row["id"]),
            "name": row["name"],
            "tax_status": row["tax_status"],
            "broker": row["broker"],
            "cash_balance": float(row["cash_balance"]) if row["cash_balance"] is not None else None,
            "last_refresh": row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
            **agg,
        })
    return results


@router.get("/portfolios/{portfolio_id}/summary")
async def portfolio_summary(portfolio_id: str, db: Session = Depends(get_db)):
    """Full portfolio summary for the portfolio page."""
    row = db.execute(text("""
        SELECT p.id, p.portfolio_name AS name, a.account_type AS tax_status, a.broker,
               p.last_refreshed_at, p.cash_balance,
               (SELECT MAX(mdc.snapshot_date)
                FROM platform_shared.market_data_cache mdc
                JOIN platform_shared.positions pos ON pos.symbol = mdc.symbol
                WHERE pos.portfolio_id = p.id AND pos.status = 'ACTIVE') AS market_data_date
        FROM platform_shared.portfolios p
        LEFT JOIN platform_shared.accounts a ON a.id = p.account_id
        WHERE p.id = :id
        LIMIT 1
    """), {"id": portfolio_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    positions = _get_positions_for_portfolio(db, portfolio_id)
    scores = _get_scores_from_db(db, portfolio_id)
    tax_prefs = await _fetch_tax_prefs()
    agg = await aggregate_portfolio(portfolio_id, positions, scores, tax_prefs=tax_prefs, service_token=settings.service_token)

    market_data_date = row["market_data_date"]
    last_refreshed_at = row["last_refreshed_at"]

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "tax_status": row["tax_status"],
        "broker": row["broker"],
        "cash_balance": float(row["cash_balance"]) if row["cash_balance"] is not None else None,
        "last_refresh": (market_data_date.isoformat() if market_data_date
                         else (last_refreshed_at.isoformat() if last_refreshed_at else None)),
        **agg,
        "scores_unavailable": not scores,
    }


def _get_positions_for_portfolio(db: Session, portfolio_id: str) -> list[dict]:
    rows = db.execute(text("""
        SELECT pos.symbol, pos.current_value, pos.annual_income,
               pos.total_cost_basis AS cost_basis,
               pos.total_dividends_received,
               COALESCE(pos.annual_fee_drag, 0)    AS annual_fee_drag,
               COALESCE(pos.net_annual_income, pos.annual_income, 0) AS net_annual_income,
               COALESCE(sec.management_fee, 0)     AS management_fee,
               COALESCE(sec.tax_qualified_pct, 100) AS tax_qualified_pct,
               COALESCE(sec.tax_ordinary_pct,  0)   AS tax_ordinary_pct,
               sec.asset_type,
               COALESCE(
                   NULLIF(pos.sector, ''),
                   NULLIF(mdc.fmp_sector, ''),
                   CASE WHEN sec.asset_type = 'BOND' THEN 'Fixed Income' END
               ) AS sector,
               sec.industry
        FROM platform_shared.positions pos
        LEFT JOIN platform_shared.securities sec ON sec.symbol = pos.symbol
        LEFT JOIN platform_shared.market_data_cache mdc ON mdc.symbol = pos.symbol
        WHERE pos.portfolio_id = :pid
          AND pos.status = 'ACTIVE'
    """), {"pid": portfolio_id}).mappings().all()
    return [dict(r) for r in rows]


def _get_scores_from_db(db: Session, portfolio_id: str) -> dict[str, dict]:
    """Read latest HHS scores from income_scores table directly (no TTL/staleness)."""
    rows = db.execute(text("""
        SELECT DISTINCT ON (pos.symbol)
            pos.symbol,
            sc.hhs_score,
            sc.hhs_status,
            sc.unsafe_flag,
            sc.quality_gate_status,
            sc.income_pillar_score,
            sc.durability_pillar_score,
            sc.ies_score,
            sc.ies_calculated,
            sc.asset_class
        FROM platform_shared.positions pos
        LEFT JOIN platform_shared.income_scores sc ON sc.ticker = pos.symbol
        WHERE pos.portfolio_id = :pid
          AND pos.status = 'ACTIVE'
        ORDER BY pos.symbol, sc.scored_at DESC NULLS LAST
    """), {"pid": portfolio_id}).mappings().all()

    result = {}
    for row in rows:
        if row["hhs_score"] is not None:
            result[row["symbol"]] = {
                "hhs_score": row["hhs_score"],
                "hhs_status": row["hhs_status"],
                "unsafe_flag": row["unsafe_flag"],
                "quality_gate_status": row["quality_gate_status"],
                "income_pillar_score": row["income_pillar_score"],
                "durability_pillar_score": row["durability_pillar_score"],
                "ies_score": row["ies_score"],
                "ies_calculated": row["ies_calculated"],
                "asset_class": row["asset_class"],
                # No valid_until → _is_stale() returns False (treated as always fresh)
            }
    return result


async def _fetch_scores_for_positions(positions: list[dict]) -> dict[str, dict]:
    """Fetch scores concurrently from Agent 03 for all unique tickers."""
    tickers = list({p["symbol"] for p in positions if p.get("symbol")})
    if not tickers:
        return {}
    tasks = [fetch_score(t, settings.scoring_service_url, settings.service_token) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {t: r for t, r in zip(tickers, results) if isinstance(r, dict)}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _default_tenant() -> str:
    return "00000000-0000-0000-0000-000000000001"


def _broker_account_uuid(broker: str, account_id: str) -> str:
    """Deterministic UUID-like ID for a broker account (namespace by broker+id)."""
    import hashlib
    raw = f"{broker}:{account_id}"
    h = hashlib.md5(raw.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _resolve_or_create_portfolio(
    db: Session, broker: str, account, today: str, now: str
) -> str:
    """Find an existing portfolio linked to this broker account, or create one."""
    account_uuid = _broker_account_uuid(broker, account.account_id)

    # Look for an existing portfolio linked to this account
    row = db.execute(text("""
        SELECT p.id FROM platform_shared.portfolios p
        JOIN platform_shared.accounts a ON a.id = p.account_id
        WHERE a.broker = :broker AND a.broker_account_id = :acct_id
          AND p.status = 'ACTIVE'
        LIMIT 1
    """), {"broker": broker, "acct_id": account.account_id}).fetchone()

    if row:
        return str(row[0])

    # Create a new portfolio for this broker account
    pid = str(uuid4())
    portfolio_name = f"{broker.title()} — {account.account_label}"
    db.execute(text("""
        INSERT INTO platform_shared.portfolios
            (id, tenant_id, account_id, portfolio_name, status,
             cash_balance, total_value, created_at, updated_at)
        VALUES
            (:id, :tid, :acct_id, :name, 'ACTIVE',
             :cash, :total, NOW(), NOW())
        ON CONFLICT DO NOTHING
    """), {
        "id": pid,
        "tid": _default_tenant(),
        "acct_id": account_uuid,
        "name": portfolio_name,
        "cash": account.cash_balance,
        "total": account.portfolio_value,
    })
    return pid


# ── Sync-fill endpoint ─────────────────────────────────────────────────────────

@router.post("/positions/sync-fill")
def sync_fill(req: SyncFillRequest, db: Session = Depends(get_db)):
    """Upsert a position after a confirmed broker fill.

    For new positions: inserts with req.filled_qty, req.avg_fill_price.
    For existing positions: adds shares and recomputes weighted-average cost basis
    atomically in SQL to prevent race conditions from concurrent fill events.
    """
    # Check if position already exists (for is_new_position flag in response)
    existing = db.execute(text("""
        SELECT quantity, avg_cost_basis
        FROM platform_shared.positions
        WHERE portfolio_id = :pid AND symbol = :sym AND status = 'ACTIVE'
        LIMIT 1
    """), {"pid": req.portfolio_id, "sym": req.ticker.upper()}).fetchone()

    is_new = existing is None or not existing[0]

    # Atomic upsert: compute new weighted average in SQL to prevent race conditions
    db.execute(text("""
        INSERT INTO platform_shared.positions
            (id, portfolio_id, symbol, status, quantity, avg_cost_basis, total_cost_basis,
             created_at, updated_at)
        VALUES
            (:id, :pid, :sym, 'ACTIVE', :filled_qty, :avg_fill_price,
             :filled_qty * :avg_fill_price, NOW(), NOW())
        ON CONFLICT (portfolio_id, symbol, status)
        DO UPDATE SET
            quantity = platform_shared.positions.quantity + :filled_qty,
            avg_cost_basis = (
                platform_shared.positions.quantity * COALESCE(platform_shared.positions.avg_cost_basis, 0)
                + :filled_qty * :avg_fill_price
            ) / NULLIF(platform_shared.positions.quantity + :filled_qty, 0),
            total_cost_basis = (platform_shared.positions.quantity + :filled_qty) * (
                (
                    platform_shared.positions.quantity * COALESCE(platform_shared.positions.avg_cost_basis, 0)
                    + :filled_qty * :avg_fill_price
                ) / NULLIF(platform_shared.positions.quantity + :filled_qty, 0)
            ),
            updated_at = NOW()
    """), {
        "id": str(uuid4()),
        "pid": req.portfolio_id,
        "sym": req.ticker.upper(),
        "filled_qty": req.filled_qty,
        "avg_fill_price": req.avg_fill_price,
    })
    db.commit()

    # Read back the updated row for accurate response values
    updated = db.execute(text("""
        SELECT quantity, avg_cost_basis
        FROM platform_shared.positions
        WHERE portfolio_id = :pid AND symbol = :sym AND status = 'ACTIVE'
        LIMIT 1
    """), {"pid": req.portfolio_id, "sym": req.ticker.upper()}).fetchone()

    total_shares = float(updated[0]) if updated else req.filled_qty
    new_avg_cost = float(updated[1]) if updated and updated[1] else req.avg_fill_price

    return {
        "portfolio_id": req.portfolio_id,
        "ticker": req.ticker.upper(),
        "filled_qty": req.filled_qty,
        "avg_fill_price": req.avg_fill_price,
        "total_shares": total_shares,
        "new_avg_cost": round(new_avg_cost, 4),
        "is_new_position": is_new,
    }
