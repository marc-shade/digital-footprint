"""Base Playwright scanner with stealth capabilities."""

import asyncio
import random
from typing import Optional

# Common desktop user agents for rotation
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1680, "height": 1050},
]


async def create_stealth_browser(headless: bool = True):
    """Create a stealth Playwright browser context with anti-detection."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    browser = await pw.chromium.launch(
        headless=headless,
        args=launch_args,
    )

    ua = random.choice(_USER_AGENTS)
    viewport = random.choice(_VIEWPORTS)

    context = await browser.new_context(
        user_agent=ua,
        viewport=viewport,
        locale="en-US",
        timezone_id="America/New_York",
        color_scheme="light",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    )

    # Remove webdriver flag
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
    """)

    try:
        from playwright_stealth import stealth_async
        await stealth_async(context)
    except ImportError:
        pass  # Stealth not available, init_script above provides baseline

    return pw, browser, context


async def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """Random delay between requests to avoid rate limiting."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))
