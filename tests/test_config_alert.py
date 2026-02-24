"""Tests for alert_email config field."""

import os
from unittest.mock import patch

from digital_footprint.config import get_config, Config


def test_config_has_alert_email_field():
    config = Config()
    assert hasattr(config, "alert_email")
    assert config.alert_email == ""


def test_config_loads_alert_email_from_env():
    with patch.dict(os.environ, {"ALERT_EMAIL": "alerts@example.com"}):
        config = get_config()
        assert config.alert_email == "alerts@example.com"


def test_config_alert_email_defaults_empty():
    with patch("digital_footprint.config.load_dotenv"):
        with patch.dict(os.environ, {}, clear=True):
            config = get_config()
            assert config.alert_email == ""
