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
from digital_footprint.pipeline.alerter import check_and_alert
from digital_footprint.removers.verification import RemovalVerifier
from digital_footprint.removers import escalation


def _get(obj, key, default=None):
    """Read a field from either a dict or a dataclass-like object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _persist_breaches(db: Database, person_id: int, results: dict) -> int:
    """Persist HIBP + DeHashed breaches for a person. Returns count persisted."""
    persisted = 0
    for b in results.get("hibp_breaches", []):
        name = _get(b, "name") or _get(b, "title") or "Unknown"
        db.insert_breach(
            person_id=person_id,
            breach_name=name,
            source="hibp",
            breach_date=_get(b, "breach_date"),
            data_types=_get(b, "data_classes", []) or [],
            severity=_get(b, "severity", "medium"),
        )
        persisted += 1
    for r in results.get("dehashed_records", []):
        name = _get(r, "database_name") or _get(r, "name") or "DeHashed record"
        db.insert_breach(
            person_id=person_id,
            breach_name=name,
            source="dehashed",
            severity=_get(r, "severity", "medium"),
        )
        persisted += 1
    return persisted


def _persist_dark_web(db: Database, person_id: int, results: dict) -> int:
    """Persist dark-web findings (pastes, ahmia, holehe) as findings rows."""
    persisted = 0
    for p in results.get("pastes", []):
        db.insert_finding(
            person_id=person_id, source="dark_web", finding_type="paste",
            data_found={"paste_id": _get(p, "paste_id"), "title": _get(p, "title")},
            risk_level=_get(p, "severity", "high"),
            url=_get(p, "source"),
        )
        persisted += 1
    for a in results.get("ahmia_results", []):
        db.insert_finding(
            person_id=person_id, source="dark_web", finding_type="tor_listing",
            data_found={"title": _get(a, "title")},
            risk_level=_get(a, "severity", "high"),
            url=_get(a, "url"),
        )
        persisted += 1
    for h in results.get("holehe_results", []):
        db.insert_finding(
            person_id=person_id, source="dark_web", finding_type="account",
            data_found={"service": _get(h, "service"), "category": _get(h, "category")},
            risk_level=_get(h, "risk_level", "medium"),
            url=_get(h, "service"),
        )
        persisted += 1
    return persisted

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
    """Run an async coroutine from a sync context, 3.12-safe.

    get_event_loop() is deprecated when no loop is running (3.12), so we probe
    for a RUNNING loop instead: none -> asyncio.run; one present -> run in a
    fresh thread so we never re-enter the live loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coro).result()


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

    previous_total = 0  # First run baseline
    last_run = db.get_last_run("breach_recheck")
    if last_run and last_run.get("details"):
        try:
            prev_details = json.loads(last_run["details"]) if isinstance(last_run["details"], str) else last_run["details"]
            previous_total = prev_details.get("new_breaches", 0)
        except (json.JSONDecodeError, TypeError):
            pass

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
            _persist_breaches(db, person.id, results)
        except Exception as e:
            logger.error(f"Breach check failed for {email}: {e}")

    # Alert if new findings
    for person in persons_with_email:
        check_and_alert(
            job_name="breach_recheck",
            new_count=total_new,
            previous_count=previous_total,
            person_name=person.name,
            config=config,
        )

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

    previous_total = 0
    last_run = db.get_last_run("dark_web_monitor")
    if last_run and last_run.get("details"):
        try:
            prev_details = json.loads(last_run["details"]) if isinstance(last_run["details"], str) else last_run["details"]
            previous_total = prev_details.get("total_findings", 0)
        except (json.JSONDecodeError, TypeError):
            pass

    total_findings = 0
    for person in persons_with_email:
        email = person.emails[0]
        try:
            results = _run_async(run_dark_web_scan(email, hibp_api_key=config.hibp_api_key))
            total_findings += results.get("total", 0)
            _persist_dark_web(db, person.id, results)
        except Exception as e:
            logger.error(f"Dark web scan failed for {email}: {e}")

    # Alert if new findings
    for person in persons_with_email:
        check_and_alert(
            job_name="dark_web_monitor",
            new_count=total_findings,
            previous_count=previous_total,
            person_name=person.name,
            config=config,
        )

    return JobResult(
        job_name="dark_web_monitor",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "total_findings": total_findings},
    )


