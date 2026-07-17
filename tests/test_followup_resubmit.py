"""Email resubmit uses the escalation-tone followup.j2, not the original
deletion template (P1 refinement of P0-5)."""

from unittest.mock import patch

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.models import Broker
from digital_footprint.removers.email_remover import EmailRemover, _days_since
from digital_footprint.removers.orchestrator import RemovalOrchestrator


def test_days_since_parses_and_defaults():
    assert _days_since("2000-01-01") > 8000
    assert _days_since("not-a-date") == 0


def test_send_followup_renders_followup_template():
    remover = EmailRemover("smtp.example.com", 587, "me@example.com", "pw")
    captured = {}

    def fake_send(recipient, subject, body, reference_id):
        captured.update(recipient=recipient, subject=subject, body=body, reference_id=reference_id)
        return {"status": "submitted", "method": "email", "reference_id": reference_id}

    with patch.object(remover, "_send_email", side_effect=fake_send):
        result = remover.send_followup(
            person={"name": "Jane Doe", "email": "jane@example.com", "state": "California"},
            broker={"name": "Spokeo", "opt_out_email": "privacy@spokeo.com"},
            reference_id="REM-5", original_date="2026-01-01",
        )
    assert result["status"] == "submitted"
    assert captured["recipient"] == "privacy@spokeo.com"
    assert "FOLLOW-UP" in captured["subject"]      # from followup.j2, not the deletion template
    assert "FTC" in captured["body"]               # escalation language
    assert "REM-5" in captured["subject"]


def test_send_followup_requires_smtp():
    remover = EmailRemover("", 587, "", "")
    r = remover.send_followup(person={"name": "x", "email": "x@y.com"},
                              broker={"name": "Spokeo", "opt_out_email": "p@spokeo.com"},
                              reference_id="REM-1", original_date="2026-01-01")
    assert r["status"] == "error" and "SMTP" in r["message"]


def test_orchestrator_resubmit_email_uses_followup(tmp_path):
    db = Database(Config(db_path=tmp_path / "t.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["jane@example.com"])
    db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com",
                            category="people_search", opt_out_method="email",
                            opt_out_email="privacy@spokeo.com"))
    orch = RemovalOrchestrator(smtp_host="smtp.example.com", smtp_user="me@example.com", smtp_password="pw")
    with patch.object(orch.email_handler, "send_followup", return_value={"status": "submitted"}) as m, \
         patch.object(orch.email_handler, "submit", return_value={"status": "submitted"}) as sub:
        orch.resubmit(pid, "spokeo", db, reference_id="REM-9", original_date="2026-01-01")
    m.assert_called_once()                      # followup path taken
    sub.assert_not_called()                     # NOT the original deletion template
    assert m.call_args.kwargs["reference_id"] == "REM-9"


def test_orchestrator_resubmit_without_reference_falls_back_to_dispatch(tmp_path):
    db = Database(Config(db_path=tmp_path / "t.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["jane@example.com"])
    db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com",
                            category="people_search", opt_out_method="email",
                            opt_out_email="privacy@spokeo.com"))
    orch = RemovalOrchestrator(smtp_host="smtp.example.com", smtp_user="me@example.com", smtp_password="pw")
    with patch.object(orch.email_handler, "send_followup") as m, \
         patch.object(orch.email_handler, "submit", return_value={"status": "submitted"}) as sub:
        orch.resubmit(pid, "spokeo", db)  # no reference_id -> standard dispatch
    m.assert_not_called()
    sub.assert_called_once()
