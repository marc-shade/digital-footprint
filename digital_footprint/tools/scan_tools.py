"""MCP scan tools for Digital Footprint."""

import json
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.reporters.exposure_report import generate_exposure_report


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


def do_exposure_report(
    person_id: int,
    db: Database,
    broker_results: Optional[list] = None,
    breach_results: Optional[dict] = None,
    username_results: Optional[list] = None,
    dork_results: Optional[list] = None,
) -> str:
    """Generate exposure report for a person."""
    person = db.get_person(person_id)
    if not person:
        return f"Person with id {person_id} not found."

    return generate_exposure_report(
        person_name=person.name,
        broker_results=broker_results or [],
        breach_results=breach_results or {"hibp_breaches": [], "dehashed_records": [], "total": 0},
        username_results=username_results or [],
        dork_results=dork_results or [],
    )
