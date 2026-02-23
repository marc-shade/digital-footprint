"""Tests for monitoring MCP tool helpers."""

import json
from unittest.mock import patch, AsyncMock, MagicMock
from digital_footprint.tools.monitor_tools import do_dark_web_monitor_sync, do_social_audit


@patch("digital_footprint.tools.monitor_tools.run_dark_web_scan", new_callable=AsyncMock)
def test_do_dark_web_monitor(mock_scan):
    mock_scan.return_value = {
        "email": "test@example.com",
        "paste_count": 1, "ahmia_count": 0, "holehe_count": 2, "total": 3,
        "pastes": [{"source": "Pastebin", "title": "Dump", "severity": "high"}],
        "ahmia_results": [],
        "holehe_results": [{"service": "twitter.com", "category": "social", "risk_level": "medium"}],
    }
    result = do_dark_web_monitor_sync("test@example.com", hibp_api_key="key")
    assert "test@example.com" in result
    assert "Pastebin" in result


def test_do_social_audit_no_person():
    db = MagicMock()
    db.get_person.return_value = None
    result = do_social_audit(person_id=999, db=db)
    assert "not found" in result.lower()


def test_do_social_audit_no_usernames():
    db = MagicMock()
    person = MagicMock()
    person.usernames = []
    person.name = "John Doe"
    db.get_person.return_value = person
    result = do_social_audit(person_id=1, db=db)
    parsed = json.loads(result)
    assert parsed["profiles_audited"] == 0
