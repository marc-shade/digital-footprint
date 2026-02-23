"""Social media public profile auditor using Playwright."""

import re
from dataclasses import dataclass, field
from typing import Optional

from digital_footprint.scanners.playwright_scanner import create_stealth_browser


@dataclass
class SocialAuditResult:
    platform: str
    url: str
    visible_fields: dict = field(default_factory=dict)
    pii_flags: list[str] = field(default_factory=list)
    privacy_score: int = 100
    error: Optional[str] = None


PLATFORM_SELECTORS = {
    "twitter": {"name": "[data-testid='UserName']", "bio": "[data-testid='UserDescription']", "location": "[data-testid='UserLocation']"},
    "github": {"name": ".p-name", "bio": ".p-note", "location": ".p-label"},
    "instagram": {"name": "header h2", "bio": "header section > div"},
    "linkedin": {"name": ".top-card-layout__title", "bio": ".top-card-layout__headline", "location": ".top-card-layout__first-subline"},
    "reddit": {"name": "h1"},
    "tiktok": {"name": "[data-e2e='user-title']", "bio": "[data-e2e='user-bio']"},
    "facebook": {"name": "h1"},
}

PLATFORM_DOMAINS = {
    "twitter.com": "twitter", "x.com": "twitter",
    "github.com": "github", "instagram.com": "instagram",
    "linkedin.com": "linkedin", "reddit.com": "reddit",
    "tiktok.com": "tiktok", "facebook.com": "facebook",
}

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')


def detect_platform(url: str) -> str:
    for domain, platform in PLATFORM_DOMAINS.items():
        if domain in url:
            return platform
    return "unknown"


def extract_meta_tags(html: str) -> dict:
    tags = {}
    pattern = re.compile(r'<meta\s+property="([^"]+)"\s+content="([^"]*)"', re.IGNORECASE)
    for match in pattern.finditer(html):
        tags[match.group(1)] = match.group(2)
    return tags


def _detect_pii(text: str) -> list[str]:
    flags = []
    if EMAIL_PATTERN.search(text):
        flags.append("email_visible")
    if PHONE_PATTERN.search(text):
        flags.append("phone_visible")
    location_keywords = {"located in", "based in", "lives in", "from "}
    if any(kw in text.lower() for kw in location_keywords):
        flags.append("location_visible")
    return flags


def compute_privacy_score(result: SocialAuditResult) -> int:
    score = 100
    deductions = {
        "email_visible": 30,
        "phone_visible": 30,
        "real_name_visible": 10,
        "location_visible": 15,
        "address_visible": 25,
    }
    for flag in result.pii_flags:
        score -= deductions.get(flag, 5)
    return max(score, 0)


async def audit_profile(url: str, timeout: int = 15000) -> SocialAuditResult:
    platform = detect_platform(url)
    try:
        pw, browser, context = await create_stealth_browser()
        page = await context.new_page()
        try:
            await page.goto(url, timeout=timeout)
            await page.wait_for_load_state("networkidle", timeout=timeout)
            html = await page.content()
            meta_tags = extract_meta_tags(html)
            page_text = await page.inner_text("body")
            visible_fields = {}
            if meta_tags.get("og:title"):
                visible_fields["name"] = meta_tags["og:title"]
            if meta_tags.get("og:description"):
                visible_fields["description"] = meta_tags["og:description"]
            all_text = " ".join([page_text, meta_tags.get("og:title", ""), meta_tags.get("og:description", "")])
            pii_flags = _detect_pii(all_text)
            name = visible_fields.get("name", "")
            if " " in name and name[0].isupper():
                pii_flags.append("real_name_visible")
            result = SocialAuditResult(platform=platform, url=url, visible_fields=visible_fields, pii_flags=pii_flags)
            result.privacy_score = compute_privacy_score(result)
            return result
        finally:
            await browser.close()
            await pw.stop()
    except Exception as e:
        return SocialAuditResult(platform=platform, url=url, error=str(e))


async def audit_profiles(urls: list[str]) -> list[SocialAuditResult]:
    results = []
    for url in urls:
        result = await audit_profile(url)
        results.append(result)
    return results
