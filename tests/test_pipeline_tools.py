"""Tests for pipeline MCP tool helpers."""

import json
from unittest.mock import patch, AsyncMock

from digital_footprint.tools.pipeline_tools import do_protect
from tests.conftest import make_test_db


def test_do_protect_person_not_found():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = do_protect(person_id=999, db=db, config=config)
    parsed = json.loads(result)
    assert parsed["status"] == "error"


def test_do_protect_success():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
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
            result = do_protect(person_id=1, db=db, config=config)

    parsed = json.loads(result)
    assert parsed["status"] == "completed"
    assert "report" in parsed


def test_do_protect_returns_risk_score():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
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
            result = do_protect(person_id=1, db=db, config=config)

    parsed = json.loads(result)
    assert "risk_score" in parsed
