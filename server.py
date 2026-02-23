#!/usr/bin/env python3
"""
Digital Footprint MCP Server
Personal data removal and privacy protection.
"""

import json

from fastmcp import FastMCP

from digital_footprint.config import get_config
from digital_footprint.db import Database
from digital_footprint.broker_registry import load_all_brokers
from digital_footprint.tools.person_tools import register_person_tools
from digital_footprint.tools.broker_tools import register_broker_tools
from digital_footprint.tools.status_tools import register_status_tools

# Initialize
config = get_config()
db = Database(config)
db.initialize()

# Load broker registry into database
brokers = load_all_brokers(config.brokers_dir)
for broker in brokers:
    db.insert_broker(broker)

# Create MCP server
mcp = FastMCP("digital-footprint")

# Register implemented tools
register_person_tools(mcp, db)
register_broker_tools(mcp, db)
register_status_tools(mcp, db)


# --- Phase 2: Discovery tools ---

from digital_footprint.tools.scan_tools import do_breach_check, do_exposure_report

@mcp.tool()
async def footprint_scan(person_id: int = None, email: str = None) -> str:
    """Run a full exposure scan for a person (broker check, breach check, username search)."""
    if not person_id and not email:
        return "Provide person_id or email to scan."

    if person_id:
        person = db.get_person(person_id)
        if not person:
            return f"Person {person_id} not found."
        email = person.emails[0] if person.emails else None

    results = {}
    if email:
        breach_result = await do_breach_check(
            email=email,
            hibp_api_key=config.hibp_api_key,
            dehashed_api_key=config.dehashed_api_key,
        )
        results["breach_check"] = breach_result

    return json.dumps(results, indent=2) if results else "No scannable data found."

@mcp.tool()
async def footprint_breach_check(email: str = None, username: str = None) -> str:
    """Check for credential exposure in data breaches via HIBP and DeHashed."""
    if not email:
        return "Provide an email address to check."
    return await do_breach_check(
        email=email,
        hibp_api_key=config.hibp_api_key,
        dehashed_api_key=config.dehashed_api_key,
    )

@mcp.tool()
async def footprint_username_search(username: str) -> str:
    """Search for a username across 3,000+ sites using Maigret."""
    import json as _json
    from digital_footprint.scanners.username_scanner import search_username
    results = await search_username(username)
    return _json.dumps([
        {"site": r.site_name, "url": r.url, "risk": r.risk_level}
        for r in results
    ], indent=2)

@mcp.tool()
def footprint_exposure_report(person_id: int = 1) -> str:
    """Generate a comprehensive exposure report for a person."""
    return do_exposure_report(person_id=person_id, db=db)

@mcp.tool()
def footprint_google_dork(name: str, additional_terms: str = None) -> str:
    """Build Google dork queries to find exposed personal data. Returns queries to run manually."""
    import json as _json
    from digital_footprint.scanners.google_dorker import build_dork_queries
    queries = build_dork_queries(name=name, email=additional_terms)
    return _json.dumps({"name": name, "queries": queries, "count": len(queries)}, indent=2)

@mcp.tool()
def footprint_broker_check(broker_slug: str, person_id: int = 1) -> str:
    """Check a specific data broker for a person's data. Requires Playwright browser."""
    return "Broker scanning requires Playwright. Use footprint_scan for a full scan, or run the /exposure skill."


# --- Phase 3: Removal tools ---

from digital_footprint.tools.removal_tools import do_broker_remove, do_removal_status, do_verify_removals

@mcp.tool()
def footprint_broker_remove(broker_slug: str, person_id: int = 1) -> str:
    """Submit a removal request to a specific data broker."""
    return do_broker_remove(
        broker_slug=broker_slug,
        person_id=person_id,
        db=db,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_password=config.smtp_password,
    )

@mcp.tool()
def footprint_removal_status(person_id: int = None) -> str:
    """Get status of all pending removal requests."""
    return do_removal_status(person_id=person_id or 1, db=db)

@mcp.tool()
def footprint_verify_removals(person_id: int = 1) -> str:
    """Verify submitted removal requests by re-scanning broker sites."""
    return do_verify_removals(person_id=person_id, db=db)


# --- Stub tools for future phases ---

@mcp.tool()
def footprint_dark_web_monitor(email: str = None) -> str:
    """Monitor dark web sources for exposed personal data. [Phase 4 - Not yet implemented]"""
    return "Dark web monitoring not yet implemented. Coming in Phase 4."

@mcp.tool()
def footprint_social_audit(person_id: int = 1) -> str:
    """Audit social media privacy settings and exposure. [Phase 4 - Not yet implemented]"""
    return "Social media audit not yet implemented. Coming in Phase 4."


if __name__ == "__main__":
    mcp.run()
