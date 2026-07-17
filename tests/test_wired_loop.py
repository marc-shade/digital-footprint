"""Tests for the wired removal/verify/report/escalate loop (2026-07-17).

These assert the ACTUAL contracts that were previously stubbed:
- findings/breaches persist and de-dup
- verify job re-scans and confirms/escalates (not just a timestamp bump)
- report job reads persisted findings (not empty sections)
- escalation drafts a real complaint file
- pipeline records dry-run removals without contacting brokers
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.models import Broker
from digital_footprint.removers import escalation
from digital_footprint.scheduler.jobs import (
    job_verify_removals,
    job_generate_report,
    job_breach_recheck,
)


def _db(tmp_path) -> Database:
    db = Database(Config(db_path=tmp_path / "t.db",
                         brokers_dir=Path(__file__).parent.parent / "digital_footprint" / "brokers"))
    db.initialize()
    return db


def _broker(db, slug="spokeo", pattern="https://spokeo.com/{first}-{last}"):
    db.insert_broker(Broker(
        slug=slug, name=slug.title(), url=f"https://{slug}.com",
        category="people_search", opt_out_method="email",
        opt_out_email=f"privacy@{slug}.com", search_url_pattern=pattern,
    ))
    return db.get_broker_by_slug(slug)


# --- persistence ---

def test_insert_and_read_finding(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe")
    fid = db.insert_finding(pid, source="broker", finding_type="listing",
                            data_found={"broker_slug": "spokeo"}, url="https://spokeo.com/jane")
    assert fid > 0
    findings = db.get_findings_by_person(pid)
    assert len(findings) == 1
    assert findings[0]["data_found"]["broker_slug"] == "spokeo"


def test_finding_dedup_on_rescan(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe")
    a = db.insert_finding(pid, source="broker", finding_type="listing", url="https://spokeo.com/jane")
    b = db.insert_finding(pid, source="broker", finding_type="listing", url="https://spokeo.com/jane")
    assert a == b  # same row refreshed, not duplicated
    assert len(db.get_findings_by_person(pid)) == 1


def test_breach_dedup(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe")
    db.insert_breach(pid, "LinkedIn", source="hibp", data_types=["Emails"])
    db.insert_breach(pid, "LinkedIn", source="hibp", data_types=["Emails"])
    assert len(db.get_breaches_by_person(pid)) == 1


def test_pending_verifications_enriched(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    broker = _broker(db)
    past = "2000-01-01T00:00:00"
    db.insert_removal(person_id=pid, broker_id=broker.id, method="email",
                      status="submitted", next_check_at=past)
    pending = db.get_pending_verifications()
    assert len(pending) == 1
    row = pending[0]
    assert row["broker_slug"] == "spokeo"
    assert row["search_url_pattern"] == "https://spokeo.com/{first}-{last}"
    assert row["person_first_name"] == "Jane"
    assert row["person_last_name"] == "Doe"


# --- verify job: real re-scan + escalation ---

def test_verify_job_confirms_when_gone(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    broker = _broker(db)
    db.insert_removal(person_id=pid, broker_id=broker.id, method="email",
                      status="submitted", next_check_at="2000-01-01T00:00:00")

    with patch("digital_footprint.removers.verification.scan_broker", new_callable=AsyncMock) as m:
        m.return_value = type("R", (), {"found": False})()
        result = job_verify_removals(db, Config(db_path=tmp_path / "t.db"))

    assert result.details["confirmed"] == 1
    assert db.get_removals_by_person(pid)[0]["status"] == "confirmed"


def test_verify_job_escalates_after_threshold(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    broker = _broker(db)
    # attempts already at threshold-1 so this check tips it over
    db.insert_removal(person_id=pid, broker_id=broker.id, method="email",
                      status="submitted", next_check_at="2000-01-01T00:00:00")
    db.update_removal(db.get_removals_by_person(pid)[0]["id"], attempts=1)

    with patch("digital_footprint.removers.verification.scan_broker", new_callable=AsyncMock) as m:
        m.return_value = type("R", (), {"found": True})()
        result = job_verify_removals(db, Config(db_path=tmp_path / "t.db"))

    assert result.details["escalated"] == 1
    assert result.details["resubmitted"] == 0  # escalation wins at threshold
    complaints = list((tmp_path / "complaints").glob("complaint-*.txt"))
    assert len(complaints) == 1
    assert "Consumer Privacy Complaint" in complaints[0].read_text()
    assert db.get_removals_by_person(pid)[0]["status"] == "escalated"


# --- auto-resubmit (P0-5): below the escalation threshold ---

def test_verify_job_resubmit_pending_dry_run(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    broker = _broker(db)
    db.insert_removal(person_id=pid, broker_id=broker.id, method="email",
                      status="submitted", next_check_at="2000-01-01T00:00:00")
    # attempts=0 -> verify makes 1 (< threshold) -> resubmit branch, dry run
    with patch("digital_footprint.removers.verification.scan_broker", new_callable=AsyncMock) as m:
        m.return_value = type("R", (), {"found": True})()
        result = job_verify_removals(db, Config(db_path=tmp_path / "t.db"))  # auto_resubmit off
    assert result.details["resubmit_pending"] == 1
    assert result.details["resubmitted"] == 0
    assert result.details["escalated"] == 0
    r = db.get_removals_by_person(pid)[0]
    assert "resubmit_pending" in (r["notes"] or "")
    assert r["status"] == "submitted"  # not escalated, not confirmed


def test_verify_job_resubmits_live_when_enabled(tmp_path):
    from unittest.mock import MagicMock
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    broker = _broker(db)
    db.insert_removal(person_id=pid, broker_id=broker.id, method="email",
                      status="submitted", next_check_at="2000-01-01T00:00:00")
    cfg = Config(db_path=tmp_path / "t.db")
    cfg.auto_resubmit = True
    with patch("digital_footprint.removers.verification.scan_broker", new_callable=AsyncMock) as m, \
         patch("digital_footprint.scheduler.jobs.RemovalOrchestrator") as OrchCls:
        m.return_value = type("R", (), {"found": True})()
        OrchCls.return_value.resubmit.return_value = {"status": "submitted"}
        result = job_verify_removals(db, cfg)
    assert result.details["resubmitted"] == 1
    assert result.details["resubmit_pending"] == 0
    OrchCls.return_value.resubmit.assert_called_once()


def test_orchestrator_resubmit_creates_no_new_row(tmp_path):
    from digital_footprint.removers.orchestrator import RemovalOrchestrator
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    broker = _broker(db)
    db.insert_removal(person_id=pid, broker_id=broker.id, method="email", status="submitted")
    before = len(db.get_removals_by_person(pid))
    # no SMTP configured -> the email send returns an error, but resubmit must
    # not create a duplicate removal row regardless
    RemovalOrchestrator().resubmit(pid, broker.slug, db)
    assert len(db.get_removals_by_person(pid)) == before


# --- report job reads persisted findings ---

def test_report_job_includes_persisted_findings(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    db.insert_breach(pid, "LinkedIn", source="hibp", data_types=["Emails", "Passwords"], severity="critical")
    db.insert_finding(pid, source="broker", finding_type="listing",
                      data_found={"broker_name": "Spokeo"}, url="https://spokeo.com/jane")

    config = Config(db_path=tmp_path / "t.db")
    result = job_generate_report(db, config)
    assert result.details["persons_reported"] == 1
    report_text = (tmp_path / "reports").glob("*jane-doe.md")
    content = next(report_text).read_text()
    assert "LinkedIn" in content
    assert "Spokeo" in content
    assert "1 found" in content  # broker section shows the finding


# --- breach recheck persists ---

def test_breach_job_persists(tmp_path):
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    config = Config(db_path=tmp_path / "t.db")
    config.hibp_api_key = "k"
    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as m:
        m.return_value = {
            "hibp_breaches": [{"name": "Adobe", "breach_date": "2013-10-04",
                               "data_classes": ["Emails"], "severity": "high"}],
            "dehashed_records": [], "total": 1,
        }
        job_breach_recheck(db, config)
    breaches = db.get_breaches_by_person(pid)
    assert len(breaches) == 1
    assert breaches[0]["breach_name"] == "Adobe"


# --- escalation module ---

def test_escalation_renders_complaint(tmp_path):
    path = escalation.generate_complaint_file(
        person={"name": "Jane Doe", "email": "j@x.com", "state": "California"},
        broker={"name": "Spokeo", "slug": "spokeo", "url": "https://spokeo.com", "ccpa_compliant": True},
        reference_id="REM-1", attempts=2,
        first_request_date="2026-01-01", last_checked="2026-02-01",
        complaints_dir=tmp_path / "complaints",
    )
    text = path.read_text()
    assert "Spokeo" in text
    assert "California Attorney General" in text
    assert "CCPA" in text


def test_escalation_followup_renders():
    subject, body = escalation.render_followup(
        person={"name": "Jane Doe", "email": "j@x.com", "state": "California"},
        broker={"name": "Spokeo"}, reference_id="REF-1",
        original_date="2026-01-01", days_elapsed=40,
    )
    assert "FOLLOW-UP" in subject
    assert "FTC" in body


# --- pipeline dry-run removal ---

def test_pipeline_dry_run_records_pending_without_submitting(tmp_path):
    from digital_footprint.pipeline.pipeline import protect_person
    db = _db(tmp_path)
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    _broker(db)
    config = Config(db_path=tmp_path / "t.db")

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mb, \
         patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as md, \
         patch("digital_footprint.pipeline.pipeline.scan_all_brokers", new_callable=AsyncMock) as ms:
        mb.return_value = {"hibp_breaches": [], "dehashed_records": [], "total": 0}
        md.return_value = {"pastes": [], "ahmia_results": [], "holehe_results": [], "total": 0}
        ms.return_value = [type("R", (), {
            "found": True, "broker_name": "Spokeo", "broker_slug": "spokeo",
            "url": "https://spokeo.com/jane", "risk_level": "medium"})()]
        # dry run (default): must NOT construct a RemovalOrchestrator / send anything
        with patch("digital_footprint.pipeline.pipeline.RemovalOrchestrator") as orch:
            result = protect_person(pid, db, config)  # submit_removals defaults False
            orch.assert_not_called()

    assert result.brokers_found == 1
    assert result.removals_queued == 1
    assert result.removals_submitted == 0
    removals = db.get_removals_by_person(pid)
    assert len(removals) == 1
    assert removals[0]["status"] == "pending"
