"""Scheduled job definitions for Digital Footprint."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.scanners.broker_scanner import scan_broker
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan
from digital_footprint.reporters.exposure_report import generate_exposure_report
from digital_footprint.tools.scan_tools import collect_report_inputs
from digital_footprint.pipeline.alerter import check_and_alert
from digital_footprint.removers.verification import RemovalVerifier
from digital_footprint.removers import escalation
from digital_footprint.removers.confirmation import ConfirmationProcessor, ImapFetcher
from digital_footprint.removers.orchestrator import RemovalOrchestrator


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
    # Confirmation links expire fast; check the inbox daily.
    "process_confirmations": 1,
    # Re-scan confirmed removals weekly; per-removal due date honors the
    # broker's recheck_days.
    "recheck_confirmed": 7,
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
            # Record whether the check actually completed, so reports can tell
            # "checked & clean" from "couldn't check".
            db.record_breach_check(person.id, results.get("checked", True))
        except Exception as e:
            logger.error(f"Breach check failed for {email}: {e}")
            db.record_breach_check(person.id, False)

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
    orchestrator = RemovalOrchestrator(
        smtp_host=config.smtp_host, smtp_port=config.smtp_port,
        smtp_user=config.smtp_user, smtp_password=config.smtp_password,
    )
    complaints_dir = config.db_path.parent / "complaints"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    confirmed = still_listed = unverifiable = escalated = 0
    resubmitted = resubmit_pending = resubmit_failed = 0

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
        broker_row = db.get_broker_by_slug(removal.get("broker_slug", ""))
        recheck_days = broker_row.recheck_days if broker_row else 7
        next_check = (datetime.now() + timedelta(days=recheck_days)).strftime("%Y-%m-%d %H:%M:%S")
        db.update_removal(removal["id"], attempts=attempts, last_checked_at=now, next_check_at=next_check)

        if attempts >= escalation.ESCALATION_ATTEMPT_THRESHOLD:
            person = db.get_person(removal["person_id"])
            if not person:
                continue
            person_ctx = {"name": person.name, "email": person.emails[0] if person.emails else "", "state": ""}
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
        else:
            # Below the escalation threshold: resubmit the ignored request.
            # Dry-run by default (record intent, contact no broker); only send
            # when DIGITAL_FOOTPRINT_AUTO_RESUBMIT is on.
            if config.auto_resubmit:
                try:
                    res = orchestrator.resubmit(
                        removal["person_id"], removal.get("broker_slug", ""), db,
                        reference_id=f"REM-{removal['id']}",
                        original_date=removal.get("submitted_at"),
                    )
                    if res.get("status") == "submitted":
                        resubmitted += 1
                        db.update_removal(removal["id"], submitted_at=now, notes=f"resubmitted (attempt {attempts})")
                    else:
                        resubmit_failed += 1
                        db.update_removal(removal["id"], notes=f"resubmit failed: {res.get('message') or res.get('status')}")
                except Exception as e:
                    resubmit_failed += 1
                    logger.error(f"Resubmit failed for removal {removal['id']}: {e}")
            else:
                resubmit_pending += 1
                db.update_removal(removal["id"], notes=f"resubmit_pending (attempt {attempts})")

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
            "resubmitted": resubmitted,
            "resubmit_pending": resubmit_pending,
            "resubmit_failed": resubmit_failed,
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
        # Read what prior scan/monitor jobs persisted for this person (shared
        # with the exposure-report tool), so the weekly report reflects real
        # findings instead of empty sections.
        inputs = collect_report_inputs(db, person.id)
        report = generate_exposure_report(person_name=person.name, **inputs)
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


def job_process_confirmations(db: Database, config: Config) -> JobResult:
    """Poll the confirmation inbox and complete removals whose broker emailed a
    'click to confirm' link. Off unless IMAP is configured; only visits links
    when DIGITAL_FOOTPRINT_AUTO_CONFIRM is on (else records the link)."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def done(status, details, error=None):
        return JobResult(
            job_name="process_confirmations", started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status=status, details=details, error=error,
        )

    if not (config.imap_host and config.imap_user and config.imap_password):
        return done("skipped", {"message": "IMAP not configured (IMAP_HOST/IMAP_USER/IMAP_PASSWORD)"})

    pending = db.get_removals_for_confirmation()
    if not pending:
        return done("skipped", {"pending": 0, "message": "no removals awaiting confirmation"})

    try:
        fetcher = ImapFetcher(config.imap_host, config.imap_user, config.imap_password, config.imap_port)
        messages = fetcher.fetch_recent()
    except Exception as e:
        logger.error(f"IMAP fetch failed: {e}")
        return done("failed", {"pending": len(pending)}, error=str(e))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    processor = ConfirmationProcessor(auto_confirm=config.auto_confirm)
    result = processor.process(db, messages, pending, now)
    return done("success", {
        "pending": len(pending),
        "messages": result.processed,
        "matched": result.matched,
        "confirmed": result.confirmed,
        "links_recorded": result.links_recorded,
        "unmatched": result.unmatched,
        "auto_confirm": config.auto_confirm,
    })


