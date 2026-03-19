"""
Agent 07 — Opportunity Scanner Service
Market Data Cache: fetch FMP data per symbol, upsert to platform_shared.market_data_cache.

Flow:
  1. get_stale_tickers()   — split tickers into fresh (today) vs stale/missing
  2. fetch_and_upsert()    — call FMP per symbol (stable API is single-symbol only), upsert cache
  3. pre_filter_sql()      — SQL query against cache applying Group 2 criteria

FMP stable API endpoints (single symbol per call — batch returns empty):
  GET /profile?symbol=X&apikey=KEY → price, marketCap, beta, lastDividend, averageVolume
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
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


def _to_fmp_symbol(ticker: str) -> str:
    """Convert Bloomberg /PR format to FMP hyphen format.
    CHMI/PRA → CHMI-PA,  CIM/PRC → CIM-PC,  ATH/PRD → ATH-PD
    """
    if "/" in ticker:
        base, suffix = ticker.split("/", 1)
        if suffix.startswith("PR") and len(suffix) == 3:
            return f"{base}-P{suffix[2]}"
    return ticker


def _is_cusip(ticker: str) -> bool:
    """Return True if ticker looks like a CUSIP (9-char alphanumeric with leading digits)."""
    return len(ticker) == 9 and ticker[:6].isdigit()


async def _resolve_cusips(cusips: list[str]) -> dict[str, str]:
    """
    Resolve CUSIPs to FMP symbols via /stable/search-cusip.
    Returns {cusip: symbol} for each CUSIP that resolves to a tradeable symbol.
    Takes the result with the highest marketCap (primary listing).
    """
    result: dict[str, str] = {}
    sem = asyncio.Semaphore(settings.fmp_concurrency)

    async def _one(cusip: str):
        async with sem:
            async with httpx.AsyncClient(timeout=settings.fmp_request_timeout) as client:
                try:
                    resp = await client.get(
                        f"{settings.fmp_base_url}/search-cusip",
                        params={"cusip": cusip, "apikey": settings.fmp_api_key},
                        timeout=settings.fmp_request_timeout,
                    )
                    if resp.status_code != 200:
                        return
                    data = resp.json()
                    if not isinstance(data, list) or not data:
                        return
                    # Pick primary listing (highest marketCap, prefer plain symbol over .XX)
                    primary = sorted(
                        data,
                        key=lambda x: (
                            "." not in x.get("symbol", ""),
                            x.get("marketCap") or 0,
                        ),
                        reverse=True,
                    )[0]
                    sym = primary.get("symbol", "")
                    if sym:
                        result[cusip.upper()] = sym.upper()
                        logger.debug("CUSIP %s resolved to %s", cusip, sym)
                except Exception as exc:
                    logger.debug("CUSIP resolve %s failed: %s", cusip, exc)

    await asyncio.gather(*[_one(c) for c in cusips])
    logger.info("CUSIP resolution: %d/%d resolved", len(result), len(cusips))
    return result


# ─── FMP single-symbol fetcher ────────────────────────────────────────────────

async def _fmp_profile(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch FMP /stable/profile for one symbol.
    FMP stable API does NOT support batch (comma-separated) — returns empty list.
    Returns {} on any error or empty response.
    Fields: price, marketCap, beta, lastDividend, averageVolume, changePercentage,
            yearHigh (from range), yearLow (from range), sector, exchange.
    """
    try:
        resp = await client.get(
            f"{settings.fmp_base_url}/profile",
            params={"symbol": symbol, "apikey": settings.fmp_api_key},
            timeout=settings.fmp_request_timeout,
        )
        if resp.status_code != 200:
            logger.debug("FMP profile %s returned %d", symbol, resp.status_code)
            return {}
        data = resp.json()
        if not isinstance(data, list) or not data:
            return {}
        return data[0]
    except Exception as exc:
        logger.debug("FMP profile %s failed: %s", symbol, exc)
        return {}


