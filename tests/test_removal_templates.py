"""Tests for Jinja2 removal email templates."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = Path(__file__).parent.parent / "digital_footprint" / "removers" / "templates"


def _render(template_name: str, **ctx) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tmpl = env.get_template(template_name)
    return tmpl.render(**ctx)


def _base_ctx():
    return {
        "person": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "address": "123 Main St, Springfield, IL",
            "state": "California",
        },
        "broker": {
            "name": "TestBroker",
            "url": "https://testbroker.com",
            "opt_out_email": "privacy@testbroker.com",
        },
        "date": "2026-02-23",
        "reference_id": "REF-001",
    }


def test_ccpa_deletion_template():
    result = _render("ccpa_deletion.j2", **_base_ctx())
    assert "CCPA" in result
    assert "John Doe" in result
    assert "john@example.com" in result
    assert "TestBroker" in result
    assert "REF-001" in result
    assert "1798.105" in result


def test_ccpa_do_not_sell_template():
    result = _render("ccpa_do_not_sell.j2", **_base_ctx())
    assert "Do Not Sell" in result or "opt out of the sale" in result
    assert "1798.120" in result
    assert "John Doe" in result


def test_gdpr_erasure_template():
    result = _render("gdpr_erasure.j2", **_base_ctx())
    assert "GDPR" in result
    assert "Article 17" in result
    assert "John Doe" in result


def test_followup_template():
    ctx = _base_ctx()
    ctx["original_date"] = "2026-01-01"
    ctx["days_elapsed"] = 50
    result = _render("followup.j2", **ctx)
    assert "FOLLOW-UP" in result or "follow-up" in result.lower()
    assert "2026-01-01" in result
    assert "50" in result


def test_generic_removal_template():
    result = _render("generic_removal.j2", **_base_ctx())
    assert "removal" in result.lower()
    assert "John Doe" in result
    assert "TestBroker" in result


def test_template_handles_missing_optional_fields():
    ctx = _base_ctx()
    ctx["person"]["phone"] = ""
    ctx["person"]["address"] = ""
    result = _render("ccpa_deletion.j2", **ctx)
    assert "John Doe" in result
    assert "555-123-4567" not in result
