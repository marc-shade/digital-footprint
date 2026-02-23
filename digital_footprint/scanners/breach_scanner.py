"""Breach scanner using HIBP and DeHashed APIs."""

from dataclasses import dataclass, field
from typing import Optional

import httpx


HIBP_BASE = "https://haveibeenpwned.com/api/v3"
DEHASHED_BASE = "https://api.dehashed.com"


@dataclass
class HibpBreach:
    name: str
    title: str
    domain: str
    breach_date: str
    data_classes: list[str] = field(default_factory=list)
    is_verified: bool = False

    @property
    def severity(self) -> str:
        critical_types = {"Passwords", "Credit cards", "Social security numbers"}
        if critical_types & set(self.data_classes):
            return "critical"
        high_types = {"Phone numbers", "Physical addresses", "IP addresses"}
        if high_types & set(self.data_classes):
            return "high"
        return "medium"


@dataclass
class DehashedRecord:
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    hashed_password: Optional[str] = None
    name: Optional[str] = None
    database_name: Optional[str] = None

    @property
    def severity(self) -> str:
        if self.password:
            return "critical"
        if self.hashed_password:
            return "high"
        return "medium"


async def check_hibp(email: str, api_key: Optional[str] = None) -> list[HibpBreach]:
    """Check Have I Been Pwned for breaches affecting this email."""
    if not api_key:
        return []

    headers = {
        "hibp-api-key": api_key,
        "user-agent": "DigitalFootprint-Scanner",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{HIBP_BASE}/breachedaccount/{email}",
            headers=headers,
            params={"truncateResponse": "false"},
        )

    if resp.status_code == 404:
        return []

    breaches = resp.json()
    return [
        HibpBreach(
            name=b["Name"],
            title=b["Title"],
            domain=b.get("Domain", ""),
            breach_date=b.get("BreachDate", ""),
            data_classes=b.get("DataClasses", []),
            is_verified=b.get("IsVerified", False),
        )
        for b in breaches
    ]


async def check_dehashed(
    email: str, api_key: Optional[str] = None
) -> list[DehashedRecord]:
    """Check DeHashed for breach records containing this email."""
    if not api_key:
        return []

    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DEHASHED_BASE}/search",
            headers=headers,
            params={"query": f"email:{email}"},
            auth=("email@example.com", api_key),
        )

    if resp.status_code != 200:
        return []

    data = resp.json()
    entries = data.get("entries", [])
    return [
        DehashedRecord(
            email=e.get("email"),
            username=e.get("username"),
            password=e.get("password"),
            hashed_password=e.get("hashed_password"),
            name=e.get("name"),
            database_name=e.get("database_name"),
        )
        for e in entries
    ]


async def scan_breaches(
    email: str,
    hibp_api_key: Optional[str] = None,
    dehashed_api_key: Optional[str] = None,
) -> dict:
    """Run all breach checks for an email address."""
    hibp_results = await check_hibp(email, api_key=hibp_api_key)
    dehashed_results = await check_dehashed(email, api_key=dehashed_api_key)

    return {
        "email": email,
        "hibp_breaches": hibp_results,
        "hibp_count": len(hibp_results),
        "dehashed_records": dehashed_results,
        "dehashed_count": len(dehashed_results),
        "total": len(hibp_results) + len(dehashed_results),
    }
