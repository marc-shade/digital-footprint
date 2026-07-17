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

    @staticmethod
    def _build_contexts(person, broker, method):
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
        return person_ctx, broker_ctx

    def _dispatch(self, method, person_ctx, broker_ctx) -> dict:
        handler = self.select_handler(method)
        if method in ("email", "phone", "mail"):
            return handler.submit(person=person_ctx, broker=broker_ctx)
        # web_form is async; run it 3.12-safely (get_event_loop is deprecated
        # with no running loop and raises from some contexts).
        import asyncio
        return asyncio.run(handler.submit(person=person_ctx, broker=broker_ctx))

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
        person_ctx, broker_ctx = self._build_contexts(person, broker, method)
        result = self._dispatch(method, person_ctx, broker_ctx)

        # Record a NEW removal row.
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

    def resubmit(
        self,
        person_id: int,
        broker_slug: str,
        db: Database,
        reference_id: Optional[str] = None,
        original_date: Optional[str] = None,
    ) -> dict:
        """Re-dispatch the opt-out for an EXISTING removal (no new row). Used by
        the verify job to re-send a request the broker ignored, before
        escalating. The caller updates the existing removal's tracking fields.

        For email brokers a resubmit is a SECOND request, so it sends the
        escalation-tone follow-up (followup.j2) rather than re-sending the
        original deletion template. Other methods re-run the standard dispatch.
        """
        person = db.get_person(person_id)
        if not person:
            return {"status": "error", "message": f"Person {person_id} not found"}
        broker = db.get_broker_by_slug(broker_slug)
        if not broker:
            return {"status": "error", "message": f"Broker '{broker_slug}' not found"}
        method = broker.opt_out_method or "manual"
        person_ctx, broker_ctx = self._build_contexts(person, broker, method)
        if method == "email" and reference_id:
            return self.email_handler.send_followup(
                person=person_ctx, broker=broker_ctx,
                reference_id=reference_id, original_date=original_date or "unknown",
            )
        return self._dispatch(method, person_ctx, broker_ctx)

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
