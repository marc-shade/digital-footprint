"""Configuration management for Digital Footprint."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    db_path: Path = field(default_factory=lambda: Path.home() / ".digital-footprint" / "footprint.db")
    brokers_dir: Path = field(default_factory=lambda: Path(__file__).parent / "brokers")
    hibp_api_key: str = ""
    dehashed_api_key: str = ""
    dehashed_email: str = ""
    captcha_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


def get_config() -> Config:
    """Load configuration from environment variables."""
    load_dotenv()

    config = Config()

    db_override = os.environ.get("DIGITAL_FOOTPRINT_DB_PATH")
    if db_override:
        config.db_path = Path(os.path.expanduser(db_override))

    config.hibp_api_key = os.environ.get("HIBP_API_KEY", "")
    config.dehashed_api_key = os.environ.get("DEHASHED_API_KEY", "")
    config.dehashed_email = os.environ.get("DEHASHED_EMAIL", "")
    config.captcha_api_key = os.environ.get("CAPTCHA_API_KEY", "")
    config.smtp_host = os.environ.get("SMTP_HOST", "")
    config.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    config.smtp_user = os.environ.get("SMTP_USER", "")
    config.smtp_password = os.environ.get("SMTP_PASSWORD", "")

    return config
