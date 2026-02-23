"""Tests for the pipeline orchestrator."""

from unittest.mock import patch, AsyncMock, MagicMock
from dataclasses import asdict

from digital_footprint.config import Config
from digital_footprint.pipeline.pipeline import protect_person, PipelineResult
from tests.conftest import make_test_db


def test_pipeline_result_dataclass():
    result = PipelineResult(
        person_id=1,
        started_at="2026-02-23 10:00:00",
        completed_at="2026-02-23 10:05:00",
        breaches_found=3,
        dark_web_findings=2,
        accounts_found=10,
        removals_submitted=1,
        risk_score=45,
        report="# Report",
    )
    assert result.person_id == 1
    assert result.risk_score == 45


def test_protect_person_not_found():
    db = make_test_db()
    config = Config()
    result = protect_person(person_id=999, db=db, config=config)
    assert result.status == "error"


def test_protect_person_no_email():
    db = make_test_db()
    db.insert_person(name="No Email User")
    config = Config()
    result = protect_person(person_id=1, db=db, config=config)
    assert result.status == "completed"
    assert result.breaches_found == 0


def test_protect_person_runs_breach_check():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [{"name": "TestBreach", "severity": "high", "breach_date": "2024-01-01", "data_classes": ["Passwords"]}],
            "hibp_count": 1,
            "dehashed_records": [],
            "dehashed_count": 0,
            "total": 1,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    assert result.status == "completed"
    assert result.breaches_found == 1


def test_protect_person_runs_dark_web():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [{"source": "Pastebin", "paste_id": "abc", "title": "test", "date": "2024-01-01", "severity": "high"}],
                "ahmia_results": [],
                "holehe_results": [{"service": "Twitter", "category": "social", "risk_level": "medium"}],
                "paste_count": 1, "ahmia_count": 0, "holehe_count": 1, "total": 2,
            }
            result = protect_person(person_id=1, db=db, config=config)

    assert result.dark_web_findings == 2


def test_protect_person_stores_pipeline_run():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    runs = db.get_pipeline_runs(person_id=1)
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"


def test_protect_person_generates_report():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    assert "Exposure Report" in result.report
    assert "Test User" in result.report
