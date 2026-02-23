"""MCP monitoring tool helpers."""

import asyncio
import json
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan, format_dark_web_report


def do_dark_web_monitor_sync(email: str, hibp_api_key: Optional[str] = None) -> str:
    """Run dark web monitoring (sync wrapper for MCP tool)."""
    if not email:
        return json.dumps({"status": "error", "message": "Provide an email address."})

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(asyncio.run, run_dark_web_scan(email, hibp_api_key=hibp_api_key)).result()
        else:
            results = loop.run_until_complete(run_dark_web_scan(email, hibp_api_key=hibp_api_key))
    except RuntimeError:
        results = asyncio.run(run_dark_web_scan(email, hibp_api_key=hibp_api_key))

    return format_dark_web_report(results)


def do_social_audit(person_id: int, db: Database) -> str:
    """Run social media audit for a person."""
    person = db.get_person(person_id)
    if not person:
        return f"Person {person_id} not found."

    if not person.usernames:
        return json.dumps({
            "person": person.name,
            "profiles_audited": 0,
            "message": "No usernames stored for this person. Add usernames first.",
        })

    platforms = [
        ("https://twitter.com/{}", "twitter"),
        ("https://github.com/{}", "github"),
        ("https://instagram.com/{}", "instagram"),
        ("https://reddit.com/user/{}", "reddit"),
        ("https://tiktok.com/@{}", "tiktok"),
    ]

    profile_urls = []
    for username in person.usernames:
        for url_pattern, platform in platforms:
            profile_urls.append(url_pattern.format(username))

    return json.dumps({
        "person": person.name,
        "profiles_audited": 0,
        "profiles_to_check": profile_urls,
        "message": f"Found {len(profile_urls)} profiles to audit across {len(platforms)} platforms for {len(person.usernames)} usernames. Use /monitor skill for full Playwright-based audit.",
    }, indent=2)