def job_verify_removals(db: Database, config: Config) -> JobResult:
    """Verify pending removals by re-scanning, and escalate ignored ones.

    For each removal due for verification:
      * re-scan the broker (RemovalVerifier); if the person is gone, mark the
        removal 'confirmed'.
      * if still listed, bump attempts and reschedule the next check.
      * once a broker has ignored ESCALATION_ATTEMPT_THRESHOLD+ requests and
        the person is still listed, DRAFT an FTC / state-AG complaint to disk
        (never auto-filed) and record it on the removal.

    Brokers without a search_url_pattern cannot be re-scanned (the discovery
    URL is unknown); those are counted as 'unverifiable' rather than silently
    treated as confirmed.
    """
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

    verifier = RemovalVerifier()
    complaints_dir = config.db_path.parent / "complaints"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    confirmed = still_listed = unverifiable = escalated = 0

    for removal in pending:
        try:
            result = _run_async(verifier.verify_single(removal))
        except Exception as e:
            logger.error(f"Verification failed for removal {removal.get('id')}: {e}")
            continue

        status = result.get("status")
        if status in ("skipped", "unverifiable"):
            # No search pattern, or the broker served an anti-bot challenge:
            # listing status is unknown. Do NOT confirm, do NOT escalate.
            unverifiable += 1
            db.update_removal(removal["id"], last_checked_at=now)
            continue

        if status == "confirmed":
            confirmed += 1
            db.update_removal(removal["id"], status="confirmed", confirmed_at=now, last_checked_at=now)
            continue

        # still_found or failed -> still listed
        still_listed += 1
        attempts = result.get("attempts", removal.get("attempts", 0) + 1)
        db.update_removal(removal["id"], attempts=attempts, last_checked_at=now)

        if attempts >= escalation.ESCALATION_ATTEMPT_THRESHOLD:
            person = db.get_person(removal["person_id"])
            if not person:
                continue
            person_ctx = {"name": person.name, "email": person.emails[0] if person.emails else "", "state": ""}
            broker_row = db.get_broker_by_slug(removal.get("broker_slug", ""))
            broker_ctx = {
                "name": removal.get("broker_name", ""),
                "slug": removal.get("broker_slug", ""),
                "url": broker_row.url if broker_row else "",
                "ccpa_compliant": bool(broker_row.ccpa_compliant) if broker_row else False,
            }
            try:
                path = escalation.generate_complaint_file(
                    person=person_ctx,
                    broker=broker_ctx,
                    reference_id=removal.get("notes") or f"REM-{removal['id']}",
                    attempts=attempts,
                    first_request_date=removal.get("submitted_at") or "unknown",
                    last_checked=now,
                    complaints_dir=complaints_dir,
                )
                escalated += 1
                db.update_removal(
                    removal["id"],
                    status="escalated",
                    notes=f"Complaint drafted: {path.name}",
                )
                logger.info(f"Escalation complaint drafted for removal {removal['id']}: {path}")
            except Exception as e:
                logger.error(f"Escalation draft failed for removal {removal['id']}: {e}")

    return JobResult(
        job_name="verify_removals",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={
            "pending_count": len(pending),
            "confirmed": confirmed,
            "still_listed": still_listed,
            "unverifiable": unverifiable,
            "escalated": escalated,
        },
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
        # Read what prior scan/monitor jobs persisted for this person, so the
        # weekly report reflects real findings instead of empty sections.
        findings = db.get_findings_by_person(person.id, status="active")
        breaches = db.get_breaches_by_person(person.id)

        broker_results = [
            {
                "found": True,
                "broker_name": (f.get("data_found") or {}).get("broker_name") or f.get("url") or "broker",
                "broker_slug": (f.get("data_found") or {}).get("broker_slug"),
                "url": f.get("url"),
                "risk_level": f.get("risk_level", "medium"),
            }
            for f in findings if f.get("source") == "broker"
        ]
        hibp_dicts = [
            {
                "name": b.get("breach_name"),
                "breach_date": b.get("breach_date"),
                "data_classes": b.get("data_types", []),
                "severity": b.get("severity", "medium"),
            }
            for b in breaches if b.get("source") == "hibp"
        ]
        dehashed_dicts = [
            {"database_name": b.get("breach_name"), "severity": b.get("severity", "medium")}
            for b in breaches if b.get("source") == "dehashed"
        ]
        dark_web_findings = [
            {"site_name": f.get("finding_type", "dark_web"), "url": f.get("url"), "risk_level": f.get("risk_level", "high")}
            for f in findings if f.get("source") == "dark_web"
        ]

        report = generate_exposure_report(
            person_name=person.name,
            broker_results=broker_results,
            breach_results={
                "hibp_breaches": hibp_dicts,
                "dehashed_records": dehashed_dicts,
                "total": len(hibp_dicts) + len(dehashed_dicts),
            },
            username_results=dark_web_findings,
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
