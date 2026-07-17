"""Broker scanner using Playwright for site checking."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrokerScanResult:
    broker_slug: str
    broker_name: str
    url: str
    found: bool
    page_text: Optional[str] = None
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    # status distinguishes the four outcomes that `found` alone conflates:
    #   found      -- the person's name appeared in a real results page
    #   not_found  -- a real page loaded and the name was absent
    #   blocked    -- an anti-bot challenge / empty shell was served (we learn
    #                 NOTHING about listing; must NOT be reported as clean)
    #   error      -- navigation failed (timeout, DNS, etc.)
    status: str = "not_found"
    blocked: bool = False

    @property
    def risk_level(self) -> str:
        return "high" if self.found else "low"


# Markers of an anti-bot challenge / interstitial rather than real content.
# Lowercased substring match against the page title + body.
_CHALLENGE_MARKERS = (
    "just a moment",              # Cloudflare
    "checking your browser",      # Cloudflare legacy
    "attention required",         # Cloudflare block
    "cf-browser-verification",
    "enable javascript and cookies to continue",
    "verify you are human",
    "verifying you are human",
    "luktelėkite",                # DataDome interstitial (observed on FastPeopleSearch)
    "loading search results",     # DataDome placeholder that never resolves
    "please wait while we",
    "ddos protection by",
    "px-captcha",                 # PerimeterX
    "captcha-delivery",
    "access denied",
    "request blocked",
    "unusual traffic",
)


def detect_challenge(title: str, body: str) -> bool:
    """True if the page looks like an anti-bot challenge / empty shell.

    Two signals: (1) a known challenge marker in title/body, or (2) an
    essentially empty body (a JS-challenge shell renders no text). Either
    means we did NOT see real results and cannot conclude the person is absent.
    """
    blob = f"{title or ''}\n{body or ''}".lower()
    if any(marker in blob for marker in _CHALLENGE_MARKERS):
        return True
    if len((body or "").strip()) < 40:
        return True
    return False


def build_search_url(
    url_pattern: str,
    first_name: str,
    last_name: str,
    state: str = "",
    city: str = "",
) -> str:
    """Build a broker search URL from a pattern and person data."""
    return (
        url_pattern
        .replace("{first}", first_name)
        .replace("{last}", last_name)
        .replace("{state}", state)
        .replace("{city}", city)
    )


def check_name_in_results(page_text: str, first_name: str, last_name: str) -> bool:
    """Check if a person's full name appears in page text (fuzzy)."""
    text_lower = page_text.lower()
    first_lower = first_name.lower()
    last_lower = last_name.lower()
    # Both first and last name must appear
    return first_lower in text_lower and last_lower in text_lower


async def scan_broker(
    broker_slug: str,
    broker_name: str,
    url_pattern: str,
    first_name: str,
    last_name: str,
    state: str = "",
    city: str = "",
    timeout: int = 30000,
) -> BrokerScanResult:
    """Scan a single broker site for a person's data."""
    from digital_footprint.scanners.playwright_scanner import (
        create_stealth_browser,
        random_delay,
    )

    url = build_search_url(url_pattern, first_name, last_name, state, city)

    try:
        pw, browser, context = await create_stealth_browser()
        page = await context.new_page()

        try:
            await page.goto(url, timeout=timeout)
            # networkidle can hang forever behind a JS challenge; fall back to
            # domcontentloaded so a challenged site is reported as blocked
            # rather than raising a bare timeout.
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout)
            except Exception:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)

            try:
                title = await page.title()
            except Exception:
                title = ""
            page_text = await page.inner_text("body")

            if detect_challenge(title, page_text):
                return BrokerScanResult(
                    broker_slug=broker_slug, broker_name=broker_name, url=url,
                    found=False, status="blocked", blocked=True,
                    error="anti-bot challenge or empty shell (listing status unknown)",
                )

            found = check_name_in_results(page_text, first_name, last_name)
            return BrokerScanResult(
                broker_slug=broker_slug,
                broker_name=broker_name,
                url=url,
                found=found,
                status="found" if found else "not_found",
                page_text=page_text[:500] if found else None,
            )
        finally:
            await browser.close()
            await pw.stop()
            await random_delay()

    except Exception as e:
        return BrokerScanResult(
            broker_slug=broker_slug,
            broker_name=broker_name,
            url=url,
            found=False,
            status="error",
            error=str(e),
        )


async def scan_all_brokers(
    brokers: list[dict],
    first_name: str,
    last_name: str,
    state: str = "",
    city: str = "",
) -> list[BrokerScanResult]:
    """Scan all brokers that have search URL patterns."""
    results = []
    for broker in brokers:
        url_pattern = broker.get("search_url_pattern")
        if not url_pattern:
            continue
        result = await scan_broker(
            broker_slug=broker["slug"],
            broker_name=broker["name"],
            url_pattern=url_pattern,
            first_name=first_name,
            last_name=last_name,
            state=state,
            city=city,
        )
        results.append(result)
    return results
