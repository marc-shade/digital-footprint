"""MCP schedule tool helpers."""

import json

from digital_footprint.db import Database
from digital_footprint.scheduler.runner import get_schedule_status


def do_schedule_status(db: Database) -> str:
    """Get scheduler status as JSON."""
    status = get_schedule_status(db)
    return json.dumps(status, indent=2, default=str)
