"""Configuration management for Digital Footprint."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    alert_email: str = ""
    # Auto-visit broker confirmation links found over IMAP. Off by default:
    # when off, the link is recorded for the human to click.
    auto_confirm: bool = False
    # Auto-resubmit a removal that is still listed (before escalation). Off by
    # default: when off, the verify job records that a resubmit is due instead
    # of contacting the broker.
    auto_resubmit: bool = False
    # Encryption at rest for PII (see crypto.py). Off by default; enabled by
    # DIGITAL_FOOTPRINT_ENCRYPT=1 or by setting DIGITAL_FOOTPRINT_DB_KEY.
    encrypt: bool = False
    key_path: Optional[Path] = None

    def resolved_key_path(self) -> Path:
        """Where the key file lives when encryption uses a generated key."""
        if self.key_path is not None:
            return self.key_path
        return self.db_path.parent / "db.key"


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
    config.imap_host = os.environ.get("IMAP_HOST", "")
    config.imap_port = int(os.environ.get("IMAP_PORT", "993"))
    config.imap_user = os.environ.get("IMAP_USER", "")
    config.imap_password = os.environ.get("IMAP_PASSWORD", "")
    config.alert_email = os.environ.get("ALERT_EMAIL", "")
    config.auto_confirm = os.environ.get("DIGITAL_FOOTPRINT_AUTO_CONFIRM", "").strip().lower() in ("1", "true", "yes", "on")
    config.auto_resubmit = os.environ.get("DIGITAL_FOOTPRINT_AUTO_RESUBMIT", "").strip().lower() in ("1", "true", "yes", "on")

    from digital_footprint.crypto import encryption_requested
    config.encrypt = encryption_requested()

    return config
