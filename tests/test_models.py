import json
from digital_footprint.models import Person, Broker, Finding, Removal, Breach, Scan


def test_person_creation():
    p = Person(name="Marc Shade", emails=["marc@example.com"])
    assert p.name == "Marc Shade"
    assert p.emails == ["marc@example.com"]
    assert p.relation == "self"
    assert p.phones == []


def test_person_to_dict():
    p = Person(name="Marc Shade", emails=["marc@example.com"], phones=["555-0100"])
    d = p.to_dict()
    assert d["name"] == "Marc Shade"
    assert d["emails"] == ["marc@example.com"]
    assert d["phones"] == ["555-0100"]


def test_broker_creation():
    b = Broker(
        slug="spokeo",
        name="Spokeo",
        url="https://www.spokeo.com",
        category="people_search",
        opt_out_method="web_form",
    )
    assert b.slug == "spokeo"
    assert b.difficulty == "medium"
    assert b.recheck_days == 30


def test_finding_creation():
    f = Finding(
        person_id=1,
        source="broker",
        finding_type="profile",
        data_found={"name": "Marc Shade", "address": "123 Main St"},
    )
    assert f.risk_level == "medium"
    assert f.status == "active"
    assert f.data_found["name"] == "Marc Shade"


def test_broker_from_yaml_dict():
    yaml_data = {
        "name": "Spokeo",
        "url": "https://www.spokeo.com",
        "category": "people_search",
        "opt_out": {
            "method": "web_form",
            "url": "https://www.spokeo.com/optout",
            "captcha": True,
            "email_verification": True,
            "time_to_removal": "24-72 hours",
        },
        "automatable": True,
        "difficulty": "easy",
        "recheck_days": 30,
        "ccpa_compliant": True,
    }
    b = Broker.from_yaml("spokeo", yaml_data)
    assert b.name == "Spokeo"
    assert b.opt_out_method == "web_form"
    assert b.opt_out_url == "https://www.spokeo.com/optout"
    assert b.difficulty == "easy"
    assert b.automatable is True
    assert b.ccpa_compliant is True
