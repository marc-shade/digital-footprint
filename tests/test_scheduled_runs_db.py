"""Tests for scheduled_runs DB operations."""

import json
from datetime import datetime

from digital_footprint.db import Database
from tests.conftest import make_test_db


def test_insert_scheduled_run():
    db = make_test_db()
    run_id = db.insert_scheduled_run(
        job_name="breach_recheck",
        started_at="2026-02-23 10:00:00",
    )
    assert run_id > 0


def test_update_scheduled_run():
    db = make_test_db()
    run_id = db.insert_scheduled_run(
        job_name="breach_recheck",
        started_at="2026-02-23 10:00:00",
    )
    db.update_scheduled_run(
        run_id,
        status="success",
        completed_at="2026-02-23 10:01:00",
        details=json.dumps({"breaches_checked": 5}),
    )
    run = db.get_scheduled_run(run_id)
    assert run["status"] == "success"
    assert run["completed_at"] == "2026-02-23 10:01:00"


def test_get_last_run():
    db = make_test_db()
    db.insert_scheduled_run(job_name="breach_recheck", started_at="2026-02-23 08:00:00")
    db.update_scheduled_run(1, status="success", completed_at="2026-02-23 08:01:00")
    db.insert_scheduled_run(job_name="breach_recheck", started_at="2026-02-23 14:00:00")
    db.update_scheduled_run(2, status="success", completed_at="2026-02-23 14:01:00")

    last = db.get_last_run("breach_recheck")
    assert last is not None
    assert last["started_at"] == "2026-02-23 14:00:00"


def test_get_last_run_no_history():
    db = make_test_db()
    assert db.get_last_run("nonexistent_job") is None


def test_get_run_history():
    db = make_test_db()
    for i in range(5):
        db.insert_scheduled_run(job_name="dark_web", started_at=f"2026-02-{20+i} 10:00:00")
        db.update_scheduled_run(i + 1, status="success", completed_at=f"2026-02-{20+i} 10:01:00")

    history = db.get_run_history(limit=3)
    assert len(history) == 3
    # Most recent first
    assert history[0]["started_at"] == "2026-02-24 10:00:00"


def test_get_run_history_default_limit():
    db = make_test_db()
    db.insert_scheduled_run(job_name="test", started_at="2026-02-23 10:00:00")
    history = db.get_run_history()
    assert len(history) == 1
