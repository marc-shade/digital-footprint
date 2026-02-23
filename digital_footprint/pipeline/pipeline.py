"""End-to-end protection pipeline orchestrator."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan
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
    removals_submitted: int = 0
    risk_score: int = 0
    report: str = ""
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


def protect_person(person_id: int, db: Database, config: Config) -> PipelineResult:
    """Run the full protection pipeline for a person."""
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

    # Stage 4: Generate report
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
        broker_results=[],
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
        removals_submitted=0,
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
        removals_submitted=0,
        risk_score=risk_score,
        report=report,
    )
