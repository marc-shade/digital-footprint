"""Email-based removal handler using Jinja2 templates and SMTP."""

import smtplib
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = Path(__file__).parent / "templates"


class EmailRemover:
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    def select_template(self, broker: dict) -> str:
        if broker.get("ccpa_compliant"):
            return "ccpa_deletion.j2"
        if broker.get("gdpr_compliant"):
            return "gdpr_erasure.j2"
        return "generic_removal.j2"

    @staticmethod
    def _normalize_person(person: dict) -> dict:
        """Normalize person dict so templates get singular fields."""
        p = dict(person)
        if "email" not in p and "emails" in p:
            emails = p["emails"]
            p["email"] = emails[0] if emails else ""
        if "phone" not in p and "phones" in p:
            phones = p["phones"]
            p["phone"] = phones[0] if phones else ""
        if "address" not in p and "addresses" in p:
            addrs = p["addresses"]
            p["address"] = addrs[0] if addrs else ""
        return p

    def render_email(
        self,
        person: dict,
        broker: dict,
        reference_id: Optional[str] = None,
    ) -> tuple[str, str]:
        if not reference_id:
            reference_id = f"REF-{uuid.uuid4().hex[:8].upper()}"

        person = self._normalize_person(person)
        template_name = self.select_template(broker)
        template = self.env.get_template(template_name)

        rendered = template.render(
            person=person,
            broker=broker,
            date=datetime.now().strftime("%Y-%m-%d"),
            reference_id=reference_id,
        )

        # Extract subject from first line
        lines = rendered.strip().split("\n")
        subject = lines[0].replace("Subject: ", "").strip()
        body = "\n".join(lines[1:]).strip()

        return subject, body

    def submit(self, person: dict, broker: dict) -> dict:
        if not self.smtp_host or not self.smtp_user:
            return {
                "status": "error",
                "method": "email",
                "message": "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env",
            }

        reference_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
        subject, body = self.render_email(person, broker, reference_id=reference_id)

        recipient = broker.get("opt_out_email", "")
        if not recipient:
            return {
                "status": "error",
                "method": "email",
                "message": f"No opt-out email for {broker['name']}",
            }

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = recipient

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)

        return {
            "status": "submitted",
            "method": "email",
            "reference_id": reference_id,
            "recipient": recipient,
            "subject": subject,
            "submitted_at": datetime.now().isoformat(),
        }
