"""Integration tests for the full scheduler pipeline."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from digital_footprint.config import Config
from digital_footprint.scheduler.jobs import JOB_INTERVALS
from digital_footprint.scheduler.runner import get_overdue_jobs, run_scheduled_jobs, get_schedule_status
from tests.conftest import make_test_db


def test_full_scheduler_cycle():
    """Test: no history -> all overdue -> run all -> none overdue."""
    db = make_test_db()
    config = Config()

    # 1. All jobs should be overdue initially
    overdue = get_overdue_jobs(db)
    assert len(overdue) == len(JOB_INTERVALS)

    # 2. Run all jobs (mock external calls)
    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_breach, \
         patch("digital_footprint.scheduler.jobs.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
        mock_breach.return_value = {"email": "x", "hibp_breaches": [], "hibp_count": 0, "dehashed_records": [], "dehashed_count": 0, "total": 0}
        mock_dark.return_value = {"email": "x", "pastes": [], "ahmia_results": [], "holehe_results": [], "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0}
        results = run_scheduled_jobs(db, config)

    # 3. All jobs should have run
    assert len(results) == len(JOB_INTERVALS)
    for r in results:
        assert r.status in ("success", "skipped")

    # 4. No jobs should be overdue now
    overdue = get_overdue_jobs(db)
    assert len(overdue) == 0

    # 5. Status should show all jobs with last_run
    status = get_schedule_status(db)
    for job in status["jobs"]:
        assert job["last_run"] is not None


def test_scheduler_partial_failure():
    """Test that one job failing doesn't prevent others from running."""
    db = make_test_db()
    config = Config()

    def failing_job(db, config):
        raise RuntimeError("Simulated failure")

    with patch("digital_footprint.scheduler.runner.JOB_FUNCTIONS", {
        "breach_recheck": failing_job,
        "dark_web_monitor": lambda db, cfg: __import__(
            "digital_footprint.scheduler.jobs", fromlist=["JobResult"]
        ).JobResult(
            job_name="dark_web_monitor",
            started_at="2026-02-23 10:00:00",
            completed_at="2026-02-23 10:01:00",
            status="success",
            details={},
        ),
    }):
        with patch("digital_footprint.scheduler.runner.JOB_INTERVALS", {"breach_recheck": 7, "dark_web_monitor": 3}):
            results = run_scheduled_jobs(db, config)

    statuses = {r.job_name: r.status for r in results}
    assert statuses["breach_recheck"] == "failed"
    assert statuses["dark_web_monitor"] == "success"

    # Both should be recorded in DB
    history = db.get_run_history(limit=10)
    assert len(history) == 2


def test_scheduler_respects_intervals():
    """Test that jobs run on correct intervals."""
    db = make_test_db()

    # Simulate breach_recheck ran 2 days ago (interval = 7, should NOT be overdue)
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at=two_days_ago)
    db.update_scheduled_run(run_id, status="success", completed_at=two_days_ago)

    # Simulate dark_web_monitor ran 5 days ago (interval = 3, SHOULD be overdue)
    five_days_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="dark_web_monitor", started_at=five_days_ago)
    db.update_scheduled_run(run_id, status="success", completed_at=five_days_ago)

    overdue = get_overdue_jobs(db)
    assert "breach_recheck" not in overdue
    assert "dark_web_monitor" in overdue
    # verify_removals and generate_report have never run, so they're overdue
    assert "verify_removals" in overdue
    assert "generate_report" in overdue
