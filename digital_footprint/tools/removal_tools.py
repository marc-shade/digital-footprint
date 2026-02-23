"""MCP removal tool helpers."""

import json
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.removers.orchestrator import RemovalOrchestrator


def do_broker_remove(
    broker_slug: str,
    person_id: int,
    db: Database,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
) -> str:
    orch = RemovalOrchestrator(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )
    result = orch.submit_removal(person_id=person_id, broker_slug=broker_slug, db=db)
    return json.dumps(result, indent=2)


def do_removal_status(person_id: int, db: Database) -> str:
    orch = RemovalOrchestrator()
    status = orch.get_status(person_id=person_id, db=db)
    return json.dumps(status, indent=2, default=str)


def do_verify_removals(person_id: int, db: Database) -> str:
    pending = db.get_pending_verifications()
    if person_id:
        pending = [r for r in pending if r["person_id"] == person_id]

    if not pending:
        return json.dumps({"verified": 0, "message": "No removals due for verification."})

    results = []
    for removal in pending:
        results.append({
            "removal_id": removal["id"],
            "status": "verification_needed",
            "broker_id": removal["broker_id"],
        })

    return json.dumps({
        "verified": len(results),
        "results": results,
    }, indent=2)
