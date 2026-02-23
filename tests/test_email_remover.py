"""Tests for email-based removal handler."""

from unittest.mock import patch, MagicMock
from digital_footprint.removers.email_remover import EmailRemover


def _person_ctx():
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "address": "123 Main St, Springfield, CA",
        "state": "California",
    }


def _broker_ctx(ccpa=True, gdpr=False):
    return {
        "name": "TestBroker",
        "url": "https://testbroker.com",
        "opt_out_email": "privacy@testbroker.com",
        "ccpa_compliant": ccpa,
        "gdpr_compliant": gdpr,
        "recheck_days": 30,
    }


def test_select_template_ccpa():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    template = remover.select_template(_broker_ctx(ccpa=True, gdpr=False))
    assert template == "ccpa_deletion.j2"


def test_select_template_gdpr():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    template = remover.select_template(_broker_ctx(ccpa=False, gdpr=True))
    assert template == "gdpr_erasure.j2"


def test_select_template_generic():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    template = remover.select_template(_broker_ctx(ccpa=False, gdpr=False))
    assert template == "generic_removal.j2"


def test_render_email():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    subject, body = remover.render_email(
        person=_person_ctx(),
        broker=_broker_ctx(),
    )
    assert "John Doe" in subject
    assert "TestBroker" in body
    assert "CCPA" in body
    assert "REF-" in subject  # auto-generated reference_id


@patch("digital_footprint.removers.email_remover.smtplib.SMTP")
def test_send_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    remover = EmailRemover(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password123",
    )
    result = remover.submit(person=_person_ctx(), broker=_broker_ctx())

    assert result["status"] == "submitted"
    assert result["method"] == "email"
    assert "reference_id" in result
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("user@example.com", "password123")
    mock_smtp.send_message.assert_called_once()


def test_submit_without_smtp_config():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    result = remover.submit(person=_person_ctx(), broker=_broker_ctx())
    assert result["status"] == "error"
    assert "SMTP" in result["message"]
