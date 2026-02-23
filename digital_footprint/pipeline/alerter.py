"""Email alerter for new findings detected during scheduled scans."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from digital_footprint.config import Config

logger = logging.getLogger("digital_footprint.pipeline")


def should_alert(new_count: int, previous_count: int) -> bool:
    """Return True if new findings exceed previous count."""
    return new_count > previous_count


def build_alert_body(
    person_name: str,
    job_name: str,
    new_count: int,
    previous_count: int,
) -> str:
    """Build plain-text alert email body."""
    delta = new_count - previous_count
    return (
        f"Digital Footprint Alert\n"
        f"=======================\n\n"
        f"Person: {person_name}\n"
        f"Scan type: {job_name}\n"
        f"Findings: {new_count} total ({delta} new)\n"
        f"Previous: {previous_count}\n\n"
        f"Action: Review new findings and take appropriate steps.\n"
        f"Run footprint_protect or /protect for a full pipeline scan.\n"
    )


def send_alert(subject: str, body: str, config: Config) -> bool:
    """Send an alert email via SMTP. Returns True if sent."""
    if not config.smtp_host or not config.alert_email:
        return False

    msg = MIMEMultipart()
    msg["From"] = config.smtp_user or "digital-footprint@localhost"
    msg["To"] = config.alert_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            if config.smtp_user and config.smtp_password:
                server.starttls()
                server.login(config.smtp_user, config.smtp_password)
            server.send_message(msg)
        logger.info(f"Alert sent to {config.alert_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def check_and_alert(
    job_name: str,
    new_count: int,
    previous_count: int,
    person_name: str,
    config: Config,
) -> bool:
    """Check if alert is needed and send it. Returns True if alert was sent."""
    if not should_alert(new_count, previous_count):
        return False

    delta = new_count - previous_count
    subject = f"[Digital Footprint] {delta} new findings for {person_name} ({job_name})"
    body = build_alert_body(person_name, job_name, new_count, previous_count)
    return send_alert(subject, body, config)
