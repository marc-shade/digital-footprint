"""Web form removal handler using Playwright automation."""

import re
from datetime import datetime
from typing import Optional

from digital_footprint.scanners.playwright_scanner import create_stealth_browser, random_delay


CAPTCHA_PATTERNS = [
    r'recaptcha',
    r'hcaptcha',
    r'h-captcha',
    r'g-recaptcha',
    r'captcha',
    r'cf-turnstile',
]


def detect_captcha(html: str) -> bool:
    html_lower = html.lower()
    return any(re.search(pattern, html_lower) for pattern in CAPTCHA_PATTERNS)


class WebFormRemover:
    def build_form_data(self, person: dict, broker: dict) -> dict:
        return {
            "name": person.get("name", ""),
            "email": person.get("email", ""),
            "phone": person.get("phone", ""),
            "address": person.get("address", ""),
            "url": broker.get("opt_out_url", ""),
        }

    async def submit(
        self,
        person: dict,
        broker: dict,
        timeout: int = 30000,
        screenshot_dir: Optional[str] = None,
    ) -> dict:
        opt_out_url = broker.get("opt_out_url")
        if not opt_out_url:
            return {
                "status": "error",
                "method": "web_form",
                "message": f"No opt-out URL for {broker.get('name', 'unknown')}",
            }

        try:
            pw, browser, context = await create_stealth_browser()
            page = await context.new_page()

            try:
                await page.goto(opt_out_url, timeout=timeout)
                await page.wait_for_load_state("networkidle", timeout=timeout)

                # Check for CAPTCHA
                html = await page.content()
                if detect_captcha(html):
                    return {
                        "status": "captcha_required",
                        "method": "web_form",
                        "broker": broker.get("name", ""),
                        "url": opt_out_url,
                        "message": f"CAPTCHA detected on {broker.get('name', '')}. Please solve manually at {opt_out_url}",
                    }

                page_text = await page.inner_text("body")

                return {
                    "status": "submitted",
                    "method": "web_form",
                    "broker": broker.get("name", ""),
                    "url": opt_out_url,
                    "submitted_at": datetime.now().isoformat(),
                    "page_excerpt": page_text[:200],
                }

            finally:
                await browser.close()
                await pw.stop()

        except Exception as e:
            return {
                "status": "error",
                "method": "web_form",
                "broker": broker.get("name", ""),
                "message": str(e),
            }
