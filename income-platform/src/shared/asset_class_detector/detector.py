"""
AssetClassDetector
Main entry point for the shared asset class detection utility.
Importable by any agent: from shared.asset_class_detector import AssetClassDetector
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from .taxonomy import AssetClass, AssetClassInfo, ASSET_CLASS_HIERARCHY
from .rule_matcher import RuleMatcher, MatchResult
from .seed_rules import SEED_RULES

logger = logging.getLogger(__name__)

ENRICHMENT_CONFIDENCE_THRESHOLD = 0.70


@dataclass
class DetectionResult:
    ticker: str
    asset_class: AssetClass
    parent_class: str
    confidence: float
    is_hybrid: bool
    characteristics: dict
    matched_rules: List[dict]
    source: str                    # "rule_engine_v1" | "override" | "fallback"
    needs_enrichment: bool = False  # True if confidence < threshold before enrichment


class AssetClassDetector:
    """
    Shared utility for asset class detection.
    Uses rule-based matching (v1). ML layer added in v2.

    Usage:
        detector = AssetClassDetector()                    # uses seed rules
        detector = AssetClassDetector(rules=db_rules)     # uses DB rules
        result = detector.detect("JEPI", security_data)
    """

    def __init__(self, rules: Optional[List[dict]] = None):
        self.rules = rules if rules is not None else SEED_RULES
        self.matcher = RuleMatcher(self.rules)

    def detect(self, ticker: str, security_data: Optional[dict] = None) -> DetectionResult:
        """
        Detect asset class for a ticker.

        Args:
            ticker: Stock/ETF ticker symbol
            security_data: Optional dict with known fields (sector, security_type, etc.)
                           If None, falls back to ticker patterns only.

        Returns:
            DetectionResult with asset_class, confidence, characteristics
        """
        data = security_data or {}
        ticker = ticker.upper().strip()

        # Run rule matching
        matches: List[MatchResult] = self.matcher.match(ticker, data)

        if not matches:
            return self._unknown_result(ticker)

        top = matches[0]
        needs_enrichment = top.total_confidence < ENRICHMENT_CONFIDENCE_THRESHOLD

        info = ASSET_CLASS_HIERARCHY.get(top.asset_class, ASSET_CLASS_HIERARCHY[AssetClass.UNKNOWN])

        return DetectionResult(
            ticker=ticker,
            asset_class=top.asset_class,
            parent_class=info.parent_class.value,
            confidence=top.total_confidence,
            is_hybrid=info.is_hybrid,
            characteristics=self._build_characteristics(info),
            matched_rules=[
                {"rule_type": m.rule_type, "matched_on": m.matched_on, "confidence": m.confidence}
                for m in top.matches
            ],
            source="rule_engine_v1",
            needs_enrichment=needs_enrichment,
        )

    def detect_with_fallback(self, ticker: str, security_data: Optional[dict] = None) -> DetectionResult:
        """
        Same as detect() but never returns UNKNOWN —
        defaults to DIVIDEND_STOCK if nothing matches.
        Used by agents that require a classification to proceed.
        """
        result = self.detect(ticker, security_data)
        if result.asset_class == AssetClass.UNKNOWN:
            logger.warning(f"No classification for {ticker} — defaulting to DIVIDEND_STOCK")
            info = ASSET_CLASS_HIERARCHY[AssetClass.DIVIDEND_STOCK]
            return DetectionResult(
                ticker=ticker,
                asset_class=AssetClass.DIVIDEND_STOCK,
                parent_class=info.parent_class.value,
                confidence=0.30,
                is_hybrid=False,
                characteristics=self._build_characteristics(info),
                matched_rules=[],
                source="fallback",
                needs_enrichment=True,
            )
        return result

    def _build_characteristics(self, info: AssetClassInfo) -> dict:
        return {
            "income_type": info.income_type,
            "tax_treatment": info.tax_treatment,
            "valuation_method": info.valuation_method,
            "rate_sensitivity": info.rate_sensitivity,
            "principal_at_risk": info.principal_at_risk,
            "nav_erosion_tracking": info.nav_erosion_tracking,
            "coverage_ratio_required": info.coverage_ratio_required,
            "preferred_account": info.preferred_account,
        }

    def _unknown_result(self, ticker: str) -> DetectionResult:
        info = ASSET_CLASS_HIERARCHY[AssetClass.UNKNOWN]
        return DetectionResult(
            ticker=ticker,
            asset_class=AssetClass.UNKNOWN,
            parent_class=info.parent_class.value,
            confidence=0.0,
            is_hybrid=False,
            characteristics=self._build_characteristics(info),
            matched_rules=[],
            source="rule_engine_v1",
            needs_enrichment=True,
        )
