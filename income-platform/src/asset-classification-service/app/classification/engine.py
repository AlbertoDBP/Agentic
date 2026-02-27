"""
Classification Engine
Orchestrates: detect → enrich (if needed) → benchmarks → tax_profile → persist
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AssetClassification, AssetClassRule, ClassificationOverride
from app.classification.data_client import MarketDataClient
from app.classification.benchmarks import get_benchmark, benchmark_to_dict
from app.classification.tax_profile import build_tax_profile

from shared.asset_class_detector import AssetClassDetector
from shared.asset_class_detector.detector import DetectionResult

logger = logging.getLogger(__name__)


class ClassificationEngine:
    """
    Full classification pipeline for Agent 04.
    Shared AssetClassDetector handles rule matching.
    This engine adds: DB rule loading, enrichment, benchmarks, tax, persistence.
    """

    def __init__(self, db: Session):
        self.db = db
        self.data_client = MarketDataClient()
        self._detector: Optional[AssetClassDetector] = None

    def _get_detector(self) -> AssetClassDetector:
        """Lazy-load detector with DB rules (falls back to seed rules)."""
        if self._detector is None:
            db_rules = self._load_db_rules()
            self._detector = AssetClassDetector(rules=db_rules if db_rules else None)
        return self._detector

    def _load_db_rules(self) -> List[dict]:
        try:
            rows = self.db.query(AssetClassRule).filter(AssetClassRule.active == True).all()
            return [
                {
                    "asset_class": r.asset_class,
                    "rule_type": r.rule_type,
                    "rule_config": r.rule_config,
                    "priority": r.priority,
                    "confidence_weight": r.confidence_weight,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Could not load DB rules, using seed rules: {e}")
            return []

    def get_cached(self, ticker: str) -> Optional[AssetClassification]:
        """Return valid cached classification if < 24hr old."""
        return (
            self.db.query(AssetClassification)
            .filter(
                AssetClassification.ticker == ticker.upper(),
                AssetClassification.valid_until > datetime.utcnow(),
            )
            .order_by(AssetClassification.classified_at.desc())
            .first()
        )

    def get_override(self, ticker: str) -> Optional[ClassificationOverride]:
        """Return active manual override for ticker."""
        now = datetime.utcnow()
        return (
            self.db.query(ClassificationOverride)
            .filter(
                ClassificationOverride.ticker == ticker.upper(),
                ClassificationOverride.effective_from <= now,
                (ClassificationOverride.effective_until == None) |
                (ClassificationOverride.effective_until > now),
            )
            .first()
        )

    async def classify(self, ticker: str, security_data: Optional[dict] = None) -> dict:
        """
        Full classification pipeline.
        Returns complete classification dict ready for API response.
        """
        ticker = ticker.upper().strip()

        # 1. Manual override — highest priority
        override = self.get_override(ticker)
        if override:
            return await self._build_from_override(ticker, override)

        # 2. Cache hit
        cached = self.get_cached(ticker)
        if cached:
            return self._serialise(cached)

        # 3. Rule-based detection
        detector = self._get_detector()
        result: DetectionResult = detector.detect(ticker, security_data or {})

        # 4. Enrichment if confidence below threshold
        if result.needs_enrichment:
            logger.info(f"{ticker}: confidence {result.confidence:.2f} < {settings.enrichment_confidence_threshold} — enriching via Agent 01")
            enriched = await self.data_client.get_enrichment_data(ticker)
            merged = {**(security_data or {}), **enriched}
            result = detector.detect(ticker, merged)

        # 5. Benchmarks + tax profile
        benchmark = get_benchmark(result.asset_class.value)
        tax = build_tax_profile(result.asset_class.value, result.characteristics)

        # 6. Persist
        record = self._persist(ticker, result, benchmark, tax)

        return self._serialise(record)

    async def _build_from_override(self, ticker: str, override: ClassificationOverride) -> dict:
        from shared.asset_class_detector.taxonomy import AssetClass, ASSET_CLASS_HIERARCHY
        ac = AssetClass(override.asset_class)
        info = ASSET_CLASS_HIERARCHY.get(ac)
        characteristics = {
            "income_type": info.income_type if info else "unknown",
            "tax_treatment": info.tax_treatment if info else "unknown",
            "valuation_method": info.valuation_method if info else "unknown",
            "rate_sensitivity": info.rate_sensitivity if info else "unknown",
            "principal_at_risk": info.principal_at_risk if info else True,
            "nav_erosion_tracking": info.nav_erosion_tracking if info else False,
            "coverage_ratio_required": info.coverage_ratio_required if info else False,
            "preferred_account": info.preferred_account if info else "TAXABLE",
        }
        benchmark = get_benchmark(override.asset_class)
        tax = build_tax_profile(override.asset_class, characteristics)

        record = self._persist_override(ticker, override, characteristics, benchmark, tax)
        return self._serialise(record)

    def _persist(self, ticker: str, result: DetectionResult, benchmark, tax: dict) -> AssetClassification:
        record = AssetClassification(
            ticker=ticker,
            asset_class=result.asset_class.value,
            parent_class=result.parent_class,
            confidence=result.confidence,
            is_hybrid=result.is_hybrid,
            characteristics=result.characteristics,
            benchmarks=benchmark_to_dict(benchmark) if benchmark else None,
            sub_scores=None,   # populated by sub_scorer in future phase
            tax_efficiency=tax,
            matched_rules=result.matched_rules,
            source=result.source,
            is_override=False,
            classified_at=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(hours=settings.classification_cache_ttl_hours),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _persist_override(self, ticker, override, characteristics, benchmark, tax) -> AssetClassification:
        record = AssetClassification(
            ticker=ticker,
            asset_class=override.asset_class,
            parent_class="OVERRIDE",
            confidence=1.0,
            is_hybrid=False,
            characteristics=characteristics,
            benchmarks=benchmark_to_dict(benchmark) if benchmark else None,
            sub_scores=None,
            tax_efficiency=tax,
            matched_rules=[],
            source="override",
            is_override=True,
            classified_at=datetime.utcnow(),
            valid_until=None,  # overrides never expire from cache
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _serialise(self, record: AssetClassification) -> dict:
        return {
            "ticker": record.ticker,
            "asset_class": record.asset_class,
            "parent_class": record.parent_class,
            "confidence": record.confidence,
            "is_hybrid": record.is_hybrid,
            "characteristics": record.characteristics,
            "benchmarks": record.benchmarks,
            "sub_scores": record.sub_scores,
            "tax_efficiency": record.tax_efficiency,
            "source": record.source,
            "is_override": record.is_override,
            "classified_at": record.classified_at.isoformat() if record.classified_at else None,
            "valid_until": record.valid_until.isoformat() if record.valid_until else None,
        }
