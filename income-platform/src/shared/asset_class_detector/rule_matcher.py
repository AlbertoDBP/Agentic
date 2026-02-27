"""
Rule Matcher
Applies 4 rule types against security data and returns confidence scores per asset class.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from .taxonomy import AssetClass

logger = logging.getLogger(__name__)


@dataclass
class RuleMatch:
    asset_class: AssetClass
    rule_type: str
    confidence: float
    matched_on: str   # human-readable description of what matched


@dataclass
class MatchResult:
    asset_class: AssetClass
    total_confidence: float
    matches: List[RuleMatch] = field(default_factory=list)


class RuleMatcher:
    """
    Applies seeded/DB rules against security data.
    Returns ranked list of asset class matches with confidence scores.
    """

    def __init__(self, rules: List[dict]):
        """
        rules: list of rule dicts (from DB or seed_rules.SEED_RULES)
        Each rule: {asset_class, rule_type, rule_config, priority, confidence_weight}
        """
        self.rules = sorted(rules, key=lambda r: r["priority"])

    def match(self, ticker: str, security_data: dict) -> List[MatchResult]:
        """
        Match security_data against all rules.
        Returns list of MatchResult sorted by total_confidence desc.
        """
        scores: Dict[str, List[RuleMatch]] = {}

        for rule in self.rules:
            asset_class = rule["asset_class"]
            rule_type = rule["rule_type"]
            config = rule["rule_config"]
            weight = rule["confidence_weight"]

            match = self._apply_rule(ticker, security_data, rule_type, config, weight)
            if match:
                match.asset_class = AssetClass(asset_class)
                if asset_class not in scores:
                    scores[asset_class] = []
                scores[asset_class].append(match)

        results = []
        for ac, matches in scores.items():
            # Combine confidences: max of individual matches (not additive)
            # to prevent stacking multiple weak signals into false certainty
            total = min(max(m.confidence for m in matches) + 0.05 * (len(matches) - 1), 0.99)
            results.append(MatchResult(
                asset_class=AssetClass(ac),
                total_confidence=round(total, 3),
                matches=matches,
            ))

        return sorted(results, key=lambda r: r.total_confidence, reverse=True)

    def _apply_rule(
        self,
        ticker: str,
        data: dict,
        rule_type: str,
        config: dict,
        weight: float,
    ) -> Optional[RuleMatch]:
        """Dispatch to correct rule handler."""
        handlers = {
            "ticker_pattern": self._ticker_pattern,
            "sector": self._sector_match,
            "feature": self._feature_match,
            "metadata": self._metadata_match,
        }
        handler = handlers.get(rule_type)
        if not handler:
            logger.warning(f"Unknown rule_type: {rule_type}")
            return None
        return handler(ticker, data, config, weight)

    def _ticker_pattern(self, ticker: str, data: dict, config: dict, weight: float) -> Optional[RuleMatch]:
        t = ticker.upper()

        # Exact ticker list
        if t in [x.upper() for x in config.get("tickers", [])]:
            return RuleMatch(
                asset_class=AssetClass.UNKNOWN,
                rule_type="ticker_pattern",
                confidence=weight,
                matched_on=f"ticker '{ticker}' in known list",
            )

        # Suffix patterns
        for suffix in config.get("suffixes", []):
            if t.endswith(suffix.upper()):
                return RuleMatch(
                    asset_class=AssetClass.UNKNOWN,
                    rule_type="ticker_pattern",
                    confidence=weight,
                    matched_on=f"ticker suffix '{suffix}'",
                )

        # Prefix patterns
        for prefix in config.get("prefixes", []):
            if t.startswith(prefix.upper()):
                return RuleMatch(
                    asset_class=AssetClass.UNKNOWN,
                    rule_type="ticker_pattern",
                    confidence=weight,
                    matched_on=f"ticker prefix '{prefix}'",
                )

        return None

    def _sector_match(self, ticker: str, data: dict, config: dict, weight: float) -> Optional[RuleMatch]:
        sector = data.get("sector", "")
        if not sector:
            return None

        for s in config.get("sectors", []):
            if s.lower() in sector.lower():
                return RuleMatch(
                    asset_class=AssetClass.UNKNOWN,
                    rule_type="sector",
                    confidence=weight,
                    matched_on=f"sector '{sector}' matches '{s}'",
                )

        return None

    def _feature_match(self, ticker: str, data: dict, config: dict, weight: float) -> Optional[RuleMatch]:
        matches = []

        # Boolean flags
        for key in ["options_strategy_present", "is_etf", "fixed_dividend",
                    "par_value_exists", "has_maturity_date", "coupon_rate_exists",
                    "is_common_stock", "contains_mortgage", "nav_erosion_tracking"]:
            if config.get(key) and data.get(key):
                matches.append(key)

        # Numeric minimums
        for key, min_val in [
            ("dividend_yield_min", data.get("dividend_yield", 0)),
            ("min_payout_ratio", data.get("payout_ratio", 0)),
            ("leverage_ratio_min", data.get("leverage_ratio", 0)),
        ]:
            if key in config and min_val >= config[key]:
                matches.append(f"{key}>={config[key]}")

        # Numeric maximums
        for key, max_val in [
            ("payout_ratio_max", data.get("payout_ratio", 1)),
        ]:
            if key in config and max_val <= config[key]:
                matches.append(f"{key}<={config[key]}")

        # Sector string match
        if "sector" in config and config["sector"]:
            data_sector = data.get("sector", "")
            if config["sector"].lower() in data_sector.lower():
                matches.append(f"sector={config['sector']}")

        if not matches:
            return None

        # Partial credit: scale confidence by fraction of features matched
        feature_count = sum(1 for k in config if k not in ("sector",))
        hit_ratio = len(matches) / max(feature_count, 1)
        confidence = round(weight * hit_ratio, 3)

        if confidence < 0.30:
            return None

        return RuleMatch(
            asset_class=AssetClass.UNKNOWN,
            rule_type="feature",
            confidence=confidence,
            matched_on=f"features: {', '.join(matches)}",
        )

    def _metadata_match(self, ticker: str, data: dict, config: dict, weight: float) -> Optional[RuleMatch]:
        matches = []

        for meta_key, allowed_values in config.items():
            if not isinstance(allowed_values, list):
                continue
            data_val = str(data.get(meta_key, "")).lower()
            if any(v.lower() in data_val for v in allowed_values):
                matches.append(f"{meta_key}='{data.get(meta_key)}'")

        if not matches:
            return None

        return RuleMatch(
            asset_class=AssetClass.UNKNOWN,
            rule_type="metadata",
            confidence=weight,
            matched_on=f"metadata: {', '.join(matches)}",
        )
