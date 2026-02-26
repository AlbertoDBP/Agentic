"""
Agent 02 — Newsletter Ingestion Service
Script: Register Prefect flow schedules

Registers two flows with their production schedules:
  harvester_flow    — Tuesday + Friday 7AM ET  (0 7 * * 2,5)
  intelligence_flow — Monday 6AM ET            (0 6 * * 1)

Usage:
    python scripts/prefect_schedule.py
    python scripts/prefect_schedule.py --dry-run
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


FLOW_SCHEDULES = [
    {
        "name": "agent-02-harvester",
        "module": "app.flows.harvester_flow",
        "flow_fn": "harvester_flow",
        "cron": "0 7 * * 2,5",          # Tuesday + Friday 7AM ET
        "timezone": "America/New_York",
        "description": "Ingest SA analyst articles + extract income signals",
    },
    {
        "name": "agent-02-intelligence",
        "module": "app.flows.intelligence_flow",
        "flow_fn": "intelligence_flow",
        "cron": "0 6 * * 1",            # Monday 6AM ET
        "timezone": "America/New_York",
        "description": "Staleness decay + backtest + philosophy + consensus rebuild",
    },
]


def register_schedules(dry_run: bool = False):
    """Register all flow schedules with Prefect server."""
    try:
        from prefect.client.orchestration import get_client
        from prefect.deployments import Deployment
        from prefect.server.schemas.schedules import CronSchedule
    except ImportError as e:
        logger.error(f"Prefect not available: {e}")
        sys.exit(1)

    logger.info(f"Registering {len(FLOW_SCHEDULES)} flow schedules...")

    for schedule_def in FLOW_SCHEDULES:
        name = schedule_def["name"]
        cron = schedule_def["cron"]
        tz = schedule_def["timezone"]

        if dry_run:
            logger.info(f"  [DRY RUN] Would register: {name} | cron={cron} | tz={tz}")
            continue

        try:
            # Dynamically import the flow function
            import importlib
            module = importlib.import_module(schedule_def["module"])
            flow_fn = getattr(module, schedule_def["flow_fn"])

            deployment = Deployment.build_from_flow(
                flow=flow_fn,
                name=name,
                schedule=CronSchedule(cron=cron, timezone=tz),
                description=schedule_def["description"],
            )
            deployment_id = deployment.apply()

            logger.info(
                f"  ✅ Registered: {name} | cron={cron} | id={deployment_id}"
            )

        except Exception as e:
            logger.error(f"  ❌ Failed to register {name}: {e}")

    if not dry_run:
        logger.info("Schedule registration complete.")
        logger.info("Verify at: http://localhost:4200 (Prefect UI)")
    else:
        logger.info("Dry run complete — no changes made.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register Prefect flow schedules")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show schedules without registering")
    args = parser.parse_args()
    register_schedules(dry_run=args.dry_run)
