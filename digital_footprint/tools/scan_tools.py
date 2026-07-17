"""MCP scan tools for Digital Footprint."""

import json
from pathlib import Path
from typing import Optional, Union

from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.reporters.exposure_report import generate_exposure_report
from digital_footprint.reporters.formats import render_report


def collect_report_inputs(db: Database, person_id: int) -> dict:
    """Read persisted findings/breaches for a person into the four report
    inputs. Shared by the exposure-report tool and the scheduler report job so
    both reflect the same data."""
    findings = db.get_findings_by_person(person_id, status="active")
    breaches = db.get_breaches_by_person(person_id)
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
    hibp = [
        {"name": b.get("breach_name"), "breach_date": b.get("breach_date"),
         "data_classes": b.get("data_types", []), "severity": b.get("severity", "medium")}
        for b in breaches if b.get("source") == "hibp"
    ]
    dehashed = [
        {"database_name": b.get("breach_name"), "severity": b.get("severity", "medium")}
        for b in breaches if b.get("source") == "dehashed"
    ]
    dark_web = [
        {"site_name": f.get("finding_type", "dark_web"), "url": f.get("url"), "risk_level": f.get("risk_level", "high")}
        for f in findings if f.get("source") == "dark_web"
    ]
    # A recorded breach-check FAILURE flips checked=False so the report shows
    # "could not be completed", not a false all-clear. Never-run (None) keeps
    # the default (don't nag when breach checking simply hasn't been used).
    breach_ok = db.breach_check_ok(person_id)
    breach_checked = breach_ok is not False
    breach_errors = [] if breach_checked else ["last breach check failed (see logs / verify HIBP key)"]
    return {
        "broker_results": broker_results,
        "breach_results": {
            "hibp_breaches": hibp, "dehashed_records": dehashed,
            "total": len(hibp) + len(dehashed),
            "checked": breach_checked, "errors": breach_errors,
        },
        "username_results": dark_web,
        "dork_results": [],
    }


async def do_breach_check(
    email: str,
    hibp_api_key: Optional[str] = None,
    dehashed_api_key: Optional[str] = None,
) -> str:
    """Run breach check and return JSON results."""
    if not hibp_api_key and not dehashed_api_key:
        return json.dumps({
            "status": "no_api_keys",
            "message": "Set HIBP_API_KEY and/or DEHASHED_API_KEY in .env to enable breach checking.",
        })

    results = await scan_breaches(
        email=email,
        hibp_api_key=hibp_api_key,
        dehashed_api_key=dehashed_api_key,
    )

    # Serialize dataclass objects
    output = {
        "email": results["email"],
        "hibp_count": results["hibp_count"],
        "dehashed_count": results["dehashed_count"],
        "total": results["total"],
        "hibp_breaches": [
            {
                "name": b.name,
                "title": b.title,
                "breach_date": b.breach_date,
                "data_classes": b.data_classes,
                "severity": b.severity,
            }
            for b in results["hibp_breaches"]
        ],
        "dehashed_records": [
            {
                "database_name": r.database_name,
                "severity": r.severity,
            }
            for r in results["dehashed_records"]
        ],
    }

    return json.dumps(output, indent=2)


_EXT = {"markdown": "md", "md": "md", "json": "json", "html": "html", "pdf": "pdf"}


def do_exposure_report(
    person_id: int,
    db: Database,
    broker_results: Optional[list] = None,
    breach_results: Optional[dict] = None,
    username_results: Optional[list] = None,
    dork_results: Optional[list] = None,
    fmt: str = "markdown",
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Generate an exposure report for a person in the requested format.

    Reads persisted findings from the DB when explicit results aren't passed.
    Returns the report text for markdown/json/html; PDF (binary) and any
    explicit output_path are written to a file and the path is returned.
    """
    person = db.get_person(person_id)
    if not person:
        return f"Person with id {person_id} not found."

    if broker_results is None and breach_results is None and username_results is None:
        inputs = collect_report_inputs(db, person_id)
    else:
        inputs = {
            "broker_results": broker_results or [],
            "breach_results": breach_results or {"hibp_breaches": [], "dehashed_records": [], "total": 0},
            "username_results": username_results or [],
            "dork_results": dork_results or [],
        }

    content = render_report(person_name=person.name, fmt=fmt, **inputs)

    # PDF is binary and can't be returned as MCP text; write it. An explicit
    # output_path forces a file for any format.
    if fmt == "pdf" or output_path is not None:
        if output_path is None:
            reports_dir = db.config.db_path.parent / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            slug = person.name.lower().replace(" ", "-")
            output_path = reports_dir / f"exposure-{slug}.{_EXT.get(fmt, 'txt')}"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            output_path.write_bytes(content)
        else:
            output_path.write_text(content)
        return f"Wrote {fmt} report to {output_path}"

    return content
