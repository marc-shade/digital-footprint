"""Removal orchestrator -- central dispatch to method-specific handlers."""

from datetime import datetime, timedelta
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.removers.email_remover import EmailRemover
from digital_footprint.removers.web_form_remover import WebFormRemover
from digital_footprint.removers.manual_remover import ManualRemover


class RemovalOrchestrator:
    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
    ):
        self.email_handler = EmailRemover(smtp_host, smtp_port, smtp_user, smtp_password)
        self.web_form_handler = WebFormRemover()
        self.manual_handler = ManualRemover()

    def select_handler(self, method: str):
        if method == "email":
            return self.email_handler
        if method == "web_form":
            return self.web_form_handler
        # phone, mail, or unknown -> manual instructions
        return self.manual_handler

    def submit_removal(
        self,
        person_id: int,
        broker_slug: str,
        db: Database,
    ) -> dict:
        person = db.get_person(person_id)
        if not person:
            return {"status": "error", "message": f"Person {person_id} not found"}

        broker = db.get_broker_by_slug(broker_slug)
        if not broker:
            return {"status": "error", "message": f"Broker '{broker_slug}' not found"}

        method = broker.opt_out_method or "manual"
        handler = self.select_handler(method)

        person_ctx = {
            "name": person.name,
            "email": person.emails[0] if person.emails else "",
            "phone": person.phones[0] if person.phones else "",
            "address": person.addresses[0] if person.addresses else "",
            "state": "",
        }

        broker_ctx = {
            "name": broker.name,
            "url": broker.url,
            "opt_out_email": broker.opt_out_email or "",
            "opt_out_url": broker.opt_out_url or "",
            "ccpa_compliant": broker.ccpa_compliant,
            "gdpr_compliant": broker.gdpr_compliant,
            "recheck_days": broker.recheck_days,
            "opt_out": {
                "method": method,
                "email": broker.opt_out_email or "",
                "url": broker.opt_out_url or "",
            },
        }

        # For sync handlers (email, manual)
        if method in ("email", "phone", "mail"):
            result = handler.submit(person=person_ctx, broker=broker_ctx)
        else:
            # web_form is async but we call from sync context
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                handler.submit(person=person_ctx, broker=broker_ctx)
            )

        # Record in DB
        next_check = (datetime.now() + timedelta(days=broker.recheck_days)).isoformat()
        db.insert_removal(
            person_id=person_id,
            broker_id=broker.id,
            method=method,
            status=result.get("status", "error"),
            reference_id=result.get("reference_id"),
            next_check_at=next_check if result.get("status") == "submitted" else None,
            submitted_at=result.get("submitted_at"),
        )

        return result

    def get_status(self, person_id: int, db: Database) -> dict:
        removals = db.get_removals_by_person(person_id)
        by_status = {}
        for r in removals:
            s = r["status"]
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "person_id": person_id,
            "total": len(removals),
            "by_status": by_status,
            "removals": removals,
        }
