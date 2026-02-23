"""Tests for scheduler runner."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from digital_footprint.scheduler.runner import (
    get_overdue_jobs,
    run_scheduled_jobs,
    get_schedule_status,
)
from digital_footprint.scheduler.jobs import JOB_INTERVALS
from tests.conftest import make_test_db


def test_get_overdue_jobs_no_history():
    """All jobs overdue when never run."""
    db = make_test_db()
    overdue = get_overdue_jobs(db)
    assert set(overdue) == set(JOB_INTERVALS.keys())


def test_get_overdue_jobs_recently_run():
    """Jobs not overdue when recently completed."""
    db = make_test_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for job_name in JOB_INTERVALS:
        run_id = db.insert_scheduled_run(job_name=job_name, started_at=now)
        db.update_scheduled_run(run_id, status="success", completed_at=now)

    overdue = get_overdue_jobs(db)
    assert len(overdue) == 0


def test_get_overdue_jobs_old_run():
    """Jobs overdue when last run is past interval."""
    db = make_test_db()
    old_time = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at=old_time)
    db.update_scheduled_run(run_id, status="success", completed_at=old_time)

    overdue = get_overdue_jobs(db)
    assert "breach_recheck" in overdue


def test_run_scheduled_jobs_records_results():
    """Runner stores results in DB."""
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()

    with patch("digital_footprint.scheduler.runner.JOB_FUNCTIONS") as mock_fns:
        mock_fns.__contains__ = lambda self, k: True
        mock_fns.__getitem__ = lambda self, k: lambda db, config: __import__(
            "digital_footprint.scheduler.jobs", fromlist=["JobResult"]
        ).JobResult(
            job_name=k,
            started_at="2026-02-23 10:00:00",
            completed_at="2026-02-23 10:01:00",
            status="success",
            details={"test": True},
        )
        mock_fns.keys = lambda self: ["breach_recheck"]

        results = run_scheduled_jobs(db, config)

    assert len(results) >= 1
    history = db.get_run_history(limit=10)
    assert len(history) >= 1


def test_get_schedule_status_empty():
    db = make_test_db()
    status = get_schedule_status(db)
    assert "jobs" in status
    assert len(status["jobs"]) == len(JOB_INTERVALS)
    for job in status["jobs"]:
        assert job["last_run"] is None
        assert job["status"] == "never_run"


def test_get_schedule_status_with_history():
    db = make_test_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at=now)
    db.update_scheduled_run(run_id, status="success", completed_at=now)

    status = get_schedule_status(db)
    breach_job = next(j for j in status["jobs"] if j["name"] == "breach_recheck")
    assert breach_job["last_run"] is not None
    assert breach_job["status"] == "success"
