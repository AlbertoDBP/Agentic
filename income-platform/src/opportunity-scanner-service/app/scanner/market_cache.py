"""
Agent 07 — Opportunity Scanner Service
Market Data Cache: batch-fetch FMP quotes/profiles, upsert to platform_shared.market_data_cache.

Flow:
  1. get_stale_tickers()   — split tickers into fresh (today) vs stale/missing
  2. fetch_and_upsert()    — batch-call FMP, upsert cache, mark is_tracked=True
  3. pre_filter_sql()      — SQL query against cache applying Group 2 criteria

FMP batch endpoints used:
  GET /quote?symbol=A,B,C&apikey=KEY   → price, volume, marketCap, pe, change%
  GET /profile?symbol=A,B,C&apikey=KEY → dividendYield, payoutRatio, beta, exchange
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(v)) if v is not None else None
    except (TypeError, ValueError):
        return None


# ─── FMP batch fetchers ───────────────────────────────────────────────────────

async def _fmp_get(path: str, params: dict) -> list[dict]:
    """Single FMP GET call; returns list or empty on error."""
    params["apikey"] = settings.fmp_api_key
    url = f"{settings.fmp_base_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=settings.fmp_request_timeout) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            logger.warning("FMP %s returned %d", path, resp.status_code)
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("FMP %s failed: %s", path, exc)
        return []


async def _batch_quotes(tickers: list[str]) -> dict[str, dict]:
    """Fetch FMP /quote for a batch of tickers. Returns {symbol: data}."""
    result: dict[str, dict] = {}
    for i in range(0, len(tickers), settings.fmp_batch_size):
        chunk = tickers[i : i + settings.fmp_batch_size]
        rows = await _fmp_get("/quote", {"symbol": ",".join(chunk)})
        for row in rows:
            sym = row.get("symbol", "").upper()
            if sym:
                result[sym] = row
    return result


async def _batch_profiles(tickers: list[str]) -> dict[str, dict]:
    """Fetch FMP /profile for a batch of tickers. Returns {symbol: data}."""
    result: dict[str, dict] = {}
    for i in range(0, len(tickers), settings.fmp_batch_size):
        chunk = tickers[i : i + settings.fmp_batch_size]
        rows = await _fmp_get("/profile", {"symbol": ",".join(chunk)})
        for row in rows:
            sym = row.get("symbol", "").upper()
            if sym:
                result[sym] = row
    return result


# ─── Cache operations ─────────────────────────────────────────────────────────

def get_stale_tickers(tickers: list[str], db: Session) -> tuple[list[str], list[str]]:
    """
    Split tickers into (fresh, stale).
    fresh = cached today; stale = missing or older than today.
    """
    if not tickers:
        return [], []
    today = date.today().isoformat()
    placeholders = ", ".join(f":t{i}" for i in range(len(tickers)))
    params = {f"t{i}": t.upper() for i, t in enumerate(tickers)}
    params["today"] = today
    rows = db.execute(
        text(
            f"SELECT symbol FROM platform_shared.market_data_cache "
            f"WHERE symbol IN ({placeholders}) AND snapshot_date = :today"
        ),
        params,
    ).fetchall()
    fresh_set = {r[0] for r in rows}
    upper = [t.upper() for t in tickers]
    fresh = [t for t in upper if t in fresh_set]
    stale = [t for t in upper if t not in fresh_set]
    return fresh, stale


async def fetch_and_upsert(
    tickers: list[str],
    db: Session,
    track_reason: str = "scan",
) -> int:
    """
    Batch-fetch FMP data for tickers and upsert into market_data_cache.
    Returns count of rows upserted.
    """
    if not tickers:
        return 0

    quotes, profiles = await _batch_quotes(tickers), await _batch_profiles(tickers)

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    upserted = 0

    for symbol in tickers:
        sym = symbol.upper()
        q = quotes.get(sym, {})
        p = profiles.get(sym, {})

        # dividend_yield: FMP profile returns as decimal (0.045 = 4.5%)
        div_yield = _safe_float(p.get("lastDiv"))  # annual div per share
        price_val = _safe_float(q.get("price") or p.get("price"))
        if div_yield is not None and price_val and price_val > 0:
            div_yield = (div_yield / price_val) * 100  # convert to %
        else:
            # fallback: profile may have dividendYield already as %
            raw_dy = _safe_float(p.get("dividendYield"))
            if raw_dy is not None:
                div_yield = raw_dy * 100 if raw_dy < 1 else raw_dy

        try:
            db.execute(
                text("""
                    INSERT INTO platform_shared.market_data_cache (
                        symbol, price, price_change_pct, volume_avg_10d,
                        market_cap_m, pe_ratio, beta,
                        week52_high, week52_low,
                        dividend_yield, payout_ratio,
                        is_tracked, track_reason,
                        snapshot_date, fetched_at
                    ) VALUES (
                        :symbol, :price, :price_change_pct, :volume_avg_10d,
                        :market_cap_m, :pe_ratio, :beta,
                        :week52_high, :week52_low,
                        :dividend_yield, :payout_ratio,
                        TRUE, :track_reason,
                        :snapshot_date, :fetched_at
                    )
                    ON CONFLICT (symbol) DO UPDATE SET
                        price             = EXCLUDED.price,
                        price_change_pct  = EXCLUDED.price_change_pct,
                        volume_avg_10d    = EXCLUDED.volume_avg_10d,
                        market_cap_m      = EXCLUDED.market_cap_m,
                        pe_ratio          = EXCLUDED.pe_ratio,
                        beta              = EXCLUDED.beta,
                        week52_high       = EXCLUDED.week52_high,
                        week52_low        = EXCLUDED.week52_low,
                        dividend_yield    = EXCLUDED.dividend_yield,
                        payout_ratio      = EXCLUDED.payout_ratio,
                        is_tracked        = TRUE,
                        track_reason      = EXCLUDED.track_reason,
                        snapshot_date     = EXCLUDED.snapshot_date,
                        fetched_at        = EXCLUDED.fetched_at
                """),
                {
                    "symbol": sym,
                    "price": price_val,
                    "price_change_pct": _safe_float(q.get("changesPercentage")),
                    "volume_avg_10d": _safe_int(q.get("avgVolume")),
                    "market_cap_m": (
                        _safe_float(q.get("marketCap")) / 1_000_000
                        if q.get("marketCap") else None
                    ),
                    "pe_ratio": _safe_float(q.get("pe") or p.get("price") and None),
                    "beta": _safe_float(p.get("beta")),
                    "week52_high": _safe_float(q.get("yearHigh")),
                    "week52_low": _safe_float(q.get("yearLow")),
                    "dividend_yield": div_yield,
                    "payout_ratio": _safe_float(p.get("payoutRatio")),
                    "track_reason": track_reason,
                    "snapshot_date": today,
                    "fetched_at": now,
                },
            )
            upserted += 1
        except Exception as exc:
            logger.warning("Cache upsert failed for %s: %s", sym, exc)

    db.commit()
    logger.info("Upserted %d rows into market_data_cache", upserted)
    return upserted


def get_tracked_tickers(db: Session) -> list[str]:
    """Return all symbols marked is_tracked=TRUE in the cache."""
    rows = db.execute(
        text(
            "SELECT symbol FROM platform_shared.market_data_cache "
            "WHERE is_tracked = TRUE ORDER BY symbol"
        )
    ).fetchall()
    return [r[0] for r in rows]


def apply_market_filters(
    tickers: list[str],
    db: Session,
    min_yield: float = 0.0,
    max_payout_ratio: Optional[float] = None,
    min_volume: Optional[int] = None,
    min_market_cap_m: Optional[float] = None,
    max_market_cap_m: Optional[float] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    max_pe: Optional[float] = None,
    max_nav_discount_pct: Optional[float] = None,
    min_nav_discount_pct: Optional[float] = None,
) -> list[str]:
    """
    SQL pre-filter: given a list of tickers, return only those that pass
    all market criteria. Tickers not in cache are passed through (no data = no filter).
    """
    if not tickers:
        return []

    conditions = ["symbol IN :syms"]
    params: dict[str, Any] = {"syms": tuple(t.upper() for t in tickers)}

    if min_yield > 0:
        conditions.append("(dividend_yield IS NULL OR dividend_yield >= :min_yield)")
        params["min_yield"] = min_yield

    if max_payout_ratio is not None:
        conditions.append("(payout_ratio IS NULL OR payout_ratio <= :max_payout_ratio)")
        params["max_payout_ratio"] = max_payout_ratio

    if min_volume is not None:
        conditions.append("(volume_avg_10d IS NULL OR volume_avg_10d >= :min_volume)")
        params["min_volume"] = min_volume

    if min_market_cap_m is not None:
        conditions.append("(market_cap_m IS NULL OR market_cap_m >= :min_market_cap_m)")
        params["min_market_cap_m"] = min_market_cap_m

    if max_market_cap_m is not None:
        conditions.append("(market_cap_m IS NULL OR market_cap_m <= :max_market_cap_m)")
        params["max_market_cap_m"] = max_market_cap_m

    if min_price is not None:
        conditions.append("(price IS NULL OR price >= :min_price)")
        params["min_price"] = min_price

    if max_price is not None:
        conditions.append("(price IS NULL OR price <= :max_price)")
        params["max_price"] = max_price

    if max_pe is not None:
        conditions.append("(pe_ratio IS NULL OR pe_ratio <= :max_pe)")
        params["max_pe"] = max_pe

    if min_nav_discount_pct is not None:
        # nav_discount_pct is negative for discount, positive for premium
        # e.g. min_nav_discount_pct = -5 means "at least 5% discount"
        conditions.append(
            "(nav_discount_pct IS NULL OR nav_discount_pct <= :min_nav_discount_pct)"
        )
        params["min_nav_discount_pct"] = min_nav_discount_pct

    if max_nav_discount_pct is not None:
        conditions.append(
            "(nav_discount_pct IS NULL OR nav_discount_pct <= :max_nav_discount_pct)"
        )
        params["max_nav_discount_pct"] = max_nav_discount_pct

    where = " AND ".join(conditions)
    sql = text(
        f"SELECT symbol FROM platform_shared.market_data_cache WHERE {where}"
    )
    rows = db.execute(sql, params).fetchall()
    cached_pass = {r[0] for r in rows}

    # Tickers not in cache at all → pass through (can't filter what we don't have)
    cached_all = {r[0] for r in db.execute(
        text("SELECT symbol FROM platform_shared.market_data_cache WHERE symbol IN :syms"),
        {"syms": tuple(t.upper() for t in tickers)},
    ).fetchall()}
    not_in_cache = {t.upper() for t in tickers} - cached_all

    return list(cached_pass | not_in_cache)
