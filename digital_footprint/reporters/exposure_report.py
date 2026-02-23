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
            lines.append(f"- **{b['broker_name']}**: {b.get('url', 'N/A')}")
    else:
        lines.append("No data broker listings detected.")
    lines.append("")

    # Breach results
    hibp = breach_results.get("hibp_breaches", [])
    dehashed = breach_results.get("dehashed_records", [])
    lines.append(f"## Data Breaches ({len(hibp)} breaches, {len(dehashed)} records)")
    lines.append("")
    if hibp:
        for b in hibp:
            lines.append(f"- **{b['name']}** ({b.get('breach_date', 'unknown')}): {', '.join(b.get('data_classes', []))}")
    if dehashed:
        for r in dehashed:
            db_name = r.get("database_name", "Unknown")
            lines.append(f"- **{db_name}**: Exposed record found")
    if not hibp and not dehashed:
        lines.append("No breach records found.")
    lines.append("")

    # Username results
    lines.append(f"## Online Accounts ({len(username_results)} found)")
    lines.append("")
    if username_results:
        for u in username_results:
            lines.append(f"- **{u['site_name']}**: {u.get('url', 'N/A')}")
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
