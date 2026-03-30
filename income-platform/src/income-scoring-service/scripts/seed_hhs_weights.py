# scripts/seed_hhs_weights.py
"""Seed default HHS weight profiles. Run once after migration."""
import asyncio
import asyncpg
from app.scoring.hhs_weights import _DEFAULTS, _DEFAULT_UNSAFE_THRESHOLD
from app.config import settings

async def seed():
    conn = await asyncpg.connect(settings.database_url)
    for ac, income_w in _DEFAULTS.items():
        for rp in ["conservative", "moderate", "aggressive"]:
            await conn.execute("""
                INSERT INTO platform_shared.hhs_weight_profiles
                    (asset_class, risk_profile, income_weight, durability_weight,
                     unsafe_threshold, source, created_by, activated_at)
                VALUES ($1, $2, $3, $4, $5, 'INITIAL_SEED', 'seed_script', NOW())
                ON CONFLICT DO NOTHING
            """, ac, rp, income_w, 100 - income_w, _DEFAULT_UNSAFE_THRESHOLD)
    await conn.close()
    print("HHS weight profiles seeded.")

if __name__ == "__main__":
    asyncio.run(seed())
