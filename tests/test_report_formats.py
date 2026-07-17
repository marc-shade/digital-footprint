"""Multi-format exposure report tests (P1-3): markdown / json / html / pdf."""

import json

import pytest

from digital_footprint.reporters.formats import (
    build_report_data,
    render_json,
    render_html,
    render_pdf,
    render_report,
    VALID_FORMATS,
)

BROKERS = [{"found": True, "broker_name": "Spokeo", "url": "https://spokeo.com/jane", "risk_level": "medium"}]
BREACHES = {"hibp_breaches": [{"name": "LinkedIn", "breach_date": "2021",
                               "data_classes": ["Emails", "Passwords"], "severity": "critical"}],
            "dehashed_records": [], "total": 1}
ACCOUNTS = [{"site_name": "GitHub", "url": "https://github.com/jane", "risk_level": "low"}]
DORKS = [{"title": "Resume PDF", "url": "https://x.com/jane.pdf", "risk_level": "medium"}]


def _args():
    return dict(person_name="Jane Doe", broker_results=BROKERS, breach_results=BREACHES,
                username_results=ACCOUNTS, dork_results=DORKS)


def test_build_report_data_shape():
    d = build_report_data(**_args())
    assert d["subject"] == "Jane Doe"
    assert d["risk_score"] > 0
    assert d["risk_label"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert len(d["brokers"]) == 1 and d["brokers"][0]["name"] == "Spokeo"
    assert len(d["breaches"]) == 1 and d["breaches"][0]["name"] == "LinkedIn"
    assert len(d["accounts"]) == 1
    assert d["recommendations"]


def test_json_is_valid_and_roundtrips():
    out = render_report(**_args(), fmt="json")
    parsed = json.loads(out)  # must be valid JSON
    assert parsed["subject"] == "Jane Doe"
    assert parsed["brokers"][0]["name"] == "Spokeo"


def test_html_is_wellformed_and_escaped():
    out = render_report(**_args(), fmt="html")
    assert out.startswith("<!doctype html>")
    assert "</html>" in out
    assert "Spokeo" in out and "LinkedIn" in out
    assert "Jane Doe" in out
    # a subject with markup must be escaped, not injected
    evil = render_html(build_report_data(person_name="<script>x</script>",
                                         broker_results=[], breach_results={"hibp_breaches": [], "dehashed_records": []},
                                         username_results=[], dork_results=[]))
    assert "<script>x</script>" not in evil
    assert "&lt;script&gt;" in evil


def test_pdf_is_a_real_pdf():
    out = render_report(**_args(), fmt="pdf")
    assert isinstance(out, bytes)
    assert out[:5] == b"%PDF-"  # PDF magic
    assert len(out) > 500


def test_pdf_handles_non_latin1_without_crashing():
    # an accented / emoji subject must not crash fpdf2's core-font encoder
    out = render_report(person_name="Renée 🌟 Dupont", broker_results=[],
                        breach_results={"hibp_breaches": [], "dehashed_records": []},
                        username_results=[], dork_results=[], fmt="pdf")
    assert out[:5] == b"%PDF-"


def test_markdown_matches_canonical():
    out = render_report(**_args(), fmt="markdown")
    assert "# Digital Footprint Exposure Report" in out
    assert "Spokeo" in out


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        render_report(**_args(), fmt="xml")


def test_valid_formats_exposed():
    assert set(VALID_FORMATS) >= {"markdown", "json", "html", "pdf"}
