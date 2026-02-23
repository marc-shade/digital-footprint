"""MCP pipeline tool helpers."""

import json

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.pipeline.pipeline import protect_person


def do_protect(person_id: int, db: Database, config: Config) -> str:
    """Run full protection pipeline and return JSON result."""
    result = protect_person(person_id=person_id, db=db, config=config)
    return json.dumps({
        "person_id": result.person_id,
        "status": result.status,
        "breaches_found": result.breaches_found,
        "dark_web_findings": result.dark_web_findings,
        "accounts_found": result.accounts_found,
        "removals_submitted": result.removals_submitted,
        "risk_score": result.risk_score,
        "report": result.report,
        "error": result.error,
    }, indent=2)
