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
from app.scanner.bond_pricer import BondPricer

logger = logging.getLogger(__name__)

# ─── FMP rate-limit helper ─────────────────────────────────────────────────────

async def _fmp_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    *,
    retries: int = 3,
) -> httpx.Response:
    """GET with exponential backoff on 429 Too Many Requests."""
    for attempt in range(retries):
        resp = await client.get(url, params=params)
        if resp.status_code != 429:
            return resp
        wait = 2 ** (attempt + 1)   # 2s, 4s, 8s
        logger.warning("FMP 429 for %s — retry %d/%d after %ds", url, attempt + 1, retries, wait)
        await asyncio.sleep(wait)
    return resp  # return last response even if still 429


# ─── Bond registry ─────────────────────────────────────────────────────────────
# Known corporate bonds held as CUSIPs.  Provides coupon/maturity metadata for
# theoretical PV pricing when FMP CUSIP resolution returns no tradeable symbol.
# Key: CUSIP (upper), Value: {coupon: float pct, maturity: YYYY-MM-DD, face: float}
_BOND_REGISTRY: dict[str, dict] = {
    "427096AH5": {"coupon": 2.625, "maturity": "2026-09-16", "face": 1000.0},  # HTGC 2.625% 09/2026
    "55342UAH7": {"coupon": 5.0,   "maturity": "2027-10-15", "face": 1000.0},  # MPW 5% 10/2027
    "74348TAW2": {"coupon": 3.437, "maturity": "2028-10-15", "face": 1000.0},  # PSEC 3.437% 10/2028
}


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
    """Return True if ticker looks like a CUSIP.
    CUSIP format: 9 alphanumeric chars, first 2+ chars are digits.
    Real CUSIPs have letters in the issuer/issue portions (e.g. 55342UAH7).
    """
    return len(ticker) == 9 and ticker[:2].isdigit() and ticker.isalnum()


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


async def _price_bonds(cusips: list[str]) -> dict[str, float]:
    """Price unresolved CUSIP bonds via FRED Treasury yields + PV discounting.

    Only prices CUSIPs that exist in _BOND_REGISTRY (known bond metadata).
    Returns {cusip_upper: price_per_100_face}.
    """
    bond_prices: dict[str, float] = {}
    pricer = BondPricer()
    for cusip in cusips:
        meta = _BOND_REGISTRY.get(cusip.upper())
        if not meta:
            logger.debug("No bond metadata for CUSIP %s — skipping PV pricing", cusip)
            continue
        price = await pricer.get_price(
            coupon_rate_pct=meta["coupon"],
            maturity_str=meta["maturity"],
            face=meta["face"],
        )
        if price is not None:
            bond_prices[cusip.upper()] = price
            logger.info(
                "Bond PV price CUSIP %s: %.4f (coupon=%.3f%% maturity=%s)",
                cusip, price, meta["coupon"], meta["maturity"],
            )
        else:
            logger.warning("Bond PV pricing failed for CUSIP %s", cusip)
    return bond_prices


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
        resp = await _fmp_get(
            client,
            f"{settings.fmp_base_url}/profile",
            {"symbol": symbol, "apikey": settings.fmp_api_key},
        )
        if resp.status_code != 200:
            logger.debug("FMP profile %s returned %d", symbol, resp.status_code)
            return {}
        data = resp.json()
        if not isinstance(data, list) or not data:
            return {}
        result = dict(data[0])
        result["expense_ratio"] = data[0].get("expenseRatio")   # float or None
        return result
    except Exception as exc:
        logger.debug("FMP profile %s failed: %s", symbol, exc)
        return {}


async def _fetch_all_profiles(tickers: list[str]) -> dict[str, dict]:
    """Fetch FMP /profile for all tickers concurrently (capped at fmp_concurrency)."""
    sem = asyncio.Semaphore(settings.fmp_concurrency)
    result: dict[str, dict] = {}

    async def _one(sym: str):
        async with sem:
            await asyncio.sleep(0.25)   # pace to ≤4 req/s per slot — prevents 429 bursts
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
    Returns priceToEarningsRatio, priceToBookRatio, dividendPayoutRatio plus
    interestCoverage, netDebtToEBITDA, returnOnEquity, freeCashFlowYield.
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


