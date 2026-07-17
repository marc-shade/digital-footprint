"""Tests for the IMAP email-confirmation loop (P0-3)."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.models import Broker
from digital_footprint.removers.confirmation import (
    extract_confirmation_links,
    match_email_to_removal,
    parse_email,
    same_site,
    registrable_domain,
    ConfirmationProcessor,
)


def _confirm_email(from_addr="Privacy <privacy@radaris.com>",
                   subject="Confirm your opt-out request REF-ABC12345",
                   html='<a href="https://radaris.com/optout/confirm?token=xyz">Confirm removal</a>'
                        ' and an unrelated <a href="https://tracker.evil.com/x">tracker</a>',
                   text="Please confirm."):
    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg.as_bytes()


# --- pure helpers ---

def test_registrable_domain():
    assert registrable_domain("www.radaris.com") == "radaris.com"
    assert registrable_domain("mail.beenverified.com") == "beenverified.com"
    assert registrable_domain("radaris.com:443") == "radaris.com"


def test_same_site():
    assert same_site("https://radaris.com/x", "https://radaris.com")
    assert same_site("https://sub.radaris.com/x", "radaris.com")
    assert not same_site("https://evil.com/x", "radaris.com")


def test_parse_email_prefers_html_and_decodes():
    msg = parse_email(_confirm_email())
    assert msg["from_domain"] == "radaris.com"
    assert "REF-ABC12345" in msg["subject"]
    assert "radaris.com/optout/confirm" in msg["body"]


def test_extract_links_is_broker_domain_only():
    # the evil tracker link must NOT be returned even though it is in the body
    links = extract_confirmation_links(
        '<a href="https://radaris.com/optout/confirm?t=1">Confirm</a>'
        '<a href="https://tracker.evil.com/steal">x</a>',
        "radaris.com",
    )
    assert links == ["https://radaris.com/optout/confirm?t=1"]


def test_extract_links_ranks_confirm_keyword_first():
    links = extract_confirmation_links(
        '<a href="https://radaris.com/home">home</a>'
        '<a href="https://radaris.com/optout/confirm?t=1">confirm</a>',
        "radaris.com",
    )
    assert links[0] == "https://radaris.com/optout/confirm?t=1"


# --- matching ---

def test_match_by_reference_id():
    msg = parse_email(_confirm_email())
    removals = [
        {"id": 9, "reference_id": "REF-OTHER", "broker_domain": "spokeo.com", "person_emails": []},
        {"id": 5, "reference_id": "REF-ABC12345", "broker_domain": "radaris.com", "person_emails": []},
    ]
    assert match_email_to_removal(msg, removals)["id"] == 5


def test_match_by_sender_domain():
    msg = parse_email(_confirm_email(subject="Please verify"))
    removals = [{"id": 7, "reference_id": None, "broker_domain": "https://radaris.com", "person_emails": []}]
    assert match_email_to_removal(msg, removals)["id"] == 7


def test_match_by_person_email():
    msg = parse_email(_confirm_email(from_addr="noreply@mailer.net", subject="Verify",
                                     text="request for jane@example.com", html=""))
    removals = [{"id": 3, "reference_id": None, "broker_domain": "other.com",
                 "person_emails": ["jane@example.com"]}]
    assert match_email_to_removal(msg, removals)["id"] == 3


def test_no_match_returns_none():
    msg = parse_email(_confirm_email(from_addr="x@unknown.com", subject="hi", text="nothing", html=""))
    removals = [{"id": 1, "reference_id": "REF-Z", "broker_domain": "spokeo.com", "person_emails": []}]
    assert match_email_to_removal(msg, removals) is None


# --- processor (with a real in-memory DB) ---

def _db_with_submitted_removal(tmp_path):
    db = Database(Config(db_path=tmp_path / "c.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["jane@example.com"])
    db.insert_broker(Broker(slug="radaris", name="Radaris", url="https://radaris.com",
                            category="people_search", opt_out_method="email"))
    b = db.get_broker_by_slug("radaris")
    db.insert_removal(person_id=pid, broker_id=b.id, method="email",
                      status="submitted", reference_id="REF-ABC12345")
    return db, pid


def test_processor_dry_run_records_link_without_visiting(tmp_path):
    db, pid = _db_with_submitted_removal(tmp_path)
    visited = []
    proc = ConfirmationProcessor(auto_confirm=False, link_visitor=lambda u: visited.append(u) or True)
    res = proc.process(db, [_confirm_email()], db.get_removals_for_confirmation(), now="2026-07-17 09:00:00")
    assert res.matched == 1
    assert res.links_recorded == 1
    assert res.confirmed == 0
    assert visited == []  # dry run never visits
    r = db.get_removals_by_person(pid)[0]
    assert r["status"] == "submitted"
    assert "confirm_link:" in (r["notes"] or "")


def test_processor_auto_confirm_visits_and_confirms(tmp_path):
    db, pid = _db_with_submitted_removal(tmp_path)
    visited = []
    proc = ConfirmationProcessor(auto_confirm=True, link_visitor=lambda u: visited.append(u) or True)
    res = proc.process(db, [_confirm_email()], db.get_removals_for_confirmation(), now="2026-07-17 09:00:00")
    assert res.confirmed == 1
    assert visited == ["https://radaris.com/optout/confirm?token=xyz"]
    assert db.get_removals_by_person(pid)[0]["status"] == "confirmed"


def test_processor_auto_confirm_rejects_offsite_link(tmp_path):
    db, pid = _db_with_submitted_removal(tmp_path)
    # email whose only link is off the broker domain -> must never be visited
    evil = _confirm_email(html='<a href="https://phish.com/confirm">click</a>')
    visited = []
    proc = ConfirmationProcessor(auto_confirm=True, link_visitor=lambda u: visited.append(u) or True)
    res = proc.process(db, [evil], db.get_removals_for_confirmation(), now="2026-07-17 09:00:00")
    assert visited == []
    assert res.confirmed == 0
    assert db.get_removals_by_person(pid)[0]["status"] == "submitted"


def test_db_get_removals_for_confirmation_enriches(tmp_path):
    db, pid = _db_with_submitted_removal(tmp_path)
    rows = db.get_removals_for_confirmation()
    assert len(rows) == 1
    assert rows[0]["broker_domain"] == "https://radaris.com"
    assert rows[0]["reference_id"] == "REF-ABC12345"
    assert rows[0]["person_emails"] == ["jane@example.com"]


# --- scheduler job wiring (real path: job -> db query -> processor) ---

def test_job_skips_when_imap_unconfigured(tmp_path):
    from digital_footprint.scheduler.jobs import job_process_confirmations
    db, _ = _db_with_submitted_removal(tmp_path)
    result = job_process_confirmations(db, Config(db_path=tmp_path / "c.db"))
    assert result.job_name == "process_confirmations"
    assert result.status == "skipped"
    assert "IMAP" in result.details["message"]


def test_job_processes_confirmation_end_to_end(tmp_path, monkeypatch):
    from digital_footprint.scheduler import jobs as jobs_mod
    from digital_footprint.removers.confirmation import ImapFetcher

    db, pid = _db_with_submitted_removal(tmp_path)
    # feed the job a crafted confirmation message instead of real IMAP
    monkeypatch.setattr(ImapFetcher, "fetch_recent", lambda self, **kw: [_confirm_email()])

    cfg = Config(db_path=tmp_path / "c.db")
    cfg.imap_host, cfg.imap_user, cfg.imap_password = "imap.example.com", "u", "p"
    cfg.auto_confirm = False  # dry run: records the link, no network

    result = jobs_mod.job_process_confirmations(db, cfg)
    assert result.status == "success"
    assert result.details["matched"] == 1
    assert result.details["links_recorded"] == 1
    r = db.get_removals_by_person(pid)[0]
    assert "confirm_link:" in (r["notes"] or "")
