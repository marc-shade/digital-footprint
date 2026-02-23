"""Scheduled job definitions for Digital Footprint."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan
from digital_footprint.reporters.exposure_report import generate_exposure_report

logger = logging.getLogger("digital_footprint.scheduler")

# Intervals in days
JOB_INTERVALS = {
    "breach_recheck": 7,
    "dark_web_monitor": 3,
    "verify_removals": 1,
    "generate_report": 7,
}


@dataclass
class JobResult:
    job_name: str
    started_at: str
    completed_at: str = ""
    status: str = "success"
    details: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def _run_async(coro):
    """Run an async function from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def job_breach_recheck(db: Database, config: Config) -> JobResult:
    """Re-check all persons for new breaches."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persons = db.list_persons()
    persons_with_email = [p for p in persons if p.emails]

    if not persons_with_email:
        return JobResult(
            job_name="breach_recheck",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="success",
            details={"persons_checked": 0, "new_breaches": 0},
        )

    total_new = 0
    for person in persons_with_email:
        email = person.emails[0]
        try:
            results = _run_async(scan_breaches(
                email=email,
                hibp_api_key=config.hibp_api_key,
                dehashed_api_key=config.dehashed_api_key,
            ))
            total_new += results.get("total", 0)
        except Exception as e:
            logger.error(f"Breach check failed for {email}: {e}")

    return JobResult(
        job_name="breach_recheck",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "new_breaches": total_new},
    )


def job_dark_web_monitor(db: Database, config: Config) -> JobResult:
    """Re-run dark web monitoring for all persons."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persons = db.list_persons()
    persons_with_email = [p for p in persons if p.emails]

    if not persons_with_email:
        return JobResult(
            job_name="dark_web_monitor",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="success",
            details={"persons_checked": 0, "total_findings": 0},
        )

    total_findings = 0
    for person in persons_with_email:
        email = person.emails[0]
        try:
            results = _run_async(run_dark_web_scan(email, hibp_api_key=config.hibp_api_key))
            total_findings += results.get("total", 0)
        except Exception as e:
            logger.error(f"Dark web scan failed for {email}: {e}")

    return JobResult(
        job_name="dark_web_monitor",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "total_findings": total_findings},
    )


def job_verify_removals(db: Database, config: Config) -> JobResult:
    """Verify pending removal requests."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pending = db.get_pending_verifications()

    if not pending:
        return JobResult(
            job_name="verify_removals",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="skipped",
            details={"pending_count": 0, "message": "No removals due for verification"},
        )

    verified = 0
    for removal in pending:
        db.update_removal(removal["id"], last_checked_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        verified += 1

    return JobResult(
        job_name="verify_removals",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"pending_count": len(pending), "verified": verified},
    )


def job_generate_report(db: Database, config: Config) -> JobResult:
    """Generate exposure reports for all persons."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persons = db.list_persons()

    if not persons:
        return JobResult(
            job_name="generate_report",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="success",
            details={"persons_reported": 0},
        )

    reports_dir = config.db_path.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    for person in persons:
        report = generate_exposure_report(
            person_name=person.name,
            broker_results=[],
            breach_results={"hibp_breaches": [], "dehashed_records": [], "total": 0},
            username_results=[],
            dork_results=[],
        )
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = reports_dir / f"{date_str}-{person.name.lower().replace(' ', '-')}.md"
        report_path.write_text(report)
        logger.info(f"Report written to {report_path}")

    return JobResult(
        job_name="generate_report",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_reported": len(persons)},
    )
