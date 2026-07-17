"""End-to-end protection pipeline orchestrator."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.scanners.broker_scanner import scan_all_brokers
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan
from digital_footprint.removers.orchestrator import RemovalOrchestrator
from digital_footprint.reporters.exposure_report import (
    generate_exposure_report,
    compute_risk_score,
)

logger = logging.getLogger("digital_footprint.pipeline")


@dataclass
class PipelineResult:
    person_id: int
    started_at: str = ""
    completed_at: str = ""
    status: str = "running"
    breaches_found: int = 0
    dark_web_findings: int = 0
    accounts_found: int = 0
    brokers_scanned: int = 0
    brokers_found: int = 0
    brokers_blocked: int = 0
    removals_submitted: int = 0
    removals_queued: int = 0
    risk_score: int = 0
    report: str = ""
    error: Optional[str] = None


def _run_async(coro):
    """Run an async function from sync context (3.12-safe: probe for a running
    loop rather than the deprecated get_event_loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coro).result()


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or "").split()
    first = parts[0] if parts else ""
    last = parts[-1] if len(parts) > 1 else ""
    return first, last


def protect_person(
    person_id: int,
    db: Database,
    config: Config,
    submit_removals: bool = False,
) -> PipelineResult:
    """Run the full protection pipeline for a person.

    Stages: breach check -> dark web -> username -> data-broker discovery ->
    removal -> report.

    submit_removals is the live-submission gate. Default False = DRY RUN: for
    every broker the person is found on, a removal is RECORDED as 'pending'
    (so the verify/escalate loop can pick it up) but NOTHING is sent to the
    broker. Only submit_removals=True actually dispatches email/web-form
    opt-outs. This keeps the destructive, hard-to-reverse action behind an
    explicit opt-in, per the operator's approval-gated requirement.
    """
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    person = db.get_person(person_id)
    if not person:
        return PipelineResult(
            person_id=person_id,
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="error",
            error=f"Person {person_id} not found",
        )

    # Create pipeline run record
    run_id = db.insert_pipeline_run(person_id=person_id, started_at=started)

    breach_results = {"hibp_breaches": [], "dehashed_records": [], "total": 0}
    dark_web_results = {"pastes": [], "ahmia_results": [], "holehe_results": [], "total": 0}
    username_results = []

    # Stage 1: Breach check
    if person.emails:
        for email in person.emails:
            try:
                results = _run_async(scan_breaches(
                    email=email,
                    hibp_api_key=config.hibp_api_key,
                    dehashed_api_key=config.dehashed_api_key,
                ))
                breach_results["hibp_breaches"].extend(results.get("hibp_breaches", []))
                breach_results["dehashed_records"].extend(results.get("dehashed_records", []))
                breach_results["total"] += results.get("total", 0)
            except Exception as e:
                logger.error(f"Breach check failed for {email}: {e}")

    # Stage 2: Dark web scan
    if person.emails:
        for email in person.emails:
            try:
                results = _run_async(run_dark_web_scan(email, hibp_api_key=config.hibp_api_key))
                dark_web_results["pastes"].extend(results.get("pastes", []))
                dark_web_results["ahmia_results"].extend(results.get("ahmia_results", []))
                dark_web_results["holehe_results"].extend(results.get("holehe_results", []))
                dark_web_results["total"] += results.get("total", 0)
            except Exception as e:
                logger.error(f"Dark web scan failed for {email}: {e}")

    # Stage 3: Username search (skip actual Maigret call -- too slow for pipeline)
    accounts_found = 0
    if person.usernames:
        accounts_found = len(person.usernames)

    # Persist breaches so the weekly report + status reflect them.
    for b in breach_results["hibp_breaches"]:
        db.insert_breach(
            person_id=person_id,
            breach_name=(b.get("name") if isinstance(b, dict) else getattr(b, "name", None)) or "Unknown",
            source="hibp",
            breach_date=b.get("breach_date") if isinstance(b, dict) else getattr(b, "breach_date", None),
            data_types=(b.get("data_classes") if isinstance(b, dict) else getattr(b, "data_classes", [])) or [],
            severity=(b.get("severity") if isinstance(b, dict) else getattr(b, "severity", "medium")),
        )

    # Stage 4: Data-broker discovery.
    # Only brokers that carry a search_url_pattern can be auto-scanned; the
    # rest are skipped (their discovery URL is unknown -- a registry data gap,
    # not a silent success). scan_all_brokers makes zero network calls when no
    # broker has a pattern.
    broker_report_results: list[dict] = []
    brokers_found_slugs: list[dict] = []
    scannable = [
        {"slug": b.slug, "name": b.name, "search_url_pattern": b.search_url_pattern}
        for b in db.list_brokers()
        if b.search_url_pattern
    ]
    first_name, last_name = _split_name(person.name)
    brokers_scanned = 0
    brokers_blocked = 0
    if scannable and last_name:
        try:
            scan_results = _run_async(scan_all_brokers(
                brokers=scannable,
                first_name=first_name,
                last_name=last_name,
            ))
            brokers_scanned = len(scan_results)
            for r in scan_results:
                found = getattr(r, "found", False)
                if getattr(r, "blocked", False):
                    brokers_blocked += 1
                broker_report_results.append({
                    "found": found,
                    "broker_name": getattr(r, "broker_name", ""),
                    "broker_slug": getattr(r, "broker_slug", ""),
                    "url": getattr(r, "url", ""),
                    "risk_level": getattr(r, "risk_level", "low"),
                    "blocked": getattr(r, "blocked", False),
                })
                if found:
                    broker = db.get_broker_by_slug(getattr(r, "broker_slug", ""))
                    finding_id = db.insert_finding(
                        person_id=person_id,
                        source="broker",
                        finding_type="listing",
                        data_found={"broker_name": getattr(r, "broker_name", ""),
                                    "broker_slug": getattr(r, "broker_slug", "")},
                        risk_level="medium",
                        url=getattr(r, "url", ""),
                        broker_id=broker.id if broker else None,
                    )
                    brokers_found_slugs.append({"slug": getattr(r, "broker_slug", ""), "finding_id": finding_id})
        except Exception as e:
            logger.error(f"Broker discovery failed: {e}")
    else:
        logger.info(
            "Broker discovery skipped: %d brokers have a search_url_pattern (need >=1 and a full name).",
            len(scannable),
        )

    # Stage 5: Removal for brokers the person was found on.
    # DRY RUN unless submit_removals=True: record the intended removal as
    # 'pending' without contacting the broker.
    removals_submitted = 0
    removals_queued = 0
    if brokers_found_slugs:
        if submit_removals:
            orchestrator = RemovalOrchestrator(
                smtp_host=config.smtp_host, smtp_port=config.smtp_port,
                smtp_user=config.smtp_user, smtp_password=config.smtp_password,
            )
            for entry in brokers_found_slugs:
                try:
                    result = orchestrator.submit_removal(person_id, entry["slug"], db)
                    if result.get("status") == "submitted":
                        removals_submitted += 1
                except Exception as e:
                    logger.error(f"Removal submission failed for {entry['slug']}: {e}")
        else:
            for entry in brokers_found_slugs:
                broker = db.get_broker_by_slug(entry["slug"])
                if broker:
                    db.insert_removal(
                        person_id=person_id, broker_id=broker.id,
                        method=broker.opt_out_method or "manual",
                        finding_id=entry["finding_id"], status="pending",
                    )
                    removals_queued += 1

    # Stage 6: Generate report
    brokers_found_count = len(brokers_found_slugs)
    # Convert breach dataclass objects to dicts for the report generator
    hibp_dicts = []
    for b in breach_results["hibp_breaches"]:
        if isinstance(b, dict):
            hibp_dicts.append(b)
        else:
            hibp_dicts.append({
                "name": b.name, "title": b.title,
                "breach_date": b.breach_date, "data_classes": b.data_classes,
                "severity": b.severity,
            })

    dehashed_dicts = []
    for r in breach_results["dehashed_records"]:
        if isinstance(r, dict):
            dehashed_dicts.append(r)
        else:
            dehashed_dicts.append({
                "database_name": r.database_name, "severity": r.severity,
            })

    report_breach = {
        "hibp_breaches": hibp_dicts,
        "dehashed_records": dehashed_dicts,
        "total": breach_results["total"],
    }

    report = generate_exposure_report(
        person_name=person.name,
        broker_results=broker_report_results,
        breach_results=report_breach,
        username_results=[{"site_name": u, "url": "", "risk_level": "low"} for u in (person.usernames or [])],
        dork_results=[],
    )

    # Compute risk score
    all_findings = []
    for b in hibp_dicts:
        all_findings.append({"risk_level": b.get("severity", "medium")})
    for r in dehashed_dicts:
        all_findings.append({"risk_level": r.get("severity", "medium")})
    for p in dark_web_results.get("pastes", []):
        all_findings.append({"risk_level": p.get("severity", "high") if isinstance(p, dict) else "high"})
    for b in broker_report_results:
        if b.get("found"):
            all_findings.append({"risk_level": b.get("risk_level", "medium")})
    risk_score = compute_risk_score(all_findings)

    completed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update pipeline run record
    db.update_pipeline_run(
        run_id,
        status="completed",
        completed_at=completed,
        breaches_found=breach_results["total"],
        dark_web_findings=dark_web_results["total"],
        accounts_found=accounts_found,
        removals_submitted=removals_submitted,
        risk_score=risk_score,
    )

    return PipelineResult(
        person_id=person_id,
        started_at=started,
        completed_at=completed,
        status="completed",
        breaches_found=breach_results["total"],
        dark_web_findings=dark_web_results["total"],
        accounts_found=accounts_found,
        brokers_scanned=brokers_scanned,
        brokers_found=brokers_found_count,
        brokers_blocked=brokers_blocked,
        removals_submitted=removals_submitted,
        removals_queued=removals_queued,
        risk_score=risk_score,
        report=report,
    )
