"""Tests for schedule MCP tool helpers."""

import json

from digital_footprint.tools.schedule_tools import do_schedule_status
from tests.conftest import make_test_db


def test_do_schedule_status_empty():
    db = make_test_db()
    result = do_schedule_status(db)
    parsed = json.loads(result)
    assert "jobs" in parsed
    assert len(parsed["jobs"]) == 4
    for job in parsed["jobs"]:
        assert job["status"] == "never_run"


def test_do_schedule_status_with_history():
    db = make_test_db()
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at="2026-02-23 10:00:00")
    db.update_scheduled_run(run_id, status="success", completed_at="2026-02-23 10:01:00")

    result = do_schedule_status(db)
    parsed = json.loads(result)

    breach_job = next(j for j in parsed["jobs"] if j["name"] == "breach_recheck")
    assert breach_job["status"] == "success"
    assert breach_job["last_run"] is not None


def test_do_schedule_status_recent_runs():
    db = make_test_db()
    for i in range(3):
        run_id = db.insert_scheduled_run(job_name="dark_web_monitor", started_at=f"2026-02-{20+i} 10:00:00")
        db.update_scheduled_run(run_id, status="success", completed_at=f"2026-02-{20+i} 10:01:00")

    result = do_schedule_status(db)
    parsed = json.loads(result)
    assert len(parsed["recent_runs"]) == 3
