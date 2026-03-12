"""
Agent 03 — Income Scoring Service
Weight Profile Loader: loads class-specific pillar weight profiles from DB.

Provides a 5-minute in-process cache to avoid DB round-trips on every score.
Falls back to the v1.0 universal weights (40/40/20) when a class has no
profile in the database.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ScoringWeightProfile

logger = logging.getLogger(__name__)

# ── Default fallback (v1.0 universal weights) ─────────────────────────────────

_DEFAULT_PROFILE = {
    "asset_class": "DEFAULT",
    "version": 0,
    "source": "FALLBACK",
    "weight_yield": 40,
    "weight_durability": 40,
    "weight_technical": 20,
    "yield_sub_weights": {
        "payout_sustainability": 40,
        "yield_vs_market": 35,
        "fcf_coverage": 25,
    },
    "durability_sub_weights": {
        "debt_safety": 40,
        "dividend_consistency": 35,
        "volatility_score": 25,
    },
    "technical_sub_weights": {
        "price_momentum": 60,
        "price_range_position": 40,
    },
}

_CACHE_TTL_SECONDS = 300  # 5 minutes


def _profile_to_dict(profile: ScoringWeightProfile) -> dict:
    return {
        "id": str(profile.id),
        "asset_class": profile.asset_class,
        "version": profile.version,
        "source": profile.source,
        "weight_yield": profile.weight_yield,
        "weight_durability": profile.weight_durability,
        "weight_technical": profile.weight_technical,
        "yield_sub_weights": profile.yield_sub_weights,
        "durability_sub_weights": profile.durability_sub_weights,
        "technical_sub_weights": profile.technical_sub_weights,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "activated_at": profile.activated_at.isoformat() if profile.activated_at else None,
    }


class WeightProfileLoader:
    """
    Loads and caches active ScoringWeightProfile rows.

    One instance per process is sufficient; the cache is an in-memory dict
    keyed by asset_class. Cache entries expire after CACHE_TTL_SECONDS.
    """

    def __init__(self):
        self._cache: dict[str, tuple[dict, datetime]] = {}
        # { asset_class: (profile_dict, expires_at) }

    def get_active_profile(self, asset_class: str, db: Session) -> dict:
        """
        Return the active weight profile for the given asset class.

        1. Check in-memory cache — return if still valid.
        2. Query DB for the active profile.
        3. If not found in DB, return the universal fallback (40/40/20).
        """
        ac = asset_class.upper()
        now = datetime.now(timezone.utc)

        # Cache hit
        if ac in self._cache:
            cached_profile, expires_at = self._cache[ac]
            if now < expires_at:
                return cached_profile

        # Cache miss or expired — query DB
        try:
            profile = (
                db.query(ScoringWeightProfile)
                .filter(
                    ScoringWeightProfile.asset_class == ac,
                    ScoringWeightProfile.is_active.is_(True),
                )
                .first()
            )
        except Exception as exc:
            logger.warning(
                "WeightProfileLoader: DB query failed for %s, using fallback: %s", ac, exc
            )
            profile = None

        if profile is None:
            logger.debug(
                "No active weight profile for %s — using universal fallback (40/40/20)", ac
            )
            result = dict(_DEFAULT_PROFILE, asset_class=ac)
        else:
            result = _profile_to_dict(profile)

        # Store in cache
        self._cache[ac] = (result, now + timedelta(seconds=_CACHE_TTL_SECONDS))
        return result

    def invalidate(self, asset_class: Optional[str] = None) -> None:
        """Invalidate cache for one class (or all if asset_class is None)."""
        if asset_class is None:
            self._cache.clear()
            logger.debug("WeightProfileLoader: full cache invalidated")
        else:
            self._cache.pop(asset_class.upper(), None)
            logger.debug("WeightProfileLoader: cache invalidated for %s", asset_class)

    def get_all_active_profiles(self, db: Session) -> list[dict]:
        """Return all active profiles from DB (bypasses cache, for admin endpoints)."""
        try:
            profiles = (
                db.query(ScoringWeightProfile)
                .filter(ScoringWeightProfile.is_active.is_(True))
                .order_by(ScoringWeightProfile.asset_class)
                .all()
            )
            return [_profile_to_dict(p) for p in profiles]
        except Exception as exc:
            logger.warning("WeightProfileLoader: get_all_active_profiles failed: %s", exc)
            return []


# ── Module-level singleton ────────────────────────────────────────────────────
# Imported by API layer; single instance across all requests in the process.

weight_profile_loader = WeightProfileLoader()
