"""Tests for removal MCP tool helpers."""

import json
from unittest.mock import patch, MagicMock
from digital_footprint.tools.removal_tools import do_broker_remove, do_removal_status, do_verify_removals


@patch("digital_footprint.tools.removal_tools.RemovalOrchestrator")
def test_do_broker_remove(mock_orch_class):
    mock_orch = MagicMock()
    mock_orch.submit_removal.return_value = {
        "status": "submitted",
        "method": "email",
        "reference_id": "REF-123",
    }
    mock_orch_class.return_value = mock_orch

    db = MagicMock()
    result = do_broker_remove(
        broker_slug="spokeo",
        person_id=1,
        db=db,
        smtp_host="smtp.test.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
    )
    parsed = json.loads(result)
    assert parsed["status"] == "submitted"
    mock_orch.submit_removal.assert_called_once_with(person_id=1, broker_slug="spokeo", db=db)


@patch("digital_footprint.tools.removal_tools.RemovalOrchestrator")
def test_do_removal_status(mock_orch_class):
    mock_orch = MagicMock()
    mock_orch.get_status.return_value = {
        "person_id": 1,
        "total": 3,
        "by_status": {"submitted": 2, "confirmed": 1},
        "removals": [],
    }
    mock_orch_class.return_value = mock_orch

    db = MagicMock()
    result = do_removal_status(person_id=1, db=db)
    parsed = json.loads(result)
    assert parsed["total"] == 3
    assert parsed["by_status"]["confirmed"] == 1


def test_do_verify_removals():
    db = MagicMock()
    db.get_pending_verifications.return_value = []
    result = do_verify_removals(person_id=1, db=db)
    parsed = json.loads(result)
    assert parsed["verified"] == 0
