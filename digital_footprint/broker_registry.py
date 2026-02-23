"""Load and validate broker YAML definitions."""

from pathlib import Path
from typing import Optional

import yaml

from digital_footprint.models import Broker

REQUIRED_FIELDS = {"name", "url", "category"}
VALID_CATEGORIES = {
    "people_search", "background_check", "public_records", "marketing",
    "social_aggregator", "property", "financial", "genealogy",
    "reverse_lookup", "image_search",
}
VALID_METHODS = {"web_form", "email", "api", "phone", "mail"}
VALID_DIFFICULTIES = {"easy", "medium", "hard", "manual"}


def validate_broker_yaml(data: dict) -> list[str]:
    """Validate a broker YAML dictionary. Returns list of error strings."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    if "category" in data and data["category"] not in VALID_CATEGORIES:
        errors.append(f"Invalid category: {data['category']}. Valid: {VALID_CATEGORIES}")
    if "difficulty" in data and data["difficulty"] not in VALID_DIFFICULTIES:
        errors.append(f"Invalid difficulty: {data['difficulty']}. Valid: {VALID_DIFFICULTIES}")
    opt_out = data.get("opt_out", {})
    if "method" in opt_out and opt_out["method"] not in VALID_METHODS:
        errors.append(f"Invalid opt_out method: {opt_out['method']}. Valid: {VALID_METHODS}")
    return errors


def load_broker_yaml(path: Path) -> Broker:
    """Load a single broker YAML file and return a Broker model."""
    with open(path) as f:
        data = yaml.safe_load(f)
    slug = path.stem
    return Broker.from_yaml(slug, data)


def load_all_brokers(brokers_dir: Path) -> list[Broker]:
    """Load all broker YAML files from a directory."""
    brokers = []
    for path in sorted(brokers_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        brokers.append(load_broker_yaml(path))
    return brokers
