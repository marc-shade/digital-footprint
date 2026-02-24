"""Web form removal handler using Playwright automation."""

import re
from datetime import datetime
from pathlib import Path
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

# Common field selectors mapped to person dict keys
_FIELD_SELECTORS = {
    "name": [
        'input[name*="name" i]:not([name*="user" i])',
        'input[placeholder*="name" i]',
        'input[id*="name" i]:not([id*="user" i])',
        'input[aria-label*="name" i]',
    ],
    "first_name": [
        'input[name*="first" i]',
        'input[placeholder*="first" i]',
        'input[id*="first" i]',
    ],
    "last_name": [
        'input[name*="last" i]',
        'input[placeholder*="last" i]',
        'input[id*="last" i]',
    ],
    "email": [
        'input[type="email"]',
        'input[name*="email" i]',
        'input[placeholder*="email" i]',
        'input[id*="email" i]',
    ],
    "phone": [
        'input[type="tel"]',
        'input[name*="phone" i]',
        'input[placeholder*="phone" i]',
        'input[id*="phone" i]',
    ],
    "address": [
        'input[name*="address" i]',
        'input[placeholder*="address" i]',
        'input[id*="address" i]',
        'textarea[name*="address" i]',
    ],
}

_SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Submit")',
    'button:has-text("Opt Out")',
    'button:has-text("Remove")',
    'button:has-text("Delete")',
    'button:has-text("Request")',
    'button:has-text("Send")',
]


def detect_captcha(html: str) -> bool:
    html_lower = html.lower()
    return any(re.search(pattern, html_lower) for pattern in CAPTCHA_PATTERNS)


class WebFormRemover:
    def build_form_data(self, person: dict, broker: dict) -> dict:
        # Normalize list fields to singular
        email = person.get("email", "")
        if not email and "emails" in person:
            emails = person["emails"]
            email = emails[0] if emails else ""

        phone = person.get("phone", "")
        if not phone and "phones" in person:
            phones = person["phones"]
            phone = phones[0] if phones else ""

        address = person.get("address", "")
        if not address and "addresses" in person:
            addrs = person["addresses"]
            address = addrs[0] if addrs else ""

        name = person.get("name", "")
        parts = name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        return {
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "address": address,
            "url": broker.get("opt_out_url", ""),
        }

    async def _fill_field(self, page, selectors: list[str], value: str) -> bool:
        """Try to fill a field using multiple selectors. Returns True if filled."""
        if not value:
            return False
        for selector in selectors:
            try:
                el = page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    await el.fill(value)
                    return True
            except Exception:
                continue
        return False

    async def _fill_form(self, page, form_data: dict) -> int:
        """Fill form fields using heuristic selectors. Returns count of fields filled."""
        filled = 0
        for field_key, selectors in _FIELD_SELECTORS.items():
            value = form_data.get(field_key, "")
            if await self._fill_field(page, selectors, value):
                filled += 1
                await random_delay(0.3, 0.8)
        return filled

    async def _click_submit(self, page) -> bool:
        """Try to click a submit button. Returns True if clicked."""
        for selector in _SUBMIT_SELECTORS:
            try:
                el = page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    return True
            except Exception:
                continue
        return False

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
                        "message": f"CAPTCHA detected on {broker.get('name', '')}. Manual action required at {opt_out_url}",
                    }

                # Fill the form
                form_data = self.build_form_data(person, broker)
                fields_filled = await self._fill_form(page, form_data)

                if fields_filled == 0:
                    page_text = await page.inner_text("body")
                    return {
                        "status": "no_form_found",
                        "method": "web_form",
                        "broker": broker.get("name", ""),
                        "url": opt_out_url,
                        "message": f"No fillable form fields found on {broker.get('name', '')}. Manual action may be required.",
                        "page_excerpt": page_text[:200],
                    }

                # Take screenshot before submit if requested
                if screenshot_dir:
                    ss_path = Path(screenshot_dir) / f"{broker.get('name', 'unknown')}_pre_submit.png"
                    await page.screenshot(path=str(ss_path))

                # Submit the form
                submitted = await self._click_submit(page)

                if submitted:
                    await random_delay(2.0, 4.0)
                    await page.wait_for_load_state("networkidle", timeout=10000)

                    # Take screenshot after submit
                    if screenshot_dir:
                        ss_path = Path(screenshot_dir) / f"{broker.get('name', 'unknown')}_post_submit.png"
                        await page.screenshot(path=str(ss_path))

                page_text = await page.inner_text("body")

                return {
                    "status": "submitted" if submitted else "filled_not_submitted",
                    "method": "web_form",
                    "broker": broker.get("name", ""),
                    "url": opt_out_url,
                    "fields_filled": fields_filled,
                    "form_submitted": submitted,
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
