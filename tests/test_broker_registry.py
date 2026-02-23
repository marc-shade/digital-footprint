import yaml
from pathlib import Path
from digital_footprint.broker_registry import load_broker_yaml, load_all_brokers, validate_broker_yaml


def test_load_single_broker_yaml(tmp_path):
    broker_file = tmp_path / "testbroker.yaml"
    broker_file.write_text(yaml.dump({
        "name": "TestBroker",
        "url": "https://test.com",
        "category": "people_search",
        "opt_out": {"method": "email", "email": "privacy@test.com"},
        "difficulty": "easy",
        "recheck_days": 14,
    }))
    broker = load_broker_yaml(broker_file)
    assert broker.slug == "testbroker"
    assert broker.name == "TestBroker"
    assert broker.opt_out_method == "email"
    assert broker.opt_out_email == "privacy@test.com"


def test_load_all_brokers(tmp_path):
    for name in ["alpha", "beta", "gamma"]:
        (tmp_path / f"{name}.yaml").write_text(yaml.dump({
            "name": name.title(),
            "url": f"https://{name}.com",
            "category": "people_search",
        }))
    # Should skip non-yaml and underscore-prefixed files
    (tmp_path / "_schema.yaml").write_text("schema: true")
    (tmp_path / "readme.txt").write_text("not a broker")

    brokers = load_all_brokers(tmp_path)
    assert len(brokers) == 3
    slugs = {b.slug for b in brokers}
    assert slugs == {"alpha", "beta", "gamma"}


def test_validate_broker_yaml_valid():
    data = {
        "name": "Test",
        "url": "https://test.com",
        "category": "people_search",
    }
    errors = validate_broker_yaml(data)
    assert errors == []


def test_validate_broker_yaml_missing_required():
    data = {"name": "Test"}
    errors = validate_broker_yaml(data)
    assert len(errors) > 0
    assert any("url" in e for e in errors)


def test_real_brokers_dir_has_files():
    """Verify the actual brokers directory has at least one YAML file."""
    brokers_dir = Path(__file__).parent.parent / "digital_footprint" / "brokers"
    if brokers_dir.exists():
        yamls = list(brokers_dir.glob("*.yaml"))
        # Filter out schema
        yamls = [y for y in yamls if not y.name.startswith("_")]
        assert len(yamls) >= 1, "Should have at least one broker YAML"
