import os
from pathlib import Path
from digital_footprint.config import get_config


def test_default_db_path():
    config = get_config()
    assert config.db_path == Path.home() / ".digital-footprint" / "footprint.db"


def test_default_brokers_dir():
    config = get_config()
    assert config.brokers_dir.name == "brokers"


def test_env_override_db_path(tmp_path, monkeypatch):
    custom_path = str(tmp_path / "custom.db")
    monkeypatch.setenv("DIGITAL_FOOTPRINT_DB_PATH", custom_path)
    config = get_config()
    assert config.db_path == Path(custom_path)
