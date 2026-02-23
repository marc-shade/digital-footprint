"""Google dorking scanner for finding exposed personal data."""

from dataclasses import dataclass
from typing import Optional


HIGH_RISK_DOMAINS = {
    "pastebin.com", "paste.ee", "ghostbin.com", "hastebin.com",
    "doxbin.com", "doxbin.org",
}


@dataclass
class DorkResult:
    query: str
    url: str
    title: str
    snippet: str

    @property
    def risk_level(self) -> str:
        url_lower = self.url.lower()
        if any(domain in url_lower for domain in HIGH_RISK_DOMAINS):
            return "high"
        if url_lower.endswith(".pdf") or url_lower.endswith(".doc") or url_lower.endswith(".docx"):
            return "high"
        return "medium"


def build_dork_queries(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> list[str]:
    """Build Google dork queries for finding exposed personal data."""
    queries = []

    # Name-based queries
    queries.append(f'"{name}"')

    if email:
        queries.append(f'"{name}" "{email}"')
        queries.append(f'site:pastebin.com "{email}"')
        queries.append(f'"{email}"')

    if phone:
        queries.append(f'"{name}" "{phone}"')
        queries.append(f'"{phone}"')

    if address:
        queries.append(f'"{name}" "{address}"')

    # Document exposure
    queries.append(f'filetype:pdf "{name}"')
    queries.append(f'filetype:xls "{name}"')

    return queries


def parse_search_results(
    raw_results: list[dict], query: str
) -> list[DorkResult]:
    """Parse raw search results into DorkResult objects."""
    return [
        DorkResult(
            query=query,
            url=r["url"],
            title=r.get("title", ""),
            snippet=r.get("snippet", ""),
        )
        for r in raw_results
    ]
