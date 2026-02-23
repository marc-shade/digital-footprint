"""Tests for the alerter module."""

from unittest.mock import patch, MagicMock

from digital_footprint.config import Config
from digital_footprint.pipeline.alerter import (
    should_alert,
    build_alert_body,
    send_alert,
    check_and_alert,
)


def test_should_alert_new_findings():
    assert should_alert(new_count=5, previous_count=2) is True


def test_should_alert_no_change():
    assert should_alert(new_count=3, previous_count=3) is False


def test_should_alert_decrease():
    assert should_alert(new_count=1, previous_count=5) is False


def test_should_alert_from_zero():
    assert should_alert(new_count=3, previous_count=0) is True


def test_build_alert_body():
    body = build_alert_body(
        person_name="Marc Shade",
        job_name="breach_recheck",
        new_count=5,
        previous_count=2,
    )
    assert "Marc Shade" in body
    assert "breach_recheck" in body
    assert "3 new" in body


def test_build_alert_body_format():
    body = build_alert_body(
        person_name="Test User",
        job_name="dark_web_monitor",
        new_count=10,
        previous_count=0,
    )
    assert "Digital Footprint Alert" in body
    assert "dark_web_monitor" in body


def test_send_alert_calls_smtp():
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.smtp_port = 587
    config.smtp_user = "user@test.com"
    config.smtp_password = "password"
    config.alert_email = "alerts@test.com"

    with patch("digital_footprint.pipeline.alerter.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = send_alert(
            subject="Test Alert",
            body="Test body",
            config=config,
        )
        assert result is True


def test_send_alert_no_smtp_config():
    config = Config()
    config.smtp_host = ""
    config.alert_email = "alerts@test.com"

    result = send_alert(subject="Test", body="Test", config=config)
    assert result is False


def test_send_alert_no_alert_email():
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.alert_email = ""

    result = send_alert(subject="Test", body="Test", config=config)
    assert result is False


def test_check_and_alert_triggers():
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.smtp_port = 587
    config.smtp_user = "user@test.com"
    config.smtp_password = "pass"
    config.alert_email = "alerts@test.com"

    with patch("digital_footprint.pipeline.alerter.send_alert", return_value=True) as mock_send:
        result = check_and_alert(
            job_name="breach_recheck",
            new_count=5,
            previous_count=2,
            person_name="Test User",
            config=config,
        )
        assert result is True
        mock_send.assert_called_once()


def test_check_and_alert_no_trigger():
    config = Config()
    result = check_and_alert(
        job_name="breach_recheck",
        new_count=2,
        previous_count=2,
        person_name="Test User",
        config=config,
    )
    assert result is False
