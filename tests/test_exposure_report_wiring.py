"""do_exposure_report wiring (P1-3): reads persisted findings, renders all
formats, writes files for pdf / explicit output."""

import json
from pathlib import Path

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.tools.scan_tools import do_exposure_report, collect_report_inputs


def _db_with_findings(tmp_path):
    db = Database(Config(db_path=tmp_path / "r.db"))
    db.initialize()
    pid = db.insert_person("Jane Doe", emails=["jane@example.com"])
    db.insert_breach(pid, "LinkedIn", source="hibp", data_types=["Emails", "Passwords"], severity="critical")
    db.insert_finding(pid, source="broker", finding_type="listing",
                      data_found={"broker_name": "Spokeo"}, url="https://spokeo.com/jane")
    return db, pid


def test_collect_report_inputs_reads_persisted(tmp_path):
    db, pid = _db_with_findings(tmp_path)
    inputs = collect_report_inputs(db, pid)
    assert len(inputs["broker_results"]) == 1
    assert inputs["broker_results"][0]["broker_name"] == "Spokeo"
    assert inputs["breach_results"]["hibp_breaches"][0]["name"] == "LinkedIn"


def test_markdown_report_has_persisted_data(tmp_path):
    db, pid = _db_with_findings(tmp_path)
    out = do_exposure_report(pid, db, fmt="markdown")
    assert "Spokeo" in out and "LinkedIn" in out


def test_json_report_parses(tmp_path):
    db, pid = _db_with_findings(tmp_path)
    out = do_exposure_report(pid, db, fmt="json")
    parsed = json.loads(out)
    assert parsed["subject"] == "Jane Doe"
    assert parsed["brokers"][0]["name"] == "Spokeo"


def test_html_report_returned_inline(tmp_path):
    db, pid = _db_with_findings(tmp_path)
    out = do_exposure_report(pid, db, fmt="html")
    assert out.startswith("<!doctype html>") and "Spokeo" in out


def test_pdf_report_written_to_default_file(tmp_path):
    db, pid = _db_with_findings(tmp_path)
    msg = do_exposure_report(pid, db, fmt="pdf")
    assert "Wrote pdf report to" in msg
    path = Path(msg.split("Wrote pdf report to", 1)[1].strip())
    assert path.exists()
    assert path.read_bytes()[:5] == b"%PDF-"


def test_explicit_output_path_writes_file(tmp_path):
    db, pid = _db_with_findings(tmp_path)
    out_file = tmp_path / "custom.html"
    msg = do_exposure_report(pid, db, fmt="html", output_path=out_file)
    assert "Wrote html report to" in msg
    assert out_file.exists() and out_file.read_text().startswith("<!doctype html>")


def test_output_path_creates_missing_parent_dir(tmp_path):
    # regression: an explicit output_path in a not-yet-existing dir must be
    # created, not raise FileNotFoundError
    db, pid = _db_with_findings(tmp_path)
    out_file = tmp_path / "nested" / "dir" / "report.json"
    msg = do_exposure_report(pid, db, fmt="json", output_path=out_file)
    assert "Wrote json report to" in msg
    assert out_file.exists()


def test_missing_person(tmp_path):
    db = Database(Config(db_path=tmp_path / "r.db"))
    db.initialize()
    assert "not found" in do_exposure_report(999, db, fmt="json")
