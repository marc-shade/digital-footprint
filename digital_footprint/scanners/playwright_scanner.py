"""Base Playwright scanner with stealth capabilities."""

import asyncio
import random
from typing import Optional


async def create_stealth_browser():
    """Create a stealth Playwright browser context."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
    )

    try:
        from playwright_stealth import stealth_async
        await stealth_async(context)
    except ImportError:
        pass  # Stealth not available, continue without

    return pw, browser, context


async def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """Random delay between requests to avoid rate limiting."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))
