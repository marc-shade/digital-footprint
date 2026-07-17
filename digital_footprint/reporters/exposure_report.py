"""Exposure report generator."""

from datetime import datetime
from typing import Optional


RISK_WEIGHTS = {
    "critical": 25,
    "high": 10,
    "medium": 5,
    "low": 2,
}


def compute_risk_score(findings: list[dict]) -> int:
    """Compute overall risk score from findings (0-100)."""
    score = sum(RISK_WEIGHTS.get(f.get("risk_level", "medium"), 5) for f in findings)
    return min(score, 100)


def risk_label(score: int) -> str:
    """Convert numeric risk score to label."""
    if score >= 75:
        return "CRITICAL"
    elif score >= 50:
        return "HIGH"
    elif score >= 25:
        return "MODERATE"
    return "LOW"


def generate_exposure_report(
    person_name: str,
    broker_results: list[dict],
    breach_results: dict,
    username_results: list[dict],
    dork_results: list[dict],
) -> str:
    """Generate a Markdown exposure report."""
    # Collect all findings for risk scoring
    all_findings = []
    for b in broker_results:
        if b.get("found"):
            all_findings.append(b)
    for breach in breach_results.get("hibp_breaches", []):
        all_findings.append({"risk_level": breach.get("severity", "medium")})
    for rec in breach_results.get("dehashed_records", []):
        all_findings.append({"risk_level": rec.get("severity", "medium")})
    for u in username_results:
        all_findings.append(u)
    for d in dork_results:
        all_findings.append(d)

    score = compute_risk_score(all_findings)
    label = risk_label(score)

    lines = [
        f"# Digital Footprint Exposure Report",
        f"",
        f"**Subject:** {person_name}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Risk Score: {score}/100 ({label})**",
        f"",
        f"---",
        f"",
    ]

    # Broker findings
    found_brokers = [b for b in broker_results if b.get("found")]
    lines.append(f"## Data Broker Exposure ({len(found_brokers)} found)")
    lines.append("")
    if found_brokers:
        for b in found_brokers:
            name = b.get("broker_name") or b.get("broker_slug") or "Unknown broker"
            lines.append(f"- **{name}**: {b.get('url', 'N/A')}")
    else:
        lines.append("No data broker listings detected.")
    lines.append("")

    # Breach results
    hibp = breach_results.get("hibp_breaches", [])
    dehashed = breach_results.get("dehashed_records", [])
    breach_checked = breach_results.get("checked", True)
    breach_errors = breach_results.get("errors", [])
    lines.append(f"## Data Breaches ({len(hibp)} breaches, {len(dehashed)} records)")
    lines.append("")
    if hibp:
        for b in hibp:
            bname = b.get("name") or b.get("breach_name") or "Unknown breach"
            classes = b.get("data_classes") or b.get("data_types") or []
            lines.append(f"- **{bname}** ({b.get('breach_date', 'unknown')}): {', '.join(classes)}")
    if dehashed:
        for r in dehashed:
            db_name = r.get("database_name", "Unknown")
            lines.append(f"- **{db_name}**: Exposed record found")
    if not hibp and not dehashed:
        if breach_checked:
            lines.append("No breach records found.")
        else:
            # Do NOT imply "clean" when the check could not run (bad key, rate
            # limit): that would be a false all-clear.
            detail = f" ({'; '.join(breach_errors)})" if breach_errors else ""
            lines.append(f"**Breach check could not be completed{detail}.** "
                         "This is NOT an all-clear — configure a valid HIBP API key and re-run.")
    lines.append("")

    # Username results
    lines.append(f"## Online Accounts ({len(username_results)} found)")
    lines.append("")
    if username_results:
        for u in username_results:
            site = u.get("site_name") or u.get("site") or "Unknown site"
            lines.append(f"- **{site}**: {u.get('url', 'N/A')}")
    else:
        lines.append("No accounts discovered.")
    lines.append("")

    # Dork results
    lines.append(f"## Google Exposure ({len(dork_results)} results)")
    lines.append("")
    if dork_results:
        for d in dork_results:
            lines.append(f"- [{d.get('title', 'Link')}]({d.get('url', '')})")
    else:
        lines.append("No exposed documents or pastes found.")
    lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    if found_brokers:
        lines.append("1. **Submit opt-out requests** to all detected data brokers")
    if hibp:
        lines.append("2. **Change passwords** for all breached accounts")
        lines.append("3. **Enable 2FA** on critical accounts")
    if username_results:
        lines.append("4. **Review privacy settings** on discovered accounts")
    if not all_findings:
        lines.append("Your digital footprint appears minimal. Continue monitoring.")
    lines.append("")

    return "\n".join(lines)
