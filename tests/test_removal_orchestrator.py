"""Tests for removal orchestrator dispatch."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from digital_footprint.removers.orchestrator import RemovalOrchestrator


def _make_orchestrator(smtp_host="smtp.test.com", smtp_user="test@test.com", smtp_password="pass"):
    return RemovalOrchestrator(
        smtp_host=smtp_host,
        smtp_port=587,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )


def test_select_handler_email():
    orch = _make_orchestrator()
    handler = orch.select_handler("email")
    from digital_footprint.removers.email_remover import EmailRemover
    assert isinstance(handler, EmailRemover)


def test_select_handler_web_form():
    orch = _make_orchestrator()
    handler = orch.select_handler("web_form")
    from digital_footprint.removers.web_form_remover import WebFormRemover
    assert isinstance(handler, WebFormRemover)


def test_select_handler_phone():
    orch = _make_orchestrator()
    handler = orch.select_handler("phone")
    from digital_footprint.removers.manual_remover import ManualRemover
    assert isinstance(handler, ManualRemover)


def test_select_handler_mail():
    orch = _make_orchestrator()
    handler = orch.select_handler("mail")
    from digital_footprint.removers.manual_remover import ManualRemover
    assert isinstance(handler, ManualRemover)


def test_select_handler_unknown():
    orch = _make_orchestrator()
    handler = orch.select_handler("carrier_pigeon")
    from digital_footprint.removers.manual_remover import ManualRemover
    assert isinstance(handler, ManualRemover)


@patch("digital_footprint.removers.email_remover.smtplib.SMTP")
def test_submit_removal_email(mock_smtp_class, tmp_db):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    person_id = tmp_db.insert_person("John Doe", emails=["john@example.com"])
    from digital_footprint.models import Broker
    broker = Broker(
        slug="testbroker", name="TestBroker", url="https://test.com",
        category="people_search", opt_out_method="email",
        opt_out_email="privacy@test.com", ccpa_compliant=True,
    )
    tmp_db.insert_broker(broker)

    orch = _make_orchestrator()
    result = orch.submit_removal(person_id=person_id, broker_slug="testbroker", db=tmp_db)

    assert result["status"] == "submitted"
    removals = tmp_db.get_removals_by_person(person_id)
    assert len(removals) == 1
    assert removals[0]["status"] == "submitted"


def test_submit_removal_person_not_found(tmp_db):
    orch = _make_orchestrator()
    result = orch.submit_removal(person_id=999, broker_slug="testbroker", db=tmp_db)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()


def test_submit_removal_broker_not_found(tmp_db):
    person_id = tmp_db.insert_person("John Doe", emails=["john@example.com"])
    orch = _make_orchestrator()
    result = orch.submit_removal(person_id=person_id, broker_slug="nonexistent", db=tmp_db)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()


def test_get_removal_status(tmp_db):
    person_id = tmp_db.insert_person("John Doe", emails=["john@example.com"])
    from digital_footprint.models import Broker
    broker = Broker(slug="testbroker", name="TestBroker", url="https://test.com", category="people_search")
    tmp_db.insert_broker(broker)
    b = tmp_db.get_broker_by_slug("testbroker")
    tmp_db.insert_removal(person_id=person_id, broker_id=b.id, method="email", status="submitted")
    tmp_db.insert_removal(person_id=person_id, broker_id=b.id, method="email", status="confirmed")

    orch = _make_orchestrator()
    status = orch.get_status(person_id=person_id, db=tmp_db)
    assert status["total"] == 2
    assert status["by_status"]["submitted"] == 1
    assert status["by_status"]["confirmed"] == 1