async def _fetch_all_profiles(tickers: list[str]) -> dict[str, dict]:
    """Fetch FMP /profile for all tickers concurrently (capped at fmp_concurrency)."""
    sem = asyncio.Semaphore(settings.fmp_concurrency)
    result: dict[str, dict] = {}

    async def _one(sym: str):
        async with sem:
            async with httpx.AsyncClient(timeout=settings.fmp_request_timeout) as client:
                data = await _fmp_profile(sym, client)
                if data:
                    result[sym.upper()] = data

    await asyncio.gather(*[_one(t) for t in tickers])
    logger.info("FMP profiles fetched: %d/%d symbols got data", len(result), len(tickers))
    return result


async def _fmp_key_metrics(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch FMP /stable/ratios for one symbol.
    Returns priceToEarningsRatio, dividendPayoutRatio (as fraction, e.g. 0.85).
    Returns {} on any error.
    """
    try:
        resp = await client.get(
            f"{settings.fmp_base_url}/ratios",
            params={"symbol": symbol, "apikey": settings.fmp_api_key, "limit": 1},
            timeout=settings.fmp_request_timeout,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not isinstance(data, list) or not data:
            return {}
        return data[0]
    except Exception as exc:
        logger.debug("FMP ratios %s failed: %s", symbol, exc)
        return {}


async def _fmp_dividend_calendar(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch FMP /stable/dividends for one symbol.
    Returns ex_div_date, pay_date, div_frequency, and div_cagr_5y (%).
    Returns {} on any error.
    """
    try:
        resp = await client.get(
            f"{settings.fmp_base_url}/dividends",
            params={"symbol": symbol, "apikey": settings.fmp_api_key, "limit": 60},
            timeout=settings.fmp_request_timeout,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not isinstance(data, list) or not data:
            return {}
        entry = data[0]  # most recent
        result: dict = {
            "ex_div_date": entry.get("date") or entry.get("exDividendDate"),
            "pay_date": entry.get("paymentDate") or entry.get("payDate"),
            "div_frequency": entry.get("frequency"),
        }
        # 5-year CAGR: compare most recent dividend to one from ~5Y ago
        cutoff_5y = date.today() - timedelta(days=5 * 365)
        old_entries = [
            e for e in data
            if e.get("date") and date.fromisoformat(e["date"]) <= cutoff_5y
        ]
        if old_entries:
            recent_div = _safe_float(entry.get("adjDividend") or entry.get("dividend"))
            old_entry = old_entries[-1]
            old_div = _safe_float(old_entry.get("adjDividend") or old_entry.get("dividend"))
            if recent_div and old_div and old_div > 0:
                years = (date.fromisoformat(entry["date"]) - date.fromisoformat(old_entry["date"])).days / 365.25
                if years > 0:
                    result["div_cagr_5y"] = round(((recent_div / old_div) ** (1 / years) - 1) * 100, 2)
        return result
    except Exception as exc:
        logger.debug("FMP dividends %s failed: %s", symbol, exc)
        return {}


async def _fetch_supplemental(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch key-metrics + dividend calendar for all tickers concurrently.
    Returns {symbol: {"pe_ratio": ..., "payout_ratio": ..., "ex_div_date": ..., "pay_date": ...}}
    """
    sem = asyncio.Semaphore(settings.fmp_concurrency)
    result: dict[str, dict] = {}

    async def _one(sym: str):
        async with sem:
            async with httpx.AsyncClient(timeout=settings.fmp_request_timeout) as client:
                km, div = await asyncio.gather(
                    _fmp_key_metrics(sym, client),
                    _fmp_dividend_calendar(sym, client),
                )
                merged: dict = {}
                if km:
                    merged["pe_ratio"] = _safe_float(km.get("priceToEarningsRatio"))
                    raw_payout = _safe_float(km.get("dividendPayoutRatio"))
                    # FMP returns payout as fraction (0.85) — convert to % for storage
                    merged["payout_ratio"] = round(raw_payout * 100, 2) if raw_payout is not None else None
                if div:
                    merged["ex_div_date"] = div.get("ex_div_date")
                    merged["pay_date"] = div.get("pay_date")
                    merged["div_frequency"] = div.get("div_frequency")
                    merged["div_cagr_5y"] = div.get("div_cagr_5y")
                if merged:
                    result[sym.upper()] = merged

    await asyncio.gather(*[_one(t) for t in tickers])
    logger.info("FMP supplemental fetched: %d/%d symbols got data", len(result), len(tickers))
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
    Fetch FMP /stable/profile for each ticker (single-symbol calls, concurrent)
    and upsert into market_data_cache.  Returns count of rows upserted.

    FMP stable API does NOT support batch queries — single symbol per call only.
    Field mapping (stable /profile response):
      price, changePercentage, averageVolume, marketCap, beta, lastDividend
    """
    if not tickers:
        return 0

    # Separate CUSIPs from regular tickers
    cusip_tickers = [t for t in tickers if _is_cusip(t)]
    regular_tickers = [t for t in tickers if not _is_cusip(t)]

    # Resolve CUSIPs to FMP symbols (concurrent API calls)
    cusip_map: dict[str, str] = {}
    if cusip_tickers:
        cusip_map = await _resolve_cusips(cusip_tickers)
        unresolved = len(cusip_tickers) - len(cusip_map)
        if unresolved:
            logger.info("Could not resolve %d CUSIPs — skipping those", unresolved)

    # Build unified lookup: fmp_symbol → original_symbol
    # Regular tickers: convert preferred format (CHMI/PRA → CHMI-PA)
    # CUSIP tickers: use resolved FMP symbol, store result under CUSIP key
    fmp_lookup: dict[str, str] = {_to_fmp_symbol(t).upper(): t.upper() for t in regular_tickers}
    for cusip, fmp_sym in cusip_map.items():
        fmp_lookup[fmp_sym.upper()] = cusip.upper()

    fmp_syms = list(fmp_lookup.keys())
    profiles_by_fmp, supplemental_by_fmp = await asyncio.gather(
        _fetch_all_profiles(fmp_syms),
        _fetch_supplemental(fmp_syms),
    )
    # Remap results back to original ticker symbols
    profiles = {fmp_lookup[fmp_sym]: data for fmp_sym, data in profiles_by_fmp.items() if fmp_sym in fmp_lookup}
    supplemental = {fmp_lookup[fmp_sym]: data for fmp_sym, data in supplemental_by_fmp.items() if fmp_sym in fmp_lookup}

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    upserted = 0

    for symbol in tickers:
        sym = symbol.upper()
        p = profiles.get(sym, {})
        s = supplemental.get(sym, {})

        price_val = _safe_float(p.get("price"))

        # dividend_yield: lastDividend is annual $ per share — convert to %
        last_div = _safe_float(p.get("lastDividend"))
        if last_div is not None and price_val and price_val > 0:
            div_yield = round((last_div / price_val) * 100, 4)
        else:
            div_yield = None

        # chowder_number = yield_ttm + 5Y div CAGR
        div_cagr_5y = s.get("div_cagr_5y")
        chowder_number = (
            round(div_yield + div_cagr_5y, 2)
            if div_yield is not None and div_cagr_5y is not None
            else None
        )

        # week52 range comes as "7.85-12.19" string in profile
        week52_high, week52_low = None, None
        range_str = p.get("range", "")
        if range_str and "-" in range_str:
            parts = range_str.split("-")
            if len(parts) == 2:
                week52_low = _safe_float(parts[0])
                week52_high = _safe_float(parts[1])

        try:
            db.execute(
                text("""
                    INSERT INTO platform_shared.market_data_cache (
                        symbol, price, price_change_pct, volume_avg_10d,
                        market_cap_m, pe_ratio, beta,
                        week52_high, week52_low,
                        dividend_yield, payout_ratio, chowder_number,
                        ex_div_date, pay_date, div_frequency,
                        is_tracked, track_reason,
                        snapshot_date, fetched_at
                    ) VALUES (
                        :symbol, :price, :price_change_pct, :volume_avg_10d,
                        :market_cap_m, :pe_ratio, :beta,
                        :week52_high, :week52_low,
                        :dividend_yield, :payout_ratio, :chowder_number,
                        :ex_div_date, :pay_date, :div_frequency,
                        TRUE, :track_reason,
                        :snapshot_date, :fetched_at
                    )
                    ON CONFLICT (symbol) DO UPDATE SET
                        price             = EXCLUDED.price,
                        price_change_pct  = EXCLUDED.price_change_pct,
                        volume_avg_10d    = EXCLUDED.volume_avg_10d,
                        market_cap_m      = EXCLUDED.market_cap_m,
                        pe_ratio          = COALESCE(EXCLUDED.pe_ratio, platform_shared.market_data_cache.pe_ratio),
                        beta              = EXCLUDED.beta,
                        week52_high       = EXCLUDED.week52_high,
                        week52_low        = EXCLUDED.week52_low,
                        dividend_yield    = EXCLUDED.dividend_yield,
                        payout_ratio      = COALESCE(EXCLUDED.payout_ratio, platform_shared.market_data_cache.payout_ratio),
                        chowder_number    = COALESCE(EXCLUDED.chowder_number, platform_shared.market_data_cache.chowder_number),
                        ex_div_date       = COALESCE(EXCLUDED.ex_div_date, platform_shared.market_data_cache.ex_div_date),
                        pay_date          = COALESCE(EXCLUDED.pay_date, platform_shared.market_data_cache.pay_date),
                        div_frequency     = COALESCE(EXCLUDED.div_frequency, platform_shared.market_data_cache.div_frequency),
                        is_tracked        = TRUE,
                        track_reason      = EXCLUDED.track_reason,
                        snapshot_date     = EXCLUDED.snapshot_date,
                        fetched_at        = EXCLUDED.fetched_at
                """),
                {
                    "symbol": sym,
                    "price": price_val,
                    "price_change_pct": _safe_float(p.get("changePercentage")),
                    "volume_avg_10d": _safe_int(p.get("averageVolume")),
                    "market_cap_m": (
                        _safe_float(p.get("marketCap")) / 1_000_000
                        if p.get("marketCap") else None
                    ),
                    "pe_ratio": s.get("pe_ratio"),
                    "beta": _safe_float(p.get("beta")),
                    "week52_high": week52_high,
                    "week52_low": week52_low,
                    "dividend_yield": div_yield,
                    "payout_ratio": s.get("payout_ratio"),
                    "chowder_number": chowder_number,
                    "ex_div_date": s.get("ex_div_date"),
                    "pay_date": s.get("pay_date"),
                    "div_frequency": s.get("div_frequency"),
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

    # Backfill sector + industry on the securities table from FMP profile data.
    # Uses the resolved FMP symbol for CUSIPs, original symbol for regular tickers.
    # Only updates rows where sector/industry is NULL to avoid overwriting manual data.
    sec_updated = 0
    for fmp_sym, orig_sym in fmp_lookup.items():
        p = profiles.get(orig_sym, {})
        sector = p.get("sector") or None
        industry = p.get("industry") or None
        name = p.get("companyName") or None
        if not sector and not industry and not name:
            continue
        try:
            db.execute(
                text("""
                    UPDATE platform_shared.securities
                    SET
                        name     = COALESCE(name,     :name),
                        sector   = COALESCE(sector,   :sector),
                        industry = COALESCE(industry, :industry)
                    WHERE symbol = :symbol
                      AND (name IS NULL OR sector IS NULL OR industry IS NULL)
                """),
                {"symbol": orig_sym, "name": name, "sector": sector, "industry": industry},
            )
            sec_updated += 1
        except Exception as exc:
            logger.debug("Securities sector update failed for %s: %s", orig_sym, exc)
    if sec_updated:
        db.commit()
        logger.info("Backfilled sector/industry for %d securities", sec_updated)

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
