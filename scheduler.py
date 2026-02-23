#!/usr/bin/env python3
"""
Cron-friendly scheduler for Digital Footprint.

Checks for overdue jobs and runs them. Exits 0 on success, 1 on failure.

Usage:
    python scheduler.py

Cron example (every 6 hours):
    0 */6 * * * /path/to/venv/bin/python /path/to/scheduler.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from digital_footprint.config import get_config
from digital_footprint.db import Database
from digital_footprint.broker_registry import load_all_brokers
from digital_footprint.scheduler import runner


def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure logging to file and stderr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "scheduler.log"

    logger = logging.getLogger("digital_footprint.scheduler")
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(str(log_path))
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    ))
    logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    return logger


def main() -> int:
    """Run overdue scheduled jobs. Returns 0 on success, 1 on failure."""
    config = get_config()
    db = Database(config)
    db.initialize()

    # Load brokers
    brokers = load_all_brokers(config.brokers_dir)
    for broker in brokers:
        db.insert_broker(broker)

    logger = setup_logging(config.db_path.parent)

    overdue = runner.get_overdue_jobs(db)
    if not overdue:
        logger.info("No overdue jobs.")
        db.close()
        return 0

    logger.info(f"Overdue jobs: {', '.join(overdue)}")
    results = runner.run_scheduled_jobs(db, config)

    failed = [r for r in results if r.status == "failed"]
    succeeded = [r for r in results if r.status in ("success", "skipped")]

    logger.info(f"Completed: {len(succeeded)} succeeded, {len(failed)} failed")
    for r in results:
        logger.info(json.dumps({
            "job": r.job_name,
            "status": r.status,
            "details": r.details,
        }))

    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
