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


@router.get("/connection")
async def test_connection(broker: str = "alpaca"):
    """Test broker connection and return live account summary."""
    provider = _get_provider(broker)
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
    provider = _get_provider(req.broker)

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
            ON CONFLICT (symbol) DO NOTHING
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
        "source": req.broker,
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


@router.get("/portfolios")
async def list_portfolios(db: Session = Depends(get_db)):
    """List all portfolios with aggregate KPIs."""
    rows = db.execute(text("""
        SELECT p.id, p.portfolio_name AS name, a.account_type AS tax_status, a.broker,
               COUNT(pos.id) AS holding_count, p.last_refreshed_at,
               SUM(pos.current_value) AS total_value,
               SUM(pos.annual_income) AS annual_income
        FROM platform_shared.portfolios p
        LEFT JOIN platform_shared.accounts a ON a.id = p.account_id
        LEFT JOIN platform_shared.positions pos ON pos.portfolio_id = p.id
        GROUP BY p.id, p.portfolio_name, a.account_type, a.broker, p.last_refreshed_at
        ORDER BY p.portfolio_name
    """)).mappings().all()

    results = []
    for row in rows:
        # Fetch positions for this portfolio
        positions = _get_positions_for_portfolio(db, str(row["id"]))
        # Read scores directly from DB (bypasses HTTP + staleness issues)
        scores = _get_scores_from_db(db, str(row["id"]))
        agg = aggregate_portfolio(positions, scores)
        results.append({
            "id": str(row["id"]),
            "name": row["name"],
            "tax_status": row["tax_status"],
            "broker": row["broker"],
            "last_refresh": row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
            **agg,
        })
    return results


@router.get("/portfolios/{portfolio_id}/summary")
async def portfolio_summary(portfolio_id: str, db: Session = Depends(get_db)):
    """Full portfolio summary for the portfolio page."""
    row = db.execute(text("""
        SELECT p.id, p.portfolio_name AS name, a.account_type AS tax_status, a.broker,
               p.last_refreshed_at
        FROM platform_shared.portfolios p
        LEFT JOIN platform_shared.accounts a ON a.id = p.account_id
        WHERE p.id = :id
        LIMIT 1
    """), {"id": portfolio_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    positions = _get_positions_for_portfolio(db, portfolio_id)
    scores = _get_scores_from_db(db, portfolio_id)
    agg = aggregate_portfolio(positions, scores)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "tax_status": row["tax_status"],
        "broker": row["broker"],
        "last_refresh": row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
        **agg,
        "scores_unavailable": not scores,
    }


def _get_positions_for_portfolio(db: Session, portfolio_id: str) -> list[dict]:
    rows = db.execute(text("""
        SELECT pos.symbol, pos.current_value, pos.annual_income,
               pos.total_cost_basis AS cost_basis,
               pos.total_dividends_received,
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
    For existing positions: adds shares and recomputes weighted-average cost basis atomically.
    """
    # Read existing position row for (portfolio_id, ticker, status='ACTIVE')
    existing = db.execute(text("""
        SELECT quantity, avg_cost_basis
        FROM platform_shared.positions
        WHERE portfolio_id = :pid AND symbol = :sym AND status = 'ACTIVE'
        LIMIT 1
    """), {"pid": req.portfolio_id, "sym": req.ticker.upper()}).fetchone()

    if existing and existing[0]:
        old_qty = float(existing[0])
        old_cost = float(existing[1] or 0)
        new_qty = old_qty + req.filled_qty
        new_avg_cost = (old_qty * old_cost + req.filled_qty * req.avg_fill_price) / new_qty
        is_new = False
    else:
        new_qty = req.filled_qty
        new_avg_cost = req.avg_fill_price
        is_new = True

    db.execute(text("""
        INSERT INTO platform_shared.positions
            (id, portfolio_id, symbol, status, quantity, avg_cost_basis, total_cost_basis,
             created_at, updated_at)
        VALUES
            (:id, :pid, :sym, 'ACTIVE', :qty, :avg_cb, :total_cb, NOW(), NOW())
        ON CONFLICT (portfolio_id, symbol, status)
        DO UPDATE SET
            quantity         = :qty,
            avg_cost_basis   = :avg_cb,
            total_cost_basis = :total_cb,
            updated_at       = NOW()
    """), {
        "id": str(uuid4()),
        "pid": req.portfolio_id,
        "sym": req.ticker.upper(),
        "qty": new_qty,
        "avg_cb": round(new_avg_cost, 6),
        "total_cb": round(new_qty * new_avg_cost, 2),
    })
    db.commit()

    return {
        "portfolio_id": req.portfolio_id,
        "ticker": req.ticker.upper(),
        "filled_qty": req.filled_qty,
        "avg_fill_price": req.avg_fill_price,
        "total_shares": new_qty,
        "new_avg_cost": round(new_avg_cost, 4),
        "is_new_position": is_new,
    }
