"""Dark web scanner using HIBP paste endpoint and Ahmia.fi clearnet search."""

import re
from dataclasses import dataclass
from typing import Optional

import httpx

HIBP_BASE = "https://haveibeenpwned.com/api/v3"
AHMIA_BASE = "https://ahmia.fi"


@dataclass
class PasteResult:
    source: str
    paste_id: str
    title: Optional[str]
    date: Optional[str]
    email_count: int = 0

    @property
    def severity(self) -> str:
        return "high"


@dataclass
class AhmiaResult:
    title: str
    url: str
    snippet: str = ""

    @property
    def severity(self) -> str:
        keywords = {"password", "credential", "dump", "leak", "breach"}
        text = (self.title + " " + self.snippet).lower()
        if any(kw in text for kw in keywords):
            return "critical"
        return "high"


async def check_hibp_pastes(
    email: str, api_key: Optional[str] = None
) -> list[PasteResult]:
    """Check HIBP paste endpoint for email appearances in paste sites."""
    if not api_key:
        return []

    headers = {
        "hibp-api-key": api_key,
        "user-agent": "DigitalFootprint-Scanner",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{HIBP_BASE}/pasteaccount/{email}",
            headers=headers,
        )

    if resp.status_code != 200:
        return []

    pastes = resp.json()
    if not isinstance(pastes, list):
        return []

    return [
        PasteResult(
            source=p.get("Source", "Unknown"),
            paste_id=p.get("Id", ""),
            title=p.get("Title"),
            date=p.get("Date"),
            email_count=p.get("EmailCount", 0),
        )
        for p in pastes
    ]


async def search_ahmia(email: str) -> list[AhmiaResult]:
    """Search Ahmia.fi (clearnet Tor search engine) for email exposure."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{AHMIA_BASE}/search/",
            params={"q": email},
        )

    if resp.status_code != 200:
        return []

    return _parse_ahmia_html(resp.text)


def _parse_ahmia_html(html: str) -> list[AhmiaResult]:
    """Parse Ahmia search results HTML."""
    results = []
    pattern = re.compile(
        r'<li\s+class="result">\s*<h4><a\s+href="([^"]+)">([^<]+)</a></h4>\s*<p>([^<]*)</p>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        url, title, snippet = match.groups()
        results.append(AhmiaResult(
            title=title.strip(),
            url=url.strip(),
            snippet=snippet.strip(),
        ))
    return results
