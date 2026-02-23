# Phase 4: Dark Web Monitoring + Social Media Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dark web exposure detection (HIBP pastes, Ahmia.fi), email registration checking (holehe), and public social media profile auditing (Playwright) to complete the monitoring layer.

**Architecture:** Three new scanner modules following Phase 2's pattern (one per source), plus a monitor orchestrator. Each scanner is independent, returns dataclasses, and is tested with mocked external calls.

**Tech Stack:** Python 3.13, httpx (HTTP), Playwright (social scraping), holehe (subprocess CLI), FastMCP (tools)

---

### Task 1: Dark Web Scanner — HIBP Pastes

**Files:**
- Create: `digital_footprint/scanners/dark_web_scanner.py`
- Test: `tests/test_dark_web_scanner.py`

**Step 1: Write the failing test**

Create `tests/test_dark_web_scanner.py`:

```python
"""Tests for dark web scanner (HIBP pastes + Ahmia.fi)."""

import pytest
from unittest.mock import MagicMock, patch
from digital_footprint.scanners.dark_web_scanner import (
    PasteResult,
    AhmiaResult,
    check_hibp_pastes,
    search_ahmia,
)


@pytest.mark.asyncio
@patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient")
async def test_check_hibp_pastes_found(mock_client_class):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "Source": "Pastebin",
            "Id": "abc123",
            "Title": "Leaked emails dump",
            "Date": "2024-01-15T00:00:00Z",
            "EmailCount": 500,
        },
        {
            "Source": "Ghostbin",
            "Id": "def456",
            "Title": None,
            "Date": "2023-06-01T00:00:00Z",
            "EmailCount": 100,
        },
    ]

    mock_client = MagicMock()
    mock_client.get = MagicMock(return_value=mock_resp)
    mock_client.__aenter__ = MagicMock(return_value=mock_client)
    mock_client.__aexit__ = MagicMock(return_value=None)
    mock_client_class.return_value = mock_client

    results = await check_hibp_pastes("test@example.com", api_key="test-key")
    assert len(results) == 2
    assert results[0].source == "Pastebin"
    assert results[0].title == "Leaked emails dump"
    assert results[0].severity == "high"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient")
async def test_check_hibp_pastes_not_found(mock_client_class):
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = MagicMock()
    mock_client.get = MagicMock(return_value=mock_resp)
    mock_client.__aenter__ = MagicMock(return_value=mock_client)
    mock_client.__aexit__ = MagicMock(return_value=None)
    mock_client_class.return_value = mock_client

    results = await check_hibp_pastes("clean@example.com", api_key="test-key")
    assert results == []


@pytest.mark.asyncio
async def test_check_hibp_pastes_no_key():
    results = await check_hibp_pastes("test@example.com", api_key="")
    assert results == []


def test_paste_result_severity():
    r = PasteResult(source="Pastebin", paste_id="abc", title="dump", date="2024-01-01", email_count=500)
    assert r.severity == "high"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient")
async def test_search_ahmia_found(mock_client_class):
    html = """
    <html><body>
    <li class="result">
      <h4><a href="http://example.onion/page1">Leaked Database Dump</a></h4>
      <p>Contains email addresses and passwords...</p>
      <cite>http://example.onion/page1</cite>
    </li>
    <li class="result">
      <h4><a href="http://example2.onion/data">Data Collection</a></h4>
      <p>Email list compilation</p>
      <cite>http://example2.onion/data</cite>
    </li>
    </body></html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    mock_client = MagicMock()
    mock_client.get = MagicMock(return_value=mock_resp)
    mock_client.__aenter__ = MagicMock(return_value=mock_client)
    mock_client.__aexit__ = MagicMock(return_value=None)
    mock_client_class.return_value = mock_client

    results = await search_ahmia("test@example.com")
    assert len(results) == 2
    assert results[0].title == "Leaked Database Dump"
    assert results[0].url == "http://example.onion/page1"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.dark_web_scanner.httpx.AsyncClient")
async def test_search_ahmia_no_results(mock_client_class):
    html = "<html><body><p>No results found</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    mock_client = MagicMock()
    mock_client.get = MagicMock(return_value=mock_resp)
    mock_client.__aenter__ = MagicMock(return_value=mock_client)
    mock_client.__aexit__ = MagicMock(return_value=None)
    mock_client_class.return_value = mock_client

    results = await search_ahmia("clean@example.com")
    assert results == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_dark_web_scanner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'digital_footprint.scanners.dark_web_scanner'`

