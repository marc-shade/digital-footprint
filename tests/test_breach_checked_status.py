"""Report breach section must distinguish 'checked & clean' from 'couldn't
check' — no false all-clear when the HIBP check failed."""

import json

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.reporters.exposure_report import generate_exposure_report
from digital_footprint.reporters.formats import build_report_data, render_html, render_pdf
from digital_footprint.tools.scan_tools import collect_report_inputs

EMPTY = {"hibp_breaches": [], "dehashed_records": [], "total": 0}


def _md(breach):
    return generate_exposure_report("Jane", [], breach, [], [])


def test_markdown_checked_clean_says_no_records():
    out = _md({**EMPTY, "checked": True})
    assert "No breach records found." in out
    assert "could not be completed" not in out


def test_markdown_not_checked_warns_not_clean():
    out = _md({**EMPTY, "checked": False, "errors": ["hibp: invalid key"]})
    assert "could not be completed" in out
    assert "NOT an all-clear" in out
    assert "invalid key" in out
    assert "No breach records found." not in out


def test_markdown_default_is_checked_backward_compat():
    # a breach_results without a 'checked' key keeps the old behavior
    out = _md(dict(EMPTY))
    assert "No breach records found." in out


def test_html_not_checked_warns():
    data = build_report_data("Jane", [], {**EMPTY, "checked": False, "errors": ["bad key"]}, [], [])
    html = render_html(data)
    assert "could not be completed" in html
    assert "class='warn'" in html or 'class="warn"' in html


def test_pdf_not_checked_renders():
    data = build_report_data("Jane", [], {**EMPTY, "checked": False, "errors": ["bad key"]}, [], [])
    pdf = render_pdf(data)
    assert pdf[:5] == b"%PDF-"


def test_json_carries_checked_flag():
    data = build_report_data("Jane", [], {**EMPTY, "checked": False, "errors": ["x"]}, [], [])
    assert data["breach_checked"] is False
    assert data["breach_errors"] == ["x"]


# --- DB-path: collect_report_inputs threads recorded breach-check status ---

def test_collect_inputs_flags_recorded_failure(tmp_path):
    db = Database(Config(db_path=tmp_path / "t.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    db.record_breach_check(pid, ok=False)
    inputs = collect_report_inputs(db, pid)
    assert inputs["breach_results"]["checked"] is False


def test_collect_inputs_clean_after_successful_check(tmp_path):
    db = Database(Config(db_path=tmp_path / "t.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    db.record_breach_check(pid, ok=True)
    inputs = collect_report_inputs(db, pid)
    assert inputs["breach_results"]["checked"] is True


def test_collect_inputs_never_run_defaults_checked(tmp_path):
    # never-run keeps default (don't nag if breach checking wasn't used)
    db = Database(Config(db_path=tmp_path / "t.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    assert db.breach_check_ok(pid) is None
    inputs = collect_report_inputs(db, pid)
    assert inputs["breach_results"]["checked"] is True


def test_record_breach_check_latest_wins(tmp_path):
    db = Database(Config(db_path=tmp_path / "t.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["j@x.com"])
    db.record_breach_check(pid, ok=False)
    db.record_breach_check(pid, ok=True)
    assert db.breach_check_ok(pid) is True