def job_recheck_confirmed(db: Database, config: Config) -> JobResult:
    """Re-scan confirmed removals and reopen any the broker has re-listed.

    A broker often re-adds you weeks after a confirmed deletion. This re-scans
    confirmed removals that are due (per the broker's recheck_days) and, on a
    re-listing, marks the old removal 're_listed', records a finding, and opens
    a fresh 'pending' removal so the normal submit/verify loop takes over. A
    blocked/errored scan is treated as unknown (removal stays confirmed), never
    as a false re-listing.
    """
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    due = db.get_confirmed_removals_due_recheck()
    if not due:
        return JobResult(
            job_name="recheck_confirmed", started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="skipped", details={"due": 0, "message": "no confirmed removals due for re-check"},
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    relisted = still_gone = unverifiable = reopened = 0

    for removal in due:
        pattern = removal.get("search_url_pattern")
        if not pattern:
            unverifiable += 1
            db.update_removal(removal["id"], last_checked_at=now)
            continue
        try:
            result = _run_async(scan_broker(
                broker_slug=removal.get("broker_slug", ""),
                broker_name=removal.get("broker_name", ""),
                url_pattern=pattern,
                first_name=removal.get("person_first_name", ""),
                last_name=removal.get("person_last_name", ""),
            ))
        except Exception as e:
            logger.error(f"Re-listing scan failed for removal {removal['id']}: {e}")
            unverifiable += 1
            continue

        if getattr(result, "blocked", False) or getattr(result, "status", "") == "error":
            unverifiable += 1
            db.update_removal(removal["id"], last_checked_at=now)
            continue

        if not result.found:
            still_gone += 1
            db.update_removal(removal["id"], last_checked_at=now)
            continue

        # Re-listed: mark the old removal, record a finding, open a fresh removal.
        relisted += 1
        db.update_removal(removal["id"], status="re_listed", last_checked_at=now,
                          notes=f"re-listed, re-check confirmed at {now}")
        finding_id = db.insert_finding(
            person_id=removal["person_id"], source="broker", finding_type="relisting",
            data_found={"broker_name": removal.get("broker_name", ""),
                        "broker_slug": removal.get("broker_slug", "")},
            risk_level="medium", url=getattr(result, "url", ""),
            broker_id=removal.get("broker_id"),
        )
        db.insert_removal(
            person_id=removal["person_id"], broker_id=removal["broker_id"],
            method=removal.get("method", "manual"), finding_id=finding_id, status="pending",
        )
        reopened += 1

    return JobResult(
        job_name="recheck_confirmed", started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={
            "due": len(due),
            "still_gone": still_gone,
            "relisted": relisted,
            "reopened": reopened,
            "unverifiable": unverifiable,
        },
    )
