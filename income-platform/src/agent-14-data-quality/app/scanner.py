# src/agent-14-data-quality/app/scanner.py
"""Completeness scan — identifies missing required fields per asset class."""
import logging
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Allowlist of columns that exist in market_data_cache and can be used in dynamic SQL.
_VALID_FIELD_NAMES: frozenset[str] = frozenset({
    "price", "sma_50", "sma_200", "rsi_14d", "week52_high", "week52_low",
    "dividend_yield", "payout_ratio", "pe_ratio", "forward_pe",
    "debt_to_equity", "interest_coverage_ratio", "price_to_book",
    "profit_margin", "free_cash_flow_yield",
    "chowder_number", "consecutive_growth_yrs",
})


def _validate_field_name(field_name: str) -> None:
    """Raise ValueError if field_name is not in the known allowlist."""
    if field_name not in _VALID_FIELD_NAMES:
        raise ValueError(f"Unknown field_name: {field_name!r}")


ASSET_TYPE_TO_CLASS: dict[str, str] = {
    "DIVIDEND_STOCK":  "CommonStock",
    "ETF":             "ETF",
    "COVERED_CALL_ETF":"ETF",
    "CEF":             "CEF",
    "BDC":             "BDC",
    "EQUITY_REIT":     "REIT",
    "MORTGAGE_REIT":   "REIT",
    "MLP":             "MLP",
    "PREFERRED_STOCK": "Preferred",
    "BOND":            "Bond",
    "CORPORATE_BOND":  "Bond",
    "TREASURY_BOND":   "Bond",
}


def resolve_asset_class(asset_type: Optional[str]) -> Optional[str]:
    return ASSET_TYPE_TO_CLASS.get(asset_type or "")


def compute_severity(db: Session, symbol: str, field_name: str, asset_class: str) -> str:
    """Critical if any peer of same asset_class has the field populated; else warning."""
    _validate_field_name(field_name)
    peer_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM platform_shared.market_data_cache m
            JOIN platform_shared.securities s ON s.symbol = m.symbol
            WHERE s.asset_type = ANY(:types)
              AND m.symbol != :symbol
              AND m.""" + field_name + """ IS NOT NULL
              AND m.is_tracked = TRUE
        """),
        {"types": _asset_class_to_types(asset_class), "symbol": symbol},
    ).scalar()
    return "critical" if (peer_count or 0) > 0 else "warning"


def _asset_class_to_types(asset_class: str) -> list[str]:
    """Reverse mapping: asset_class → list of asset_type values."""
    return [k for k, v in ASSET_TYPE_TO_CLASS.items() if v == asset_class]


def run_scan(db: Session) -> dict:
    """
    Full completeness scan.
    Returns summary: {symbols_scanned, issues_created, issues_resolved}.
    """
    # Load requirements indexed by asset_class
    reqs_rows = db.execute(text("""
        SELECT asset_class, field_name, required
        FROM platform_shared.field_requirements
        WHERE required = TRUE
    """)).fetchall()
    requirements: dict[str, list[str]] = {}
    for r in reqs_rows:
        requirements.setdefault(r.asset_class, []).append(r.field_name)

    # Load exemptions as a set of (symbol, field_name) tuples
    exempt_rows = db.execute(text("""
        SELECT symbol, field_name FROM platform_shared.data_quality_exemptions
    """)).fetchall()
    exemptions = {(r.symbol, r.field_name) for r in exempt_rows}

    # Get tracked symbols with their asset_type
    symbols = db.execute(text("""
        SELECT m.symbol, s.asset_type
        FROM platform_shared.market_data_cache m
        LEFT JOIN platform_shared.securities s ON s.symbol = m.symbol
        WHERE m.is_tracked = TRUE
    """)).fetchall()

    issues_created = 0
    issues_resolved = 0

    for sym_row in symbols:
        symbol = sym_row.symbol
        asset_class = resolve_asset_class(sym_row.asset_type)
        if not asset_class:
            logger.debug(f"Skipping {symbol}: asset_type={sym_row.asset_type!r} not mapped")
            continue

        field_list = requirements.get(asset_class, [])
        for field_name in field_list:
            if (symbol, field_name) in exemptions:
                continue

            # Check if field is populated in market_data_cache
            _validate_field_name(field_name)
            result = db.execute(
                text(f"SELECT {field_name} FROM platform_shared.market_data_cache WHERE symbol = :s"),
                {"s": symbol},
            ).fetchone()

            field_value = getattr(result, field_name, None) if result else None

            if field_value is None or field_value == 0:
                # Field is missing — upsert into issues
                existing = db.execute(
                    text("SELECT id, status FROM platform_shared.data_quality_issues "
                         "WHERE symbol = :s AND field_name = :f"),
                    {"s": symbol, "f": field_name},
                ).fetchone()

                if existing and existing.status == "resolved":
                    # Was resolved but now missing again — reopen
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='missing', resolved_at=NULL, attempt_count=0, "
                             "updated_at=NOW() WHERE id=:id"),
                        {"id": existing.id},
                    )
                    issues_created += 1
                elif not existing:
                    severity = compute_severity(db, symbol, field_name, asset_class)
                    db.execute(
                        text("""
                            INSERT INTO platform_shared.data_quality_issues
                                (symbol, field_name, asset_class, status, severity)
                            VALUES (:s, :f, :ac, 'missing', :sev)
                            ON CONFLICT (symbol, field_name) DO UPDATE
                                SET status='missing', severity=:sev, updated_at=NOW()
                        """),
                        {"s": symbol, "f": field_name, "ac": asset_class, "sev": severity},
                    )
                    issues_created += 1
            else:
                # Field is present — mark any open issue resolved
                resolve_result = db.execute(
                    text("""
                        UPDATE platform_shared.data_quality_issues
                        SET status='resolved', resolved_at=NOW(), updated_at=NOW()
                        WHERE symbol=:s AND field_name=:f AND status NOT IN ('resolved','unresolvable')
                    """),
                    {"s": symbol, "f": field_name},
                )
                if resolve_result.rowcount > 0:
                    issues_resolved += 1

    db.commit()
    logger.info(f"Scan complete: {len(symbols)} symbols, {issues_created} issues, {issues_resolved} resolved")
    return {
        "symbols_scanned": len(symbols),
        "issues_created": issues_created,
        "issues_resolved": issues_resolved,
    }
