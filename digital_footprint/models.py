"""Data models for Digital Footprint."""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Person:
    name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)
    relation: str = "self"
    date_of_birth: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Broker:
    slug: str
    name: str
    url: str
    category: str
    opt_out_method: Optional[str] = None
    opt_out_url: Optional[str] = None
    opt_out_email: Optional[str] = None
    difficulty: str = "medium"
    automatable: bool = False
    recheck_days: int = 30
    ccpa_compliant: bool = False
    gdpr_compliant: bool = False
    notes: Optional[str] = None
    id: Optional[int] = None

    @classmethod
    def from_yaml(cls, slug: str, data: dict[str, Any]) -> "Broker":
        opt_out = data.get("opt_out", {})
        return cls(
            slug=slug,
            name=data["name"],
            url=data["url"],
            category=data["category"],
            opt_out_method=opt_out.get("method"),
            opt_out_url=opt_out.get("url"),
            opt_out_email=opt_out.get("email"),
            difficulty=data.get("difficulty", "medium"),
            automatable=data.get("automatable", False),
            recheck_days=data.get("recheck_days", 30),
            ccpa_compliant=data.get("ccpa_compliant", False),
            gdpr_compliant=data.get("gdpr_compliant", False),
            notes=data.get("notes"),
        )


@dataclass
class Finding:
    person_id: int
    source: str
    finding_type: str
    data_found: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    url: Optional[str] = None
    screenshot_path: Optional[str] = None
    status: str = "active"
    broker_id: Optional[int] = None
    id: Optional[int] = None
    discovered_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Removal:
    person_id: int
    broker_id: int
    method: str
    finding_id: Optional[int] = None
    status: str = "pending"
    submitted_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    attempts: int = 0
    next_check_at: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Breach:
    person_id: int
    breach_name: str
    source: str
    breach_date: Optional[str] = None
    data_types: list[str] = field(default_factory=list)
    severity: str = "medium"
    discovered_at: Optional[str] = None
    action_taken: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Scan:
    scan_type: str
    person_id: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    findings_count: int = 0
    new_findings: int = 0
    removed_count: int = 0
    status: str = "running"
    id: Optional[int] = None