async def _fmp_technical_indicators(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch SMA50, SMA200, RSI14 from FMP /stable/technical-indicator/daily.
    Returns {sma_50, sma_200, rsi_14d, support_level, resistance_level} or {}.
    """
    result: dict = {}
    try:
        # Fetch SMA50, SMA200, RSI14 concurrently (3 calls)
        sma50_resp, sma200_resp, rsi_resp = await asyncio.gather(
            client.get(f"{settings.fmp_base_url}/technical-indicator/daily",
                       params={"symbol": symbol, "type": "sma", "period": 50,
                               "limit": 1, "apikey": settings.fmp_api_key},
                       timeout=settings.fmp_request_timeout),
            client.get(f"{settings.fmp_base_url}/technical-indicator/daily",
                       params={"symbol": symbol, "type": "sma", "period": 200,
                               "limit": 1, "apikey": settings.fmp_api_key},
                       timeout=settings.fmp_request_timeout),
            client.get(f"{settings.fmp_base_url}/technical-indicator/daily",
                       params={"symbol": symbol, "type": "rsi", "period": 14,
                               "limit": 1, "apikey": settings.fmp_api_key},
                       timeout=settings.fmp_request_timeout),
            return_exceptions=True,
        )
        if not isinstance(sma50_resp, Exception) and sma50_resp.status_code == 200:
            d = sma50_resp.json()
            if isinstance(d, list) and d:
                result["sma_50"] = _safe_float(d[0].get("sma"))
        if not isinstance(sma200_resp, Exception) and sma200_resp.status_code == 200:
            d = sma200_resp.json()
            if isinstance(d, list) and d:
                result["sma_200"] = _safe_float(d[0].get("sma"))
        if not isinstance(rsi_resp, Exception) and rsi_resp.status_code == 200:
            d = rsi_resp.json()
            if isinstance(d, list) and d:
                result["rsi_14d"] = _safe_float(d[0].get("rsi"))
    except Exception as exc:
        logger.debug("FMP technical indicators %s failed: %s", symbol, exc)
    return result


async def _fmp_key_metrics_ttm(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch buybackYieldTTM and tangibleAssetValue from FMP.
    - /stable/key-metrics-ttm → buyback_yield
    - /stable/key-metrics     → tangible_asset_value (for NAV per share computation)
    Returns {} on any error.
    """
    try:
        ttm_resp, km_resp = await asyncio.gather(
            client.get(
                f"{settings.fmp_base_url}/key-metrics-ttm",
                params={"symbol": symbol, "apikey": settings.fmp_api_key},
                timeout=settings.fmp_request_timeout,
            ),
            client.get(
                f"{settings.fmp_base_url}/key-metrics",
                params={"symbol": symbol, "apikey": settings.fmp_api_key, "limit": 1},
                timeout=settings.fmp_request_timeout,
            ),
            return_exceptions=True,
        )
        result: dict = {}
        if not isinstance(ttm_resp, Exception) and ttm_resp.status_code == 200:
            ttm_data = ttm_resp.json()
            if isinstance(ttm_data, list) and ttm_data:
                result["buyback_yield"] = _safe_float(ttm_data[0].get("buybackYieldTTM"))
        if not isinstance(km_resp, Exception) and km_resp.status_code == 200:
            km_data = km_resp.json()
            if isinstance(km_data, list) and km_data:
                result["tangible_asset_value"] = _safe_float(km_data[0].get("tangibleAssetValue"))
        return result
    except Exception as exc:
        logger.debug("FMP key-metrics-ttm %s failed: %s", symbol, exc)
        return {}


async def _fmp_analyst_estimates(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch analyst price target and next earnings date from FMP.
    Returns {analyst_price_target, next_earnings_date} or {}.
    """
    result: dict = {}
    try:
        pt_resp = await client.get(
            f"{settings.fmp_base_url}/analyst-estimates",
            params={"symbol": symbol, "limit": 1, "apikey": settings.fmp_api_key},
            timeout=settings.fmp_request_timeout,
        )
        if pt_resp.status_code == 200:
            d = pt_resp.json()
            if isinstance(d, list) and d:
                result["analyst_price_target"] = _safe_float(d[0].get("estimatedEpsAvg"))
    except Exception as exc:
        logger.debug("FMP analyst-estimates %s failed: %s", symbol, exc)
    return result


async def _fmp_etf_info(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch FMP /stable/etf-info for ETFs and CEFs.
    Returns nav (per share NAV), expenseRatio, assetsUnderManagement, category.
    Returns {} on any error or non-ETF symbol.
    """
    try:
        resp = await client.get(
            f"{settings.fmp_base_url}/etf-info",
            params={"symbol": symbol, "apikey": settings.fmp_api_key},
            timeout=settings.fmp_request_timeout,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not isinstance(data, list) or not data:
            return {}
        return data[0]
    except Exception as exc:
        logger.debug("FMP etf-info %s failed: %s", symbol, exc)
        return {}


async def _fmp_credit_rating(symbol: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Fetch credit rating from FMP /stable/rating.
    Returns a rating string (e.g. "A-", "BBB+") or None.
    FMP returns its own scoring-model rating, not agency ratings, but uses standard letter grades.
    """
    try:
        resp = await client.get(
            f"{settings.fmp_base_url}/rating",
            params={"symbol": symbol, "apikey": settings.fmp_api_key},
            timeout=settings.fmp_request_timeout,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None
        entry = data[0]
        # Prefer ratingDetailsMoodysRating (agency), fall back to FMP model rating
        return (
            entry.get("ratingDetailsMoodysRating")
            or entry.get("ratingAgencyMoodyRating")
            or entry.get("rating")
            or None
        )
    except Exception as exc:
        logger.debug("FMP rating %s failed: %s", symbol, exc)
        return None


async def _fmp_dividend_calendar(symbol: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch FMP /stable/dividends for one symbol.
    Returns ex_div_date, pay_date, div_frequency, div_cagr_5y, div_cagr_3yr,
    div_cagr_10yr, consecutive_growth_yrs, yield_5yr_avg.
    Returns {} on any error.
    """
    try:
        resp = await client.get(
            f"{settings.fmp_base_url}/dividends",
            params={"symbol": symbol, "apikey": settings.fmp_api_key, "limit": 120},
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

        today = date.today()

        # Group dividends by calendar year for CAGR and consecutive growth calculations
        by_year: dict[int, float] = {}
        for e in data:
            raw_date = e.get("date")
            if not raw_date:
                continue
            try:
                d = date.fromisoformat(raw_date[:10])
            except (ValueError, TypeError):
                continue
            amt = _safe_float(e.get("adjDividend") or e.get("dividend")) or 0
            by_year[d.year] = by_year.get(d.year, 0.0) + amt

        # Remove current partial year
        by_year.pop(today.year, None)
        sorted_years = sorted(by_year)

        def _cagr(years_back: int) -> Optional[float]:
            cutoff = today.year - years_back
            relevant = {y: v for y, v in by_year.items() if y >= cutoff}
            if len(relevant) < 2:
                return None
            yrs = sorted(relevant)
            first, last = relevant[yrs[0]], relevant[yrs[-1]]
            n = yrs[-1] - yrs[0]
            if first <= 0 or n <= 0:
                return None
            return round(((last / first) ** (1.0 / n) - 1) * 100, 2)

        result["div_cagr_5y"]  = _cagr(5)
        result["div_cagr_3yr"] = _cagr(3)
        result["div_cagr_10yr"] = _cagr(10)

        # Consecutive growth years: count back years with YoY increase
        consec = 0
        if len(sorted_years) >= 2:
            for i in range(len(sorted_years) - 1, 0, -1):
                yr, prev_yr = sorted_years[i], sorted_years[i - 1]
                if yr - prev_yr == 1 and by_year[yr] > by_year[prev_yr]:
                    consec += 1
                else:
                    break
        result["consecutive_growth_yrs"] = consec if consec > 0 else None

        # Average annual dividend over last 5 years (raw $ per year; caller divides by price)
        cutoff_5y = today.year - 5
        recent_5y = {y: v for y, v in by_year.items() if y >= cutoff_5y and v > 0}
        result["avg_annual_div_5y"] = round(sum(recent_5y.values()) / len(recent_5y), 6) if recent_5y else None

        return result
    except Exception as exc:
        logger.debug("FMP dividends %s failed: %s", symbol, exc)
        return {}


async def _fetch_supplemental(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch ratios + dividend calendar + ETF info + technicals + key metrics TTM
    for all tickers concurrently.
    """
    sem = asyncio.Semaphore(settings.fmp_concurrency)
    result: dict[str, dict] = {}

    async def _one(sym: str):
        async with sem:
            await asyncio.sleep(0.25)   # pace supplemental calls to prevent 429 bursts
            async with httpx.AsyncClient(timeout=settings.fmp_request_timeout) as client:
                km, div, etf, tech, ttm, cr = await asyncio.gather(
                    _fmp_key_metrics(sym, client),
                    _fmp_dividend_calendar(sym, client),
                    _fmp_etf_info(sym, client),
                    _fmp_technical_indicators(sym, client),
                    _fmp_key_metrics_ttm(sym, client),
                    _fmp_credit_rating(sym, client),
                    return_exceptions=True,
                )
                # Normalize exceptions to empty dicts / None
                if isinstance(km, Exception):   km = {}
                if isinstance(div, Exception):  div = {}
                if isinstance(etf, Exception):  etf = {}
                if isinstance(tech, Exception): tech = {}
                if isinstance(ttm, Exception):  ttm = {}
                if isinstance(cr, Exception):   cr = None

                merged: dict = {}

                # /ratios: extract many fields
                if km:
                    merged["pe_ratio"]             = _safe_float(km.get("priceToEarningsRatio"))
                    raw_payout                      = _safe_float(km.get("dividendPayoutRatio"))
                    merged["payout_ratio"]         = round(raw_payout * 100, 2) if raw_payout is not None else None
                    merged["price_to_book"]        = _safe_float(km.get("priceToBookRatio"))
                    merged["interest_coverage_ratio"] = _safe_float(
                        km.get("interestCoverage") or km.get("timesInterestEarned")
                    )
                    merged["return_on_equity"]     = _safe_float(km.get("returnOnEquity"))
                    raw_fcfy                        = _safe_float(km.get("freeCashFlowYield"))
                    merged["free_cash_flow_yield"] = round(raw_fcfy * 100, 4) if raw_fcfy is not None else None
                    # net_debt / EBITDA derived from debtToEquity and EV/EBITDA as proxy
                    merged["net_debt_ebitda"]      = _safe_float(
                        km.get("netDebtToEBITDA") or km.get("debtToEbitda")
                    )
                    merged["debt_to_equity"]       = _safe_float(km.get("debtToEquityRatio"))
                    pass  # tangible_asset_value comes from ttm block below

                # credit rating from FMP rating endpoint
                if cr is not None:
                    merged["credit_rating"] = cr

                # /dividends: dates + CAGRs + consecutive growth
                if div:
                    merged["ex_div_date"]            = div.get("ex_div_date")
                    merged["pay_date"]               = div.get("pay_date")
                    merged["div_frequency"]          = div.get("div_frequency")
                    merged["div_cagr_5y"]            = div.get("div_cagr_5y")
                    merged["div_cagr_3yr"]           = div.get("div_cagr_3yr")
                    merged["div_cagr_10yr"]          = div.get("div_cagr_10yr")
                    merged["consecutive_growth_yrs"] = div.get("consecutive_growth_yrs")

                # /etf-info: NAV
                if etf:
                    nav = _safe_float(etf.get("nav"))
                    merged["nav_value"] = nav

                # technical indicators: SMA, RSI
                if tech:
                    merged.update({k: v for k, v in tech.items() if v is not None})

                # key-metrics-ttm: buyback yield + tangible asset value for NAV
                if ttm:
                    merged["buyback_yield"] = ttm.get("buyback_yield")
                    if ttm.get("tangible_asset_value") is not None:
                        merged["tangible_asset_value"] = ttm["tangible_asset_value"]

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

    # Ensure optional columns exist (idempotent)
    for _col_ddl in (
        "ADD COLUMN IF NOT EXISTS fmp_sector TEXT",
        "ADD COLUMN IF NOT EXISTS fmp_industry TEXT",
        "ADD COLUMN IF NOT EXISTS debt_to_equity FLOAT",
    ):
        try:
            db.execute(text(f"ALTER TABLE platform_shared.market_data_cache {_col_ddl}"))
            db.commit()
        except Exception as _col_err:
            db.rollback()
            logger.debug("column ensure (%s): %s", _col_ddl, _col_err)

    # Separate CUSIPs from regular tickers
    cusip_tickers = [t for t in tickers if _is_cusip(t)]
    regular_tickers = [t for t in tickers if not _is_cusip(t)]

    # Mark CUSIP-format symbols as BOND in securities table
    for cusip in cusip_tickers:
        try:
            db.execute(text(
                "UPDATE platform_shared.securities SET asset_type = 'BOND' "
                "WHERE symbol = :sym AND (asset_type IS NULL OR asset_type = 'DIVIDEND_STOCK')"
            ), {"sym": cusip.upper()})
        except Exception as _bond_err:
            logger.debug("BOND asset_type update for %s: %s", cusip, _bond_err)

    # Mark /PR format symbols as PREFERRED_STOCK in securities table
    preferred_tickers = [t for t in regular_tickers if "/PR" in t.upper() or "-P" in t.upper()]
    for pref in preferred_tickers:
        try:
            db.execute(text(
                "UPDATE platform_shared.securities SET asset_type = 'PREFERRED_STOCK' "
                "WHERE symbol = :sym AND (asset_type IS NULL OR asset_type = 'DIVIDEND_STOCK')"
            ), {"sym": pref.upper()})
        except Exception as _pref_err:
            logger.debug("PREFERRED_STOCK asset_type update for %s: %s", pref, _pref_err)

    if cusip_tickers or preferred_tickers:
        db.commit()

    # Resolve CUSIPs to FMP symbols (concurrent API calls)
    cusip_map: dict[str, str] = {}
    bond_prices: dict[str, float] = {}
    if cusip_tickers:
        cusip_map = await _resolve_cusips(cusip_tickers)
        unresolved_cusips = [c for c in cusip_tickers if c.upper() not in cusip_map]
        if unresolved_cusips:
            logger.info(
                "Could not resolve %d CUSIPs via FMP — attempting PV bond pricing",
                len(unresolved_cusips),
            )
            bond_prices = await _price_bonds(unresolved_cusips)

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

        # For unresolved CUSIP bonds, use PV-discounted theoretical price
        if price_val is None and sym in bond_prices:
            price_val = bond_prices[sym]

        # dividend_yield: lastDividend is annual $ per share — convert to %
        last_div = _safe_float(p.get("lastDividend"))
        if last_div is not None and price_val and price_val > 0:
            div_yield = round((last_div / price_val) * 100, 4)
        elif price_val and price_val > 0 and sym in bond_prices:
            # For CUSIP bonds without FMP data: current yield = annual coupon / price
            meta = _BOND_REGISTRY.get(sym)
            if meta:
                div_yield = round((meta["coupon"] / price_val) * 100, 4)
            else:
                div_yield = None
        else:
            div_yield = None

        # yield_5yr_avg: avg annual dividend (last 5y) ÷ current price
        avg_annual_div_5y = s.get("avg_annual_div_5y")
        yield_5yr_avg = (
            round(avg_annual_div_5y / price_val * 100, 4)
            if avg_annual_div_5y and price_val and price_val > 0
            else None
        )

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

        # NAV per share: meaningful only for fund-type assets (CEF, BDC, ETF)
        # tangibleAssetValue = stockholders equity; shares = marketCap / price
        nav_value = s.get("nav_value")  # from etf-info (usually empty)
        if not nav_value:
            # Only compute for fund-type assets where NAV discount is meaningful
            try:
                sec_at_row = db.execute(
                    text("SELECT asset_type FROM platform_shared.securities WHERE symbol = :sym"),
                    {"sym": sym}
                ).fetchone()
                sec_at = (sec_at_row[0] or "").upper() if sec_at_row else ""
            except Exception:
                sec_at = ""
            if sec_at in ("CEF", "BDC", "ETF", "COVERED_CALL_ETF"):
                tangible_asset_value = s.get("tangible_asset_value")
                market_cap = _safe_float(p.get("marketCap"))
                if tangible_asset_value and tangible_asset_value > 0 and price_val and market_cap and market_cap > 0:
                    shares_outstanding = market_cap / price_val
                    if shares_outstanding > 0:
                        nav_value = round(tangible_asset_value / shares_outstanding, 4)
        nav_discount_pct = None
        if nav_value and price_val and nav_value > 0:
            nav_discount_pct = round((price_val - nav_value) / nav_value * 100, 4)

        # Derive coverage_metric_type from asset_type in securities
        cov_metric_type = None
        try:
            sec_row = db.execute(
                text("SELECT asset_type FROM platform_shared.securities WHERE symbol = :sym"),
                {"sym": sym}
            ).fetchone()
            if sec_row:
                at = (sec_row[0] or "").upper()
                if at in ("EQUITY_REIT", "MORTGAGE_REIT"):
                    cov_metric_type = "AFFO"
                elif at in ("BDC",):
                    cov_metric_type = "NII"
                elif at in ("BOND", "PREFERRED_STOCK", "PREFERRED"):
                    cov_metric_type = "INTEREST"
                else:
                    cov_metric_type = "FCF"
        except Exception:
            pass

        # Compute support/resistance from 20-day price range (week52 as proxy if needed)
        support_level = week52_low
        resistance_level = week52_high

        try:
            db.execute(
                text("""
                    INSERT INTO platform_shared.market_data_cache (
                        symbol, price, price_change_pct, volume_avg_10d,
                        market_cap_m, pe_ratio, price_to_book, beta,
                        week52_high, week52_low,
                        dividend_yield, payout_ratio, chowder_number,
                        ex_div_date, pay_date, div_frequency,
                        nav_value, nav_discount_pct,
                        -- new fields
                        sma_50, sma_200, rsi_14d,
                        support_level, resistance_level,
                        yield_5yr_avg,
                        div_cagr_3yr, div_cagr_10yr, consecutive_growth_yrs,
                        buyback_yield, coverage_metric_type,
                        interest_coverage_ratio, net_debt_ebitda,
                        free_cash_flow_yield, return_on_equity,
                        credit_rating, debt_to_equity,
                        expense_ratio,
                        fmp_sector, fmp_industry,
                        is_tracked, track_reason,
                        snapshot_date, fetched_at
                    ) VALUES (
                        :symbol, :price, :price_change_pct, :volume_avg_10d,
                        :market_cap_m, :pe_ratio, :price_to_book, :beta,
                        :week52_high, :week52_low,
                        :dividend_yield, :payout_ratio, :chowder_number,
                        :ex_div_date, :pay_date, :div_frequency,
                        :nav_value, :nav_discount_pct,
                        :sma_50, :sma_200, :rsi_14d,
                        :support_level, :resistance_level,
                        :yield_5yr_avg,
                        :div_cagr_3yr, :div_cagr_10yr, :consecutive_growth_yrs,
                        :buyback_yield, :coverage_metric_type,
                        :interest_coverage_ratio, :net_debt_ebitda,
                        :free_cash_flow_yield, :return_on_equity,
                        :credit_rating, :debt_to_equity,
                        :expense_ratio,
                        :fmp_sector, :fmp_industry,
                        TRUE, :track_reason,
                        :snapshot_date, :fetched_at
                    )
                    ON CONFLICT (symbol) DO UPDATE SET
                        price                    = COALESCE(EXCLUDED.price,            platform_shared.market_data_cache.price),
                        price_change_pct         = COALESCE(EXCLUDED.price_change_pct, platform_shared.market_data_cache.price_change_pct),
                        volume_avg_10d           = COALESCE(EXCLUDED.volume_avg_10d,   platform_shared.market_data_cache.volume_avg_10d),
                        market_cap_m             = COALESCE(EXCLUDED.market_cap_m,     platform_shared.market_data_cache.market_cap_m),
                        pe_ratio                 = COALESCE(EXCLUDED.pe_ratio,          platform_shared.market_data_cache.pe_ratio),
                        price_to_book            = COALESCE(EXCLUDED.price_to_book,     platform_shared.market_data_cache.price_to_book),
                        beta                     = COALESCE(EXCLUDED.beta,             platform_shared.market_data_cache.beta),
                        week52_high              = COALESCE(EXCLUDED.week52_high,      platform_shared.market_data_cache.week52_high),
                        week52_low               = COALESCE(EXCLUDED.week52_low,       platform_shared.market_data_cache.week52_low),
                        dividend_yield           = COALESCE(EXCLUDED.dividend_yield,   platform_shared.market_data_cache.dividend_yield),
                        payout_ratio             = COALESCE(EXCLUDED.payout_ratio,      platform_shared.market_data_cache.payout_ratio),
                        chowder_number           = COALESCE(EXCLUDED.chowder_number,    platform_shared.market_data_cache.chowder_number),
                        ex_div_date              = COALESCE(EXCLUDED.ex_div_date,       platform_shared.market_data_cache.ex_div_date),
                        pay_date                 = COALESCE(EXCLUDED.pay_date,          platform_shared.market_data_cache.pay_date),
                        div_frequency            = COALESCE(EXCLUDED.div_frequency,     platform_shared.market_data_cache.div_frequency),
                        nav_value                = EXCLUDED.nav_value,
                        nav_discount_pct         = EXCLUDED.nav_discount_pct,
                        sma_50                   = COALESCE(EXCLUDED.sma_50,            platform_shared.market_data_cache.sma_50),
                        sma_200                  = COALESCE(EXCLUDED.sma_200,           platform_shared.market_data_cache.sma_200),
                        rsi_14d                  = COALESCE(EXCLUDED.rsi_14d,           platform_shared.market_data_cache.rsi_14d),
                        support_level            = COALESCE(EXCLUDED.support_level,     platform_shared.market_data_cache.support_level),
                        resistance_level         = COALESCE(EXCLUDED.resistance_level,  platform_shared.market_data_cache.resistance_level),
                        div_cagr_3yr             = COALESCE(EXCLUDED.div_cagr_3yr,      platform_shared.market_data_cache.div_cagr_3yr),
                        div_cagr_10yr            = COALESCE(EXCLUDED.div_cagr_10yr,     platform_shared.market_data_cache.div_cagr_10yr),
                        consecutive_growth_yrs   = COALESCE(EXCLUDED.consecutive_growth_yrs, platform_shared.market_data_cache.consecutive_growth_yrs),
                        buyback_yield            = COALESCE(EXCLUDED.buyback_yield,     platform_shared.market_data_cache.buyback_yield),
                        coverage_metric_type     = COALESCE(EXCLUDED.coverage_metric_type, platform_shared.market_data_cache.coverage_metric_type),
                        interest_coverage_ratio  = COALESCE(EXCLUDED.interest_coverage_ratio, platform_shared.market_data_cache.interest_coverage_ratio),
                        net_debt_ebitda          = COALESCE(EXCLUDED.net_debt_ebitda,   platform_shared.market_data_cache.net_debt_ebitda),
                        free_cash_flow_yield     = COALESCE(EXCLUDED.free_cash_flow_yield, platform_shared.market_data_cache.free_cash_flow_yield),
                        return_on_equity         = COALESCE(EXCLUDED.return_on_equity,  platform_shared.market_data_cache.return_on_equity),
                        yield_5yr_avg            = COALESCE(EXCLUDED.yield_5yr_avg,     platform_shared.market_data_cache.yield_5yr_avg),
                        credit_rating            = COALESCE(EXCLUDED.credit_rating,     platform_shared.market_data_cache.credit_rating),
                        debt_to_equity           = COALESCE(EXCLUDED.debt_to_equity,    platform_shared.market_data_cache.debt_to_equity),
                        expense_ratio            = COALESCE(EXCLUDED.expense_ratio,     platform_shared.market_data_cache.expense_ratio),
                        fmp_sector               = COALESCE(EXCLUDED.fmp_sector,        platform_shared.market_data_cache.fmp_sector),
                        fmp_industry             = COALESCE(EXCLUDED.fmp_industry,      platform_shared.market_data_cache.fmp_industry),
                        is_tracked               = TRUE,
                        track_reason             = EXCLUDED.track_reason,
                        snapshot_date            = EXCLUDED.snapshot_date,
                        fetched_at               = EXCLUDED.fetched_at
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
                    "price_to_book": s.get("price_to_book"),
                    "beta": _safe_float(p.get("beta")),
                    "week52_high": week52_high,
                    "week52_low": week52_low,
                    "dividend_yield": div_yield,
                    "payout_ratio": s.get("payout_ratio"),
                    "chowder_number": chowder_number,
                    "ex_div_date": s.get("ex_div_date"),
                    "pay_date": s.get("pay_date"),
                    "div_frequency": s.get("div_frequency"),
                    "nav_value": nav_value,
                    "nav_discount_pct": nav_discount_pct,
                    "sma_50": s.get("sma_50"),
                    "sma_200": s.get("sma_200"),
                    "rsi_14d": s.get("rsi_14d"),
                    "support_level": support_level,
                    "resistance_level": resistance_level,
                    "yield_5yr_avg": yield_5yr_avg,
                    "div_cagr_3yr": s.get("div_cagr_3yr"),
                    "div_cagr_10yr": s.get("div_cagr_10yr"),
                    "consecutive_growth_yrs": s.get("consecutive_growth_yrs"),
                    "buyback_yield": s.get("buyback_yield"),
                    "coverage_metric_type": cov_metric_type,
                    "interest_coverage_ratio": s.get("interest_coverage_ratio"),
                    "net_debt_ebitda": s.get("net_debt_ebitda"),
                    "free_cash_flow_yield": s.get("free_cash_flow_yield"),
                    "return_on_equity": s.get("return_on_equity"),
                    "credit_rating": s.get("credit_rating"),
                    "debt_to_equity": s.get("debt_to_equity"),
                    "expense_ratio": p.get("expense_ratio"),
                    "fmp_sector":   "Fixed Income" if _is_cusip(sym) else p.get("sector")   or None,
                    "fmp_industry": "Corporate Bond" if _is_cusip(sym) else p.get("industry") or None,
                    "track_reason": track_reason,
                    "snapshot_date": today,
                    "fetched_at": now,
                },
            )
            upserted += 1
        except Exception as exc:
            logger.warning("Cache upsert failed for %s: %s", sym, exc)
            try:
                db.rollback()
            except Exception:
                pass

    try:
        db.commit()
    except Exception as exc:
        logger.error("market_data_cache commit failed: %s", exc)
        db.rollback()
    logger.info("Upserted %d rows into market_data_cache", upserted)

    # Backfill name / sector / industry on the securities table from FMP profile data.
    # Uses FMP symbol → orig_sym mapping so CUSIPs and /PR preferred tickers resolve correctly.
    # Always overwrites with FMP authoritative data when available; preserves existing value
    # only when FMP returns nothing for that field.
    sec_updated = 0
    for fmp_sym, orig_sym in fmp_lookup.items():
        p = profiles.get(orig_sym, {})
        # FMP stable /profile uses "companyName"; older v3 snapshots may use "name" — try both
        name = p.get("companyName") or p.get("name") or None
        sector = p.get("sector") or None
        industry = p.get("industry") or None
        if not name and not sector and not industry:
            logger.debug("FMP returned no name/sector/industry for %s (fmp=%s)", orig_sym, fmp_sym)
            continue
        logger.debug("Securities backfill %s → name=%r sector=%r", orig_sym, name, sector)
        try:
            db.execute(
                text("""
                    UPDATE platform_shared.securities
                    SET
                        name     = COALESCE(:name,     NULLIF(name, '')),
                        sector   = COALESCE(:sector,   NULLIF(sector, '')),
                        industry = COALESCE(:industry, NULLIF(industry, ''))
                    WHERE symbol = :symbol
                """),
                {"symbol": orig_sym, "name": name, "sector": sector, "industry": industry},
            )
            sec_updated += 1
        except Exception as exc:
            logger.debug("Securities name/sector update failed for %s: %s", orig_sym, exc)
            try:
                db.rollback()
            except Exception:
                pass
    if sec_updated:
        try:
            db.commit()
            logger.info("Backfilled name/sector/industry for %d securities", sec_updated)
        except Exception as exc:
            logger.warning("Securities backfill commit failed: %s", exc)
            db.rollback()

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
