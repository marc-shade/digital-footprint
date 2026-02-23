"""Dark web monitoring orchestrator combining paste, Ahmia, and holehe scanners."""

from typing import Optional

from digital_footprint.scanners.dark_web_scanner import check_hibp_pastes, search_ahmia
from digital_footprint.scanners.holehe_scanner import check_email_registrations


async def run_dark_web_scan(email: str, hibp_api_key: Optional[str] = None) -> dict:
    """Run all dark web monitoring scans for an email."""
    pastes = await check_hibp_pastes(email, api_key=hibp_api_key)
    ahmia_results = await search_ahmia(email)
    holehe_results = await check_email_registrations(email)

    return {
        "email": email,
        "pastes": [{"source": p.source, "paste_id": p.paste_id, "title": p.title, "date": p.date, "severity": p.severity} for p in pastes],
        "ahmia_results": [{"title": a.title, "url": a.url, "severity": a.severity} for a in ahmia_results],
        "holehe_results": [{"service": h.service, "category": h.category, "risk_level": h.risk_level} for h in holehe_results],
        "paste_count": len(pastes),
        "ahmia_count": len(ahmia_results),
        "holehe_count": len(holehe_results),
        "total": len(pastes) + len(ahmia_results) + len(holehe_results),
    }


def format_dark_web_report(results: dict) -> str:
    """Format dark web scan results as Markdown."""
    lines = [
        "# Dark Web Monitoring Report", "",
        f"**Email:** {results['email']}",
        f"**Total Findings:** {results['total']}", "",
    ]

    pastes = results.get("pastes", [])
    lines.append(f"## Paste Site Exposure ({len(pastes)} found)")
    lines.append("")
    if pastes:
        for p in pastes:
            lines.append(f"- **{p['source']}**: {p.get('title', 'Untitled')} ({p['severity']})")
    else:
        lines.append("No paste site exposure detected.")
    lines.append("")

    ahmia = results.get("ahmia_results", [])
    lines.append(f"## Dark Web References ({len(ahmia)} found)")
    lines.append("")
    if ahmia:
        for a in ahmia:
            lines.append(f"- **{a['title']}**: {a['url']} ({a['severity']})")
    else:
        lines.append("No dark web references found.")
    lines.append("")

    holehe = results.get("holehe_results", [])
    lines.append(f"## Email Registered Services ({len(holehe)} found)")
    lines.append("")
    if holehe:
        high = [h for h in holehe if h["risk_level"] == "high"]
        medium = [h for h in holehe if h["risk_level"] == "medium"]
        low = [h for h in holehe if h["risk_level"] == "low"]
        if high:
            lines.append("**High Risk:**")
            for h in high:
                lines.append(f"  - {h['service']}")
        if medium:
            lines.append("**Medium Risk:**")
            for h in medium:
                lines.append(f"  - {h['service']}")
        if low:
            lines.append("**Low Risk:**")
            for h in low:
                lines.append(f"  - {h['service']}")
    else:
        lines.append("No registered services detected.")
    lines.append("")

    return "\n".join(lines)
