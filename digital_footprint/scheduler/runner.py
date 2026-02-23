"""Scheduler runner: determines overdue jobs and executes them."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scheduler.jobs import (
    JOB_INTERVALS,
    JobResult,
    job_breach_recheck,
    job_dark_web_monitor,
    job_verify_removals,
    job_generate_report,
)

logger = logging.getLogger("digital_footprint.scheduler")

JOB_FUNCTIONS = {
    "breach_recheck": job_breach_recheck,
    "dark_web_monitor": job_dark_web_monitor,
    "verify_removals": job_verify_removals,
    "generate_report": job_generate_report,
}


def get_overdue_jobs(db: Database) -> list[str]:
    """Return list of job names that are overdue for execution."""
    overdue = []
    now = datetime.now()

    for job_name, interval_days in JOB_INTERVALS.items():
        last_run = db.get_last_run(job_name)
        if last_run is None:
            overdue.append(job_name)
            continue

        last_time = datetime.strptime(last_run["started_at"], "%Y-%m-%d %H:%M:%S")
        if now - last_time >= timedelta(days=interval_days):
            overdue.append(job_name)

    return overdue


def run_scheduled_jobs(db: Database, config: Config) -> list[JobResult]:
    """Run all overdue jobs and store results."""
    overdue = get_overdue_jobs(db)
    results = []

    for job_name in overdue:
        if job_name not in JOB_FUNCTIONS:
            continue

        logger.info(f"Running scheduled job: {job_name}")
        run_id = db.insert_scheduled_run(
            job_name=job_name,
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        try:
            result = JOB_FUNCTIONS[job_name](db, config)
            db.update_scheduled_run(
                run_id,
                status=result.status,
                completed_at=result.completed_at,
                details=json.dumps(result.details),
            )
            results.append(result)
            logger.info(f"Job {job_name} completed: {result.status}")
        except Exception as e:
            error_msg = str(e)
            db.update_scheduled_run(
                run_id,
                status="failed",
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error=error_msg,
            )
            results.append(JobResult(
                job_name=job_name,
                started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status="failed",
                error=error_msg,
            ))
            logger.error(f"Job {job_name} failed: {e}")

    return results


def get_schedule_status(db: Database) -> dict:
    """Get status of all scheduled jobs."""
    now = datetime.now()
    jobs = []

    for job_name, interval_days in JOB_INTERVALS.items():
        last_run = db.get_last_run(job_name)
        if last_run is None:
            jobs.append({
                "name": job_name,
                "interval_days": interval_days,
                "last_run": None,
                "next_due": "now",
                "status": "never_run",
            })
        else:
            last_time = datetime.strptime(last_run["started_at"], "%Y-%m-%d %H:%M:%S")
            next_due = last_time + timedelta(days=interval_days)
            is_overdue = now >= next_due
            jobs.append({
                "name": job_name,
                "interval_days": interval_days,
                "last_run": last_run["started_at"],
                "next_due": next_due.strftime("%Y-%m-%d %H:%M:%S"),
                "status": last_run.get("status", "unknown"),
                "overdue": is_overdue,
            })

    recent = db.get_run_history(limit=10)
    return {
        "jobs": jobs,
        "recent_runs": recent,
    }