**Step 3: Implement dark_web_scanner.py**

Create `digital_footprint/scanners/dark_web_scanner.py`:

```python
"""Dark web scanner using HIBP paste endpoint and Ahmia.fi clearnet search."""

import re
from dataclasses import dataclass
from typing import Optional

import httpx

HIBP_BASE = "https://haveibeenpwned.com/api/v3"
AHMIA_BASE = "https://ahmia.fi"


@dataclass
class PasteResult:
    source: str
    paste_id: str
    title: Optional[str]
    date: Optional[str]
    email_count: int = 0

    @property
    def severity(self) -> str:
        return "high"


@dataclass
class AhmiaResult:
    title: str
    url: str
    snippet: str = ""

    @property
    def severity(self) -> str:
        keywords = {"password", "credential", "dump", "leak", "breach"}
        text = (self.title + " " + self.snippet).lower()
        if any(kw in text for kw in keywords):
            return "critical"
        return "high"


async def check_hibp_pastes(
    email: str, api_key: Optional[str] = None
) -> list[PasteResult]:
    """Check HIBP paste endpoint for email appearances in paste sites."""
    if not api_key:
        return []

    headers = {
        "hibp-api-key": api_key,
        "user-agent": "DigitalFootprint-Scanner",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{HIBP_BASE}/pasteaccount/{email}",
            headers=headers,
        )

    if resp.status_code == 404:
        return []

    pastes = resp.json()
    return [
        PasteResult(
            source=p.get("Source", "Unknown"),
            paste_id=p.get("Id", ""),
            title=p.get("Title"),
            date=p.get("Date"),
            email_count=p.get("EmailCount", 0),
        )
        for p in pastes
    ]


async def search_ahmia(email: str) -> list[AhmiaResult]:
    """Search Ahmia.fi (clearnet Tor search engine) for email exposure."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{AHMIA_BASE}/search/",
            params={"q": email},
        )

    if resp.status_code != 200:
        return []

    return _parse_ahmia_html(resp.text)


def _parse_ahmia_html(html: str) -> list[AhmiaResult]:
    """Parse Ahmia search results HTML."""
    results = []
    pattern = re.compile(
        r'<li\s+class="result">\s*<h4><a\s+href="([^"]+)">([^<]+)</a></h4>\s*<p>([^<]*)</p>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        url, title, snippet = match.groups()
        results.append(AhmiaResult(
            title=title.strip(),
            url=url.strip(),
            snippet=snippet.strip(),
        ))
    return results
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_dark_web_scanner.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add digital_footprint/scanners/dark_web_scanner.py tests/test_dark_web_scanner.py
git commit -m "feat: dark web scanner with HIBP paste and Ahmia.fi integration"
```

---

### Task 2: holehe Scanner — Email Registration Check

**Files:**
- Create: `digital_footprint/scanners/holehe_scanner.py`
- Test: `tests/test_holehe_scanner.py`

**Step 1: Write the failing test**

Create `tests/test_holehe_scanner.py`:

```python
"""Tests for holehe email registration scanner."""

import pytest
from unittest.mock import patch, AsyncMock
from digital_footprint.scanners.holehe_scanner import (
    HoleheResult,
    parse_holehe_output,
    check_email_registrations,
)


def test_parse_holehe_output():
    stdout = "twitter.com,Used,social\ninstagram.com,Used,social\nnetflix.com,Used,streaming\nadobe.com,Used,software\ndating-site.com,Used,dating\nunknown.com,Not Used,other\n"
    results = parse_holehe_output(stdout)
    assert len(results) == 5
    assert results[0].service == "twitter.com"
    assert results[0].exists is True


def test_parse_holehe_output_empty():
    results = parse_holehe_output("")
    assert results == []


def test_holehe_result_risk_level_high():
    r = HoleheResult(service="dating-site.com", exists=True, category="dating")
    assert r.risk_level == "high"


def test_holehe_result_risk_level_medium():
    r = HoleheResult(service="twitter.com", exists=True, category="social")
    assert r.risk_level == "medium"


def test_holehe_result_risk_level_low():
    r = HoleheResult(service="netflix.com", exists=True, category="streaming")
    assert r.risk_level == "low"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.holehe_scanner.asyncio.create_subprocess_exec")
async def test_check_email_registrations(mock_exec):
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        b"twitter.com,Used,social\ninstagram.com,Used,social\n",
        b"",
    )
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    results = await check_email_registrations("test@example.com")
    assert len(results) == 2
    assert results[0].service == "twitter.com"


@pytest.mark.asyncio
@patch("digital_footprint.scanners.holehe_scanner.asyncio.create_subprocess_exec")
async def test_check_email_registrations_holehe_not_installed(mock_exec):
    mock_exec.side_effect = FileNotFoundError("holehe not found")
    results = await check_email_registrations("test@example.com")
    assert results == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_holehe_scanner.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement holehe_scanner.py**

Create `digital_footprint/scanners/holehe_scanner.py`:

```python
"""Email registration scanner using holehe CLI."""

