"""Tests for scheduled job definitions."""

import json
from unittest.mock import patch, AsyncMock

from digital_footprint.scheduler.jobs import (
    JobResult,
    JOB_INTERVALS,
    job_breach_recheck,
    job_dark_web_monitor,
    job_verify_removals,
    job_generate_report,
)
from tests.conftest import make_test_db


def test_job_result_dataclass():
    result = JobResult(
        job_name="test",
        started_at="2026-02-23 10:00:00",
        completed_at="2026-02-23 10:01:00",
        status="success",
        details={"count": 5},
    )
    assert result.job_name == "test"
    assert result.status == "success"
    assert result.details["count"] == 5


def test_job_intervals_defined():
    assert "breach_recheck" in JOB_INTERVALS
    assert "dark_web_monitor" in JOB_INTERVALS
    assert "verify_removals" in JOB_INTERVALS
    assert "generate_report" in JOB_INTERVALS
    assert JOB_INTERVALS["breach_recheck"] == 7
    assert JOB_INTERVALS["dark_web_monitor"] == 3
    assert JOB_INTERVALS["verify_removals"] == 1
    assert JOB_INTERVALS["generate_report"] == 7


def test_job_breach_recheck_no_persons():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_breach_recheck(db, config)
    assert result.job_name == "breach_recheck"
    assert result.status == "success"
    assert result.details["persons_checked"] == 0


def test_job_breach_recheck_with_person():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [],
            "hibp_count": 0,
            "dehashed_records": [],
            "dehashed_count": 0,
            "total": 0,
        }
        result = job_breach_recheck(db, config)

    assert result.status == "success"
    assert result.details["persons_checked"] == 1


def test_job_dark_web_monitor_no_persons():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_dark_web_monitor(db, config)
    assert result.job_name == "dark_web_monitor"
    assert result.status == "success"
    assert result.details["persons_checked"] == 0


def test_job_dark_web_monitor_with_person():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()

    with patch("digital_footprint.scheduler.jobs.run_dark_web_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "pastes": [], "ahmia_results": [], "holehe_results": [],
            "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
        }
        result = job_dark_web_monitor(db, config)

    assert result.status == "success"
    assert result.details["persons_checked"] == 1


def test_job_verify_removals_no_pending():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_verify_removals(db, config)
    assert result.job_name == "verify_removals"
    assert result.status == "skipped"


def test_job_generate_report_no_persons():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_generate_report(db, config)
    assert result.job_name == "generate_report"
    assert result.status == "success"
    assert result.details["persons_reported"] == 0


def test_job_generate_report_with_person(tmp_path):
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()
    config.db_path = tmp_path / "test.db"

    result = job_generate_report(db, config)
    assert result.status == "success"
    assert result.details["persons_reported"] == 1
