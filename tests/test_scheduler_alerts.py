"""Tests for scheduler alert integration."""

from unittest.mock import patch, AsyncMock

from digital_footprint.config import Config
from digital_footprint.scheduler.jobs import job_breach_recheck, job_dark_web_monitor
from tests.conftest import make_test_db


def test_breach_recheck_calls_alert_on_new():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.hibp_api_key = "test-key"
    config.alert_email = "alerts@test.com"

    # First run: 0 previous breaches
    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [{"name": "Breach1", "severity": "high"}],
            "hibp_count": 1, "dehashed_records": [], "dehashed_count": 0, "total": 1,
        }
        with patch("digital_footprint.scheduler.jobs.check_and_alert") as mock_alert:
            result = job_breach_recheck(db, config)
            # Alert should be called since we found new breaches
            mock_alert.assert_called()


def test_breach_recheck_no_alert_when_no_findings():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.scheduler.jobs.check_and_alert") as mock_alert:
            result = job_breach_recheck(db, config)
            mock_alert.assert_called_once_with(
                job_name="breach_recheck",
                new_count=0,
                previous_count=0,
                person_name="Test User",
                config=config,
            )


def test_dark_web_calls_alert():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.alert_email = "alerts@test.com"

    with patch("digital_footprint.scheduler.jobs.run_dark_web_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "pastes": [{"source": "Pastebin", "severity": "high"}],
            "ahmia_results": [], "holehe_results": [],
            "paste_count": 1, "ahmia_count": 0, "holehe_count": 0, "total": 1,
        }
        with patch("digital_footprint.scheduler.jobs.check_and_alert") as mock_alert:
            result = job_dark_web_monitor(db, config)
            mock_alert.assert_called()
