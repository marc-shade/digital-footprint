"""Integration tests for the full pipeline + alerting system."""

from unittest.mock import patch, AsyncMock, MagicMock

from digital_footprint.config import Config
from digital_footprint.pipeline.pipeline import protect_person
from digital_footprint.pipeline.alerter import check_and_alert, should_alert
from tests.conftest import make_test_db


def test_full_pipeline_end_to_end():
    """Test complete pipeline: person -> scan -> report -> DB record."""
    db = make_test_db()
    db.insert_person(name="Integration Test", emails=["int@example.com"], usernames=["intuser"])
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "int@example.com",
            "hibp_breaches": [
                {"name": "MegaBreach", "title": "MegaBreach", "breach_date": "2024-06-01",
                 "data_classes": ["Passwords", "Email addresses"], "severity": "critical"},
            ],
            "hibp_count": 1, "dehashed_records": [], "dehashed_count": 0, "total": 1,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "int@example.com",
                "pastes": [{"source": "Pastebin", "paste_id": "xyz", "title": "leaked data", "date": "2024-01-01", "severity": "high"}],
                "ahmia_results": [],
                "holehe_results": [{"service": "Twitter", "category": "social", "risk_level": "medium"}],
                "paste_count": 1, "ahmia_count": 0, "holehe_count": 1, "total": 2,
            }
            result = protect_person(person_id=1, db=db, config=config)

    # Verify pipeline result
    assert result.status == "completed"
    assert result.breaches_found == 1
    assert result.dark_web_findings == 2
    assert result.accounts_found == 1
    assert result.risk_score > 0
    assert "Integration Test" in result.report
    assert "Exposure Report" in result.report

    # Verify DB record
    runs = db.get_pipeline_runs(person_id=1)
    assert len(runs) == 1
    assert runs[0]["breaches_found"] == 1
    assert runs[0]["dark_web_findings"] == 2
    assert runs[0]["risk_score"] > 0


def test_alerter_integrates_with_pipeline():
    """Test that alerts fire correctly based on finding counts."""
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.smtp_port = 587
    config.smtp_user = "user@test.com"
    config.smtp_password = "pass"
    config.alert_email = "alerts@test.com"

    # Should alert: new findings > previous
    assert should_alert(new_count=5, previous_count=2) is True

    with patch("digital_footprint.pipeline.alerter.send_alert", return_value=True):
        result = check_and_alert(
            job_name="breach_recheck",
            new_count=5,
            previous_count=2,
            person_name="Test User",
            config=config,
        )
        assert result is True

    # Should NOT alert: no change
    result = check_and_alert(
        job_name="breach_recheck",
        new_count=2,
        previous_count=2,
        person_name="Test User",
        config=config,
    )
    assert result is False


def test_pipeline_multiple_emails():
    """Test pipeline handles multiple emails for one person."""
    db = make_test_db()
    db.insert_person(
        name="Multi Email",
        emails=["first@example.com", "second@example.com"],
    )
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "x", "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "x", "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    # scan_breaches should be called twice (once per email)
    assert mock_breach.call_count == 2
    assert mock_dark.call_count == 2
    assert result.status == "completed"