import asyncio
from dataclasses import dataclass


HIGH_RISK_CATEGORIES = {"dating", "adult", "financial", "gambling"}
MEDIUM_RISK_CATEGORIES = {"social", "photo", "video", "gaming", "forum"}


@dataclass
class HoleheResult:
    service: str
    exists: bool
    category: str = "other"

    @property
    def risk_level(self) -> str:
        if self.category in HIGH_RISK_CATEGORIES:
            return "high"
        if self.category in MEDIUM_RISK_CATEGORIES:
            return "medium"
        return "low"


def parse_holehe_output(stdout: str) -> list[HoleheResult]:
    """Parse holehe CSV-style stdout output."""
    results = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip().split(",")
        if len(parts) < 2:
            continue
        service = parts[0].strip()
        status = parts[1].strip()
        category = parts[2].strip() if len(parts) > 2 else "other"
        if status == "Used":
            results.append(HoleheResult(
                service=service,
                exists=True,
                category=category,
            ))
    return results


async def check_email_registrations(
    email: str, timeout: int = 60
) -> list[HoleheResult]:
    """Check which services an email is registered with using holehe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "holehe", email,
            "--only-used", "--csv",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return parse_holehe_output(stdout.decode())
    except FileNotFoundError:
        return []
    except Exception:
        return []
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_holehe_scanner.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add digital_footprint/scanners/holehe_scanner.py tests/test_holehe_scanner.py
git commit -m "feat: holehe email registration scanner"
```

---

### Task 3: Social Media Auditor — Public Profile Scraping

**Files:**
- Create: `digital_footprint/scanners/social_auditor.py`
- Test: `tests/test_social_auditor.py`

**Step 1: Write the failing test**

Create `tests/test_social_auditor.py`:

```python
"""Tests for social media public profile auditor."""

import pytest
from unittest.mock import AsyncMock, patch
from digital_footprint.scanners.social_auditor import (
    SocialAuditResult,
    detect_platform,
    extract_meta_tags,
    compute_privacy_score,
    audit_profile,
    PLATFORM_SELECTORS,
)


def test_detect_platform_twitter():
    assert detect_platform("https://twitter.com/johndoe") == "twitter"
    assert detect_platform("https://x.com/johndoe") == "twitter"


def test_detect_platform_github():
    assert detect_platform("https://github.com/johndoe") == "github"


def test_detect_platform_instagram():
    assert detect_platform("https://instagram.com/johndoe") == "instagram"


def test_detect_platform_unknown():
    assert detect_platform("https://obscuresite.com/johndoe") == "unknown"


def test_extract_meta_tags():
    html = '<html><head><meta property="og:title" content="John Doe"><meta property="og:description" content="Developer in NYC. john@test.com"></head></html>'
    tags = extract_meta_tags(html)
    assert tags["og:title"] == "John Doe"
    assert "john@test.com" in tags["og:description"]


def test_compute_privacy_score_all_private():
    result = SocialAuditResult(platform="twitter", url="https://twitter.com/anon", visible_fields={}, pii_flags=[])
    assert compute_privacy_score(result) >= 80


def test_compute_privacy_score_exposed():
    result = SocialAuditResult(
        platform="twitter",
        url="https://twitter.com/johndoe",
        visible_fields={"name": "John Doe", "email": "john@test.com"},
        pii_flags=["email_visible", "phone_visible", "real_name_visible", "location_visible"],
    )
    score = compute_privacy_score(result)
    assert score <= 30


def test_platform_selectors_exist():
    assert "twitter" in PLATFORM_SELECTORS
    assert "github" in PLATFORM_SELECTORS
    assert "instagram" in PLATFORM_SELECTORS


@pytest.mark.asyncio
@patch("digital_footprint.scanners.social_auditor.create_stealth_browser")
async def test_audit_profile(mock_browser):
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value='<html><head><meta property="og:title" content="John Doe"><meta property="og:description" content="Software dev. john@test.com | 555-1234"></head><body><div>John Doe</div></body></html>')
    mock_page.inner_text = AsyncMock(return_value="John Doe\nSoftware developer in NYC\njohn@test.com")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    result = await audit_profile("https://twitter.com/johndoe")
    assert result.platform == "twitter"
    assert "email_visible" in result.pii_flags


@pytest.mark.asyncio
@patch("digital_footprint.scanners.social_auditor.create_stealth_browser")
async def test_audit_profile_error(mock_browser):
    mock_browser.side_effect = Exception("Browser launch failed")
    result = await audit_profile("https://twitter.com/johndoe")
    assert result.platform == "twitter"
    assert result.error is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_social_auditor.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement social_auditor.py**

Create `digital_footprint/scanners/social_auditor.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_social_auditor.py -v`
Expected: 10 passed

**Step 5: Commit**

```bash
git add digital_footprint/scanners/social_auditor.py tests/test_social_auditor.py
git commit -m "feat: social media public profile auditor with PII detection"
```

---

### Task 4: Dark Web Monitor — Orchestrator

**Files:**
- Create: `digital_footprint/monitors/__init__.py`
- Create: `digital_footprint/monitors/dark_web_monitor.py`
- Test: `tests/test_dark_web_monitor.py`

**Step 1: Write the failing test**

Create `tests/test_dark_web_monitor.py`:

```python
"""Tests for dark web monitoring orchestrator."""

import pytest
from unittest.mock import patch, AsyncMock
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan, format_dark_web_report


@pytest.mark.asyncio
@patch("digital_footprint.monitors.dark_web_monitor.check_email_registrations")
@patch("digital_footprint.monitors.dark_web_monitor.search_ahmia")
@patch("digital_footprint.monitors.dark_web_monitor.check_hibp_pastes")
async def test_run_dark_web_scan(mock_pastes, mock_ahmia, mock_holehe):
    from digital_footprint.scanners.dark_web_scanner import PasteResult, AhmiaResult
    from digital_footprint.scanners.holehe_scanner import HoleheResult

    mock_pastes.return_value = [PasteResult(source="Pastebin", paste_id="abc", title="Dump", date="2024-01-01")]
    mock_ahmia.return_value = [AhmiaResult(title="Leak Forum", url="http://example.onion/leak")]
    mock_holehe.return_value = [
        HoleheResult(service="twitter.com", exists=True, category="social"),
        HoleheResult(service="netflix.com", exists=True, category="streaming"),
    ]

    results = await run_dark_web_scan("test@example.com", hibp_api_key="key")
    assert results["paste_count"] == 1
    assert results["ahmia_count"] == 1
    assert results["holehe_count"] == 2
    assert results["total"] == 4


@pytest.mark.asyncio
@patch("digital_footprint.monitors.dark_web_monitor.check_email_registrations")
@patch("digital_footprint.monitors.dark_web_monitor.search_ahmia")
@patch("digital_footprint.monitors.dark_web_monitor.check_hibp_pastes")
async def test_run_dark_web_scan_no_results(mock_pastes, mock_ahmia, mock_holehe):
    mock_pastes.return_value = []
    mock_ahmia.return_value = []
    mock_holehe.return_value = []
    results = await run_dark_web_scan("clean@example.com", hibp_api_key="key")
    assert results["total"] == 0


def test_format_dark_web_report():
    results = {
        "email": "test@example.com",
        "paste_count": 1, "ahmia_count": 0, "holehe_count": 3, "total": 4,
        "pastes": [{"source": "Pastebin", "title": "Dump", "severity": "high"}],
        "ahmia_results": [],
        "holehe_results": [
            {"service": "twitter.com", "category": "social", "risk_level": "medium"},
            {"service": "netflix.com", "category": "streaming", "risk_level": "low"},
            {"service": "dating.com", "category": "dating", "risk_level": "high"},
        ],
    }
    report = format_dark_web_report(results)
    assert "test@example.com" in report
    assert "Pastebin" in report
    assert "twitter.com" in report
    assert "dating.com" in report
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_dark_web_monitor.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement the monitor**

Create `digital_footprint/monitors/__init__.py`:

```python
"""Monitoring modules for Digital Footprint."""
```

Create `digital_footprint/monitors/dark_web_monitor.py`:

```python
"""Dark web monitoring orchestrator combining paste, Ahmia, and holehe scanners."""

from typing import Optional

from digital_footprint.scanners.dark_web_scanner import check_hibp_pastes, search_ahmia
from digital_footprint.scanners.holehe_scanner import check_email_registrations


async def run_dark_web_scan(email: str, hibp_api_key: Optional[str] = None) -> dict:
    """Run all dark web monitoring scans for an email."""
    pastes = await check_hibp_pastes(email, api_key=hibp_api_key)
    ahmia_results = await search_ahmia(email)
    holehe_results = await check_email_registrations(email)

    return {
        "email": email,
        "pastes": [{"source": p.source, "paste_id": p.paste_id, "title": p.title, "date": p.date, "severity": p.severity} for p in pastes],
        "ahmia_results": [{"title": a.title, "url": a.url, "severity": a.severity} for a in ahmia_results],
        "holehe_results": [{"service": h.service, "category": h.category, "risk_level": h.risk_level} for h in holehe_results],
        "paste_count": len(pastes),
        "ahmia_count": len(ahmia_results),
        "holehe_count": len(holehe_results),
        "total": len(pastes) + len(ahmia_results) + len(holehe_results),
    }


def format_dark_web_report(results: dict) -> str:
    """Format dark web scan results as Markdown."""
    lines = [
        "# Dark Web Monitoring Report", "",
        f"**Email:** {results['email']}",
        f"**Total Findings:** {results['total']}", "",
    ]

    pastes = results.get("pastes", [])
    lines.append(f"## Paste Site Exposure ({len(pastes)} found)")
    lines.append("")
    if pastes:
        for p in pastes:
            lines.append(f"- **{p['source']}**: {p.get('title', 'Untitled')} ({p['severity']})")
    else:
        lines.append("No paste site exposure detected.")
    lines.append("")

    ahmia = results.get("ahmia_results", [])
    lines.append(f"## Dark Web References ({len(ahmia)} found)")
    lines.append("")
    if ahmia:
        for a in ahmia:
            lines.append(f"- **{a['title']}**: {a['url']} ({a['severity']})")
    else:
        lines.append("No dark web references found.")
    lines.append("")

    holehe = results.get("holehe_results", [])
    lines.append(f"## Email Registered Services ({len(holehe)} found)")
    lines.append("")
    if holehe:
        high = [h for h in holehe if h["risk_level"] == "high"]
        medium = [h for h in holehe if h["risk_level"] == "medium"]
        low = [h for h in holehe if h["risk_level"] == "low"]
        if high:
            lines.append("**High Risk:**")
            for h in high:
                lines.append(f"  - {h['service']}")
        if medium:
            lines.append("**Medium Risk:**")
            for h in medium:
                lines.append(f"  - {h['service']}")
        if low:
            lines.append("**Low Risk:**")
            for h in low:
                lines.append(f"  - {h['service']}")
    else:
        lines.append("No registered services detected.")
    lines.append("")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_dark_web_monitor.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add digital_footprint/monitors/ tests/test_dark_web_monitor.py
git commit -m "feat: dark web monitoring orchestrator (pastes + Ahmia + holehe)"
```

---

### Task 5: MCP Tool Helpers

**Files:**
- Create: `digital_footprint/tools/monitor_tools.py`
- Test: `tests/test_monitor_tools.py`

**Step 1: Write the failing test**

Create `tests/test_monitor_tools.py`:

```python
"""Tests for monitoring MCP tool helpers."""

import json
from unittest.mock import patch, AsyncMock, MagicMock
from digital_footprint.tools.monitor_tools import do_dark_web_monitor_sync, do_social_audit


@patch("digital_footprint.tools.monitor_tools.run_dark_web_scan", new_callable=AsyncMock)
def test_do_dark_web_monitor(mock_scan):
    mock_scan.return_value = {
        "email": "test@example.com",
        "paste_count": 1, "ahmia_count": 0, "holehe_count": 2, "total": 3,
        "pastes": [{"source": "Pastebin", "title": "Dump", "severity": "high"}],
        "ahmia_results": [],
        "holehe_results": [{"service": "twitter.com", "category": "social", "risk_level": "medium"}],
    }
    result = do_dark_web_monitor_sync("test@example.com", hibp_api_key="key")
    assert "test@example.com" in result
    assert "Pastebin" in result


def test_do_social_audit_no_person():
    db = MagicMock()
    db.get_person.return_value = None
    result = do_social_audit(person_id=999, db=db)
    assert "not found" in result.lower()


def test_do_social_audit_no_usernames():
    db = MagicMock()
    person = MagicMock()
    person.usernames = []
    person.name = "John Doe"
    db.get_person.return_value = person
    result = do_social_audit(person_id=1, db=db)
    parsed = json.loads(result)
    assert parsed["profiles_audited"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_monitor_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement monitor_tools.py**

Create `digital_footprint/tools/monitor_tools.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_monitor_tools.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add digital_footprint/tools/monitor_tools.py tests/test_monitor_tools.py
git commit -m "feat: monitoring MCP tool helpers (dark web + social audit)"
```

---

### Task 6: Wire Up MCP Tools in server.py

**Files:**
- Modify: `server.py`

**Step 1: Replace Phase 4 stubs in server.py**

Find the section:

```python
# --- Stub tools for future phases ---

@mcp.tool()
def footprint_dark_web_monitor(email: str = None) -> str:
    """Monitor dark web sources for exposed personal data. [Phase 4 - Not yet implemented]"""
    return "Dark web monitoring not yet implemented. Coming in Phase 4."

@mcp.tool()
def footprint_social_audit(person_id: int = 1) -> str:
    """Audit social media privacy settings and exposure. [Phase 4 - Not yet implemented]"""
    return "Social media audit not yet implemented. Coming in Phase 4."
```

Replace with:

```python
# --- Phase 4: Monitoring tools ---

from digital_footprint.tools.monitor_tools import do_dark_web_monitor_sync, do_social_audit

@mcp.tool()
def footprint_dark_web_monitor(email: str = None) -> str:
    """Monitor dark web sources for exposed personal data (paste sites, Ahmia.fi, holehe)."""
    if not email:
        return "Provide an email address to monitor."
    return do_dark_web_monitor_sync(email=email, hibp_api_key=config.hibp_api_key)

@mcp.tool()
def footprint_social_audit(person_id: int = 1) -> str:
    """Audit social media privacy settings and public exposure."""
    return do_social_audit(person_id=person_id, db=db)
```

**Step 2: Run all tests**

Run: `pytest --tb=short -q`
Expected: All pass

**Step 3: Commit**

```bash
git add server.py
git commit -m "feat: wire up Phase 4 MCP tools (dark web monitor, social audit)"
```

---

### Task 7: /monitor Skill

**Files:**
- Create: `.claude/skills/monitor.md`

**Step 1: Create the skill**

Create `.claude/skills/monitor.md`:

```markdown
---
name: monitor
description: Run dark web monitoring and social media privacy audit
---

# /monitor - Dark Web Monitoring & Social Audit

Check for dark web exposure and audit social media privacy.

## Usage

`/monitor` - Full monitoring scan for default person
`/monitor dark` - Dark web scan only (paste sites, Ahmia, holehe)
`/monitor social` - Social media audit only
`/monitor <email>` - Dark web scan for specific email

## Steps

### Full monitoring scan:
1. Call `footprint_list_persons` to find the person
2. Call `footprint_dark_web_monitor` with their primary email
3. Call `footprint_social_audit` with their person ID
4. Present combined results with risk assessment

### Dark web only:
1. Call `footprint_dark_web_monitor` with the email
2. Present paste site findings, dark web references, and registered services
3. Highlight high-risk findings (dating sites, financial services, dark web mentions)

### Social audit only:
1. Call `footprint_social_audit` with person ID
2. Show which platforms have public profiles
3. Flag PII exposure (email, phone, real name, location visible)
4. Give per-platform privacy score

## Recommendations
- For paste site exposure: change passwords immediately, enable 2FA
- For holehe high-risk services: review and delete unused accounts
- For social PII exposure: update privacy settings on flagged platforms
```

**Step 2: Commit**

```bash
git add .claude/skills/monitor.md
git commit -m "feat: /monitor skill for dark web and social media auditing"
```

---

### Task 8: Full Test Verification

**Step 1: Run entire test suite**

Run: `pytest --tb=short -v`
Expected: All tests pass. Should be approximately 111 existing + ~29 new = ~140 tests.

**Step 2: Verify all imports**

Run: `python -c "from digital_footprint.scanners.dark_web_scanner import check_hibp_pastes, search_ahmia; from digital_footprint.scanners.holehe_scanner import check_email_registrations; from digital_footprint.scanners.social_auditor import audit_profile; from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan; print('All imports OK')"`
Expected: `All imports OK`

**Step 3: MCP server smoke test**

Run: `timeout 3 python server.py 2>&1 || true`
Expected: Server starts without import errors

**Step 4: Done**

If everything passes, Phase 4 is complete. No stubs remaining in server.py.
