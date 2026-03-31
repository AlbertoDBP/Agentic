# src/agent-14-data-quality/app/healer.py
"""Self-healing engine — fetches missing fields and writes them back to market_data_cache."""
import logging
from enum import Enum
from typing import Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clients.fmp import FMPHealClient
from app.clients.massive import MASSIVEHealClient
from app.config import settings
from app.scanner import _validate_field_name

logger = logging.getLogger(__name__)


class IssueStatus(str, Enum):
    MISSING = "missing"
    FETCHING = "fetching"
    RESOLVED = "resolved"
    UNRESOLVABLE = "unresolvable"


class HealerEngine:
    def __init__(self, fmp_client: FMPHealClient, massive_client: MASSIVEHealClient):
        self.fmp = fmp_client
        self.massive = massive_client
        self.max_attempts = settings.max_heal_attempts

    def _should_skip(self, symbol: str, field_name: str, exemptions: Set[Tuple[str, str]]) -> bool:
        return (symbol, field_name) in exemptions

    def _fetch(
        self,
        symbol: str,
        field_name: str,
        primary: Optional[str],
        fallback: Optional[str],
    ) -> Tuple[Optional[float], dict, Optional[str]]:
        """Try primary then fallback. Returns (value, diagnostic, source_used)."""
        sources = [(primary, self.fmp if primary == "fmp" else self.massive),
                   (fallback, self.fmp if fallback == "fmp" else self.massive)]
        sources = [(s, c) for s, c in sources if s and c]

        last_diag: dict = {}
        for source_name, client in sources:
            value, diag = client.fetch_field_with_diagnostic(symbol, field_name)
            if value is not None:
                return value, {}, source_name
            last_diag = diag

        return None, last_diag if sources else {"code": "FIELD_NOT_SUPPORTED"}, None

    def run_retry_pass(self, db: Session) -> dict:
        """
        Process all open issues (status='missing' or 'fetching', attempt_count < max).
        Called every 15 minutes.
        """
        # Load exemptions
        exempt_rows = db.execute(
            text("SELECT symbol, field_name FROM platform_shared.data_quality_exemptions")
        ).fetchall()
        exemptions = {(r.symbol, r.field_name) for r in exempt_rows}

        # Load open issues with their fetch sources
        issues = db.execute(text("""
            SELECT i.id, i.symbol, i.field_name, i.asset_class, i.attempt_count,
                   r.fetch_source_primary, r.fetch_source_fallback
            FROM platform_shared.data_quality_issues i
            LEFT JOIN platform_shared.field_requirements r
                   ON r.asset_class = i.asset_class AND r.field_name = i.field_name
            WHERE i.status IN ('missing', 'fetching')
              AND i.attempt_count < :max_attempts
        """), {"max_attempts": self.max_attempts}).fetchall()

        healed = 0
        failed = 0
        escalated = 0

        for issue in issues:
            if self._should_skip(issue.symbol, issue.field_name, exemptions):
                continue

            # Mark as fetching
            db.execute(
                text("UPDATE platform_shared.data_quality_issues "
                     "SET status='fetching', last_attempted_at=NOW(), "
                     "attempt_count=attempt_count+1, updated_at=NOW() WHERE id=:id"),
                {"id": issue.id},
            )
            db.commit()

            value, diag, source_used = self._fetch(
                issue.symbol,
                issue.field_name,
                issue.fetch_source_primary,
                issue.fetch_source_fallback,
            )

            if value is not None:
                # Write healed value back to market_data_cache
                try:
                    _validate_field_name(issue.field_name)
                    db.execute(
                        text(f"UPDATE platform_shared.market_data_cache "
                             f"SET {issue.field_name} = :val WHERE symbol = :s"),
                        {"val": value, "s": issue.symbol},
                    )
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='resolved', resolved_at=NOW(), "
                             "source_used=:src, diagnostic=:diag, updated_at=NOW() WHERE id=:id"),
                        {"src": source_used, "diag": None, "id": issue.id},
                    )
                    healed += 1
                    logger.info(f"Healed {issue.symbol}/{issue.field_name} via {source_used}")
                except Exception as e:
                    logger.error(f"Failed to write healed value for {issue.symbol}/{issue.field_name}: {e}")
                    failed += 1
            else:
                new_attempts = issue.attempt_count + 1
                if new_attempts >= self.max_attempts:
                    # Escalate to unresolvable
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='unresolvable', diagnostic=:diag, updated_at=NOW() WHERE id=:id"),
                        {"diag": diag, "id": issue.id},
                    )
                    logger.warning(
                        f"UNRESOLVABLE: {issue.symbol}/{issue.field_name} — {diag.get('code')}"
                    )
                    escalated += 1
                else:
                    db.execute(
                        text("UPDATE platform_shared.data_quality_issues "
                             "SET status='missing', diagnostic=:diag, updated_at=NOW() WHERE id=:id"),
                        {"diag": diag, "id": issue.id},
                    )
                    failed += 1

            db.commit()

        return {"healed": healed, "failed": failed, "escalated": escalated}
