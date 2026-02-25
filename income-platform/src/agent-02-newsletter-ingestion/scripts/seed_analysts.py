"""
Agent 02 — Newsletter Ingestion Service
Seed: Insert test analysts into the analysts table

Test authors:
  - SA Author ID 16392    (Author 1)
  - SA Author ID 49926601 (Author 2)

Usage:
    python scripts/seed_analysts.py
    python scripts/seed_analysts.py --dry-run
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_ANALYSTS = [
    {
        "sa_publishing_id": "96726",
        "display_name": "Test Analyst A (SA ID 96726)",
        "is_active": True,
        "config": {
            "fetch_limit": 5,       # small fetch for test runs
            "aging_days": 365,
            "halflife_days": 180,
        }
    },
    {
        "sa_publishing_id": "104956",
        "display_name": "Test Analyst B (SA ID 104956)",
        "is_active": True,
        "config": {
            "fetch_limit": 5,
            "aging_days": 365,
            "halflife_days": 180,
        }
    },
]


def seed_analysts(dry_run: bool = False):
    from app.database import get_db_context
    from app.models.models import Analyst
    from sqlalchemy import text

    logger.info(f"Seeding {len(TEST_ANALYSTS)} test analysts...")

    with get_db_context() as db:
        for analyst_data in TEST_ANALYSTS:
            sa_id = analyst_data["sa_publishing_id"]

            # Check if already exists
            existing = (
                db.query(Analyst)
                .filter(Analyst.sa_publishing_id == sa_id)
                .first()
            )

            if existing:
                logger.info(f"  ⏭  Skipping SA ID {sa_id} — already in DB (id={existing.id})")
                continue

            if dry_run:
                logger.info(f"  [DRY RUN] Would insert: {analyst_data['display_name']} ({sa_id})")
                continue

            analyst = Analyst(**analyst_data)
            db.add(analyst)
            db.flush()
            logger.info(f"  ✅ Inserted: {analyst_data['display_name']} → DB id={analyst.id}")

    if not dry_run:
        logger.info("Seed complete.")
    else:
        logger.info("Dry run complete — no changes made.")


def verify_seed():
    """Print current analysts table contents."""
    from app.database import get_db_context
    from app.models.models import Analyst

    with get_db_context() as db:
        analysts = db.query(Analyst).order_by(Analyst.id).all()
        logger.info(f"\nCurrent analysts table ({len(analysts)} rows):")
        for a in analysts:
            logger.info(
                f"  id={a.id} | sa_id={a.sa_publishing_id} | "
                f"name='{a.display_name}' | active={a.is_active} | "
                f"articles={a.article_count}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed test analysts into Agent 02 DB")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be inserted without writing to DB")
    parser.add_argument("--verify", action="store_true",
                        help="Print current analysts table and exit")
    args = parser.parse_args()

    if args.verify:
        verify_seed()
    else:
        seed_analysts(dry_run=args.dry_run)
        verify_seed()
