#!/usr/bin/env python3
"""
Agent 05 — Tax Optimization Service
Migration script (no-op)

Agent 05 creates NO new database tables.
It reads from the existing shared platform DB (user_preferences table).
This script exists only to satisfy the platform's deploy checklist and
to provide a hook for future lightweight schema changes if needed.

Run from service root:
    python scripts/migrate.py
"""
import sys
import os

sys.path.insert(0, "..")

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def run_migrations() -> None:
    logger.info("Agent 05 — Tax Optimization Service migration check")
    logger.info("No schema changes required — service is read-only.")
    logger.info(
        "This service reads from: user_preferences (existing table, no modifications)."
    )
    logger.info("Migration complete — no-op.")


if __name__ == "__main__":
    run_migrations()
