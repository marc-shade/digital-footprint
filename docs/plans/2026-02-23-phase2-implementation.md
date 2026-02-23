# Phase 2: Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add scanning, breach checking, username search, Google dorking, and report generation to Digital Footprint.

**Architecture:** New `scanners/` package for all discovery engines, new `reporters/` package for report generation. Each scanner is a standalone module with pure functions. MCP server stubs get replaced with real implementations.

**Tech Stack:** playwright + playwright-stealth (browser), maigret (username search), httpx (async HTTP for APIs), existing SQLite DB

---

### Task 1: Add New Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Update requirements.txt**

Add these lines to `requirements.txt`:

```
playwright>=1.40
playwright-stealth>=1.0
maigret>=0.4
httpx>=0.27
```

**Step 2: Install dependencies**

Run:
```bash
.venv/bin/pip install -r requirements.txt
```

**Step 3: Install Playwright browsers**

Run:
```bash
.venv/bin/playwright install chromium
```

**Step 4: Verify imports work**

Run:
```bash
.venv/bin/python -c "import playwright; import httpx; print('OK')"
```
Expected: `OK`

**Step 5: Verify existing tests still pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 33 passed

**Step 6: Commit**

```bash
git add requirements.txt
git commit -m "feat: add Phase 2 dependencies (playwright, maigret, httpx)"
```

---

### Task 2: Breach Scanner (HIBP + DeHashed)

**Files:**
- Create: `digital_footprint/scanners/__init__.py`
- Create: `digital_footprint/scanners/breach_scanner.py`
- Create: `tests/test_breach_scanner.py`

**Step 1: Create scanners package**

Create `digital_footprint/scanners/__init__.py`:

```python
"""Discovery scanners for Digital Footprint."""
```

**Step 2: Write failing tests**

Create `tests/test_breach_scanner.py`:

```python
"""Tests for breach scanner (HIBP + DeHashed)."""

import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from digital_footprint.scanners.breach_scanner import (
    check_hibp,
    check_dehashed,
    scan_breaches,
    HibpBreach,
    DehashedRecord,
)


@pytest.fixture
def hibp_response():
    return [
        {
            "Name": "LinkedIn",
            "Title": "LinkedIn",
            "Domain": "linkedin.com",
            "BreachDate": "2012-05-05",
            "DataClasses": ["Email addresses", "Passwords"],
            "IsVerified": True,
        },
        {
            "Name": "Adobe",
            "Title": "Adobe",
            "Domain": "adobe.com",
            "BreachDate": "2013-10-04",
            "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
            "IsVerified": True,
        },
    ]


@pytest.fixture
def dehashed_response():
    return {
        "total": 1,
        "entries": [
            {
                "email": "test@example.com",
                "username": "testuser",
                "password": "hashed123",
                "hashed_password": "abc123hash",
                "name": "Test User",
                "database_name": "SomeDB",
            }
        ],
    }


@pytest.mark.asyncio
async def test_check_hibp_found(hibp_response):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = hibp_response

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await check_hibp("test@example.com", api_key="test-key")

    assert len(results) == 2
    assert isinstance(results[0], HibpBreach)
    assert results[0].name == "LinkedIn"
    assert results[0].breach_date == "2012-05-05"
    assert "Passwords" in results[0].data_classes


@pytest.mark.asyncio
async def test_check_hibp_not_found():
    mock_response = AsyncMock()
    mock_response.status_code = 404

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await check_hibp("clean@example.com", api_key="test-key")

    assert results == []


@pytest.mark.asyncio
async def test_check_hibp_no_api_key():
    results = await check_hibp("test@example.com", api_key=None)
    assert results == []


@pytest.mark.asyncio
async def test_check_dehashed_found(dehashed_response):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = dehashed_response

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await check_dehashed("test@example.com", api_key="test-key")

    assert len(results) == 1
    assert isinstance(results[0], DehashedRecord)
    assert results[0].email == "test@example.com"
    assert results[0].database_name == "SomeDB"


@pytest.mark.asyncio
async def test_check_dehashed_no_api_key():
    results = await check_dehashed("test@example.com", api_key=None)
    assert results == []


@pytest.mark.asyncio
async def test_scan_breaches_combines_sources(hibp_response, dehashed_response):
    mock_hibp_resp = AsyncMock()
    mock_hibp_resp.status_code = 200
    mock_hibp_resp.json.return_value = hibp_response

    mock_dh_resp = AsyncMock()
    mock_dh_resp.status_code = 200
    mock_dh_resp.json.return_value = dehashed_response

    with patch("digital_footprint.scanners.breach_scanner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = [mock_hibp_resp, mock_dh_resp]
        mock_client_cls.return_value = mock_client

        results = await scan_breaches(
            "test@example.com",
            hibp_api_key="test-key",
            dehashed_api_key="test-key",
        )

    assert results["hibp_count"] == 2
    assert results["dehashed_count"] == 1
    assert results["total"] == 3
```

**Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_breach_scanner.py -v`
Expected: FAIL (module not found)

**Step 4: Implement breach scanner**

Create `digital_footprint/scanners/breach_scanner.py`:

```python
"""Breach scanner using HIBP and DeHashed APIs."""

from dataclasses import dataclass, field
from typing import Optional

import httpx


HIBP_BASE = "https://haveibeenpwned.com/api/v3"
DEHASHED_BASE = "https://api.dehashed.com"


@dataclass
class HibpBreach:
    name: str
    title: str
    domain: str
    breach_date: str
    data_classes: list[str] = field(default_factory=list)
    is_verified: bool = False

    @property
    def severity(self) -> str:
        critical_types = {"Passwords", "Credit cards", "Social security numbers"}
        if critical_types & set(self.data_classes):
            return "critical"
        high_types = {"Phone numbers", "Physical addresses", "IP addresses"}
        if high_types & set(self.data_classes):
            return "high"
        return "medium"


@dataclass
class DehashedRecord:
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    hashed_password: Optional[str] = None
    name: Optional[str] = None
    database_name: Optional[str] = None

    @property
    def severity(self) -> str:
        if self.password:
            return "critical"
        if self.hashed_password:
            return "high"
        return "medium"


async def check_hibp(email: str, api_key: Optional[str] = None) -> list[HibpBreach]:
    """Check Have I Been Pwned for breaches affecting this email."""
    if not api_key:
        return []

    headers = {
        "hibp-api-key": api_key,
        "user-agent": "DigitalFootprint-Scanner",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{HIBP_BASE}/breachedaccount/{email}",
            headers=headers,
            params={"truncateResponse": "false"},
        )

    if resp.status_code == 404:
        return []

    breaches = resp.json()
    return [
        HibpBreach(
            name=b["Name"],
            title=b["Title"],
            domain=b.get("Domain", ""),
            breach_date=b.get("BreachDate", ""),
            data_classes=b.get("DataClasses", []),
            is_verified=b.get("IsVerified", False),
        )
        for b in breaches
    ]


async def check_dehashed(
    email: str, api_key: Optional[str] = None
) -> list[DehashedRecord]:
    """Check DeHashed for breach records containing this email."""
    if not api_key:
        return []

    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DEHASHED_BASE}/search",
            headers=headers,
            params={"query": f"email:{email}"},
            auth=("email@example.com", api_key),
        )

    if resp.status_code != 200:
        return []

    data = resp.json()
    entries = data.get("entries", [])
    return [
        DehashedRecord(
            email=e.get("email"),
            username=e.get("username"),
            password=e.get("password"),
            hashed_password=e.get("hashed_password"),
            name=e.get("name"),
            database_name=e.get("database_name"),
        )
        for e in entries
    ]


async def scan_breaches(
    email: str,
    hibp_api_key: Optional[str] = None,
    dehashed_api_key: Optional[str] = None,
) -> dict:
    """Run all breach checks for an email address."""
    hibp_results = await check_hibp(email, api_key=hibp_api_key)
    dehashed_results = await check_dehashed(email, api_key=dehashed_api_key)

    return {
        "email": email,
        "hibp_breaches": hibp_results,
        "hibp_count": len(hibp_results),
        "dehashed_records": dehashed_results,
        "dehashed_count": len(dehashed_results),
        "total": len(hibp_results) + len(dehashed_results),
    }
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_breach_scanner.py -v`
Expected: 7 passed

**Step 6: Commit**

```bash
git add digital_footprint/scanners/ tests/test_breach_scanner.py
git commit -m "feat: breach scanner with HIBP and DeHashed integration"
```

---

### Task 3: Username Scanner (Maigret Wrapper)

**Files:**
- Create: `digital_footprint/scanners/username_scanner.py`
- Create: `tests/test_username_scanner.py`

**Step 1: Write failing tests**

Create `tests/test_username_scanner.py`:

```python
"""Tests for username scanner (Maigret wrapper)."""

import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from digital_footprint.scanners.username_scanner import (
    search_username,
    parse_maigret_results,
    UsernameResult,
)


@pytest.fixture
def maigret_json_output():
    return {
        "testuser": {
            "GitHub": {
                "url_user": "https://github.com/testuser",
                "status": "Claimed",
                "tags": ["coding"],
            },
            "Twitter": {
                "url_user": "https://twitter.com/testuser",
                "status": "Claimed",
                "tags": ["social"],
            },
            "Reddit": {
                "url_user": "https://reddit.com/user/testuser",
                "status": "Claimed",
                "tags": ["social"],
            },
            "Instagram": {
                "url_user": "https://instagram.com/testuser",
                "status": "Available",
                "tags": ["social"],
            },
        }
    }


def test_parse_maigret_results(maigret_json_output):
    results = parse_maigret_results(maigret_json_output, "testuser")
    assert len(results) == 3  # Only "Claimed" entries
    assert all(isinstance(r, UsernameResult) for r in results)
    sites = {r.site_name for r in results}
    assert "GitHub" in sites
    assert "Twitter" in sites
    assert "Instagram" not in sites  # Available, not Claimed


def test_parse_maigret_results_empty():
    results = parse_maigret_results({}, "nobody")
    assert results == []


def test_username_result_risk_level():
    social = UsernameResult(site_name="Twitter", url="https://twitter.com/u", tags=["social"])
    assert social.risk_level == "medium"

    coding = UsernameResult(site_name="GitHub", url="https://github.com/u", tags=["coding"])
    assert coding.risk_level == "low"


@pytest.mark.asyncio
async def test_search_username_runs_maigret(tmp_path, maigret_json_output):
    output_file = tmp_path / "maigret_testuser.json"
    output_file.write_text(json.dumps(maigret_json_output))

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = ""
    mock_proc.stderr = ""

    with patch("digital_footprint.scanners.username_scanner.asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = mock_proc
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("digital_footprint.scanners.username_scanner._get_output_path", return_value=str(output_file)):
            results = await search_username("testuser")

    assert len(results) == 3
    assert results[0].site_name in {"GitHub", "Twitter", "Reddit"}
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_username_scanner.py -v`
Expected: FAIL (module not found)

**Step 3: Implement username scanner**

Create `digital_footprint/scanners/username_scanner.py`:

```python
"""Username scanner using Maigret."""

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class UsernameResult:
    site_name: str
    url: str
    tags: list[str] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        high_risk_tags = {"dating", "adult", "financial"}
        if high_risk_tags & set(self.tags):
            return "high"
        medium_risk_tags = {"social", "photo", "video"}
        if medium_risk_tags & set(self.tags):
            return "medium"
        return "low"


def _get_output_path(username: str) -> str:
    return str(Path(tempfile.gettempdir()) / f"maigret_{username}.json")


def parse_maigret_results(data: dict, username: str) -> list[UsernameResult]:
    """Parse Maigret JSON output into UsernameResult objects."""
    user_data = data.get(username, {})
    results = []
    for site_name, info in user_data.items():
        if info.get("status") == "Claimed":
            results.append(
                UsernameResult(
                    site_name=site_name,
                    url=info.get("url_user", ""),
                    tags=info.get("tags", []),
                )
            )
    return results


async def search_username(
    username: str, timeout: int = 120
) -> list[UsernameResult]:
    """Search for a username across sites using Maigret."""
    output_path = _get_output_path(username)

    proc = await asyncio.create_subprocess_exec(
        "maigret", username,
        "--json", output_path,
        "--timeout", str(timeout),
        "--no-color",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    output_file = Path(output_path)
    if not output_file.exists():
        return []

    data = json.loads(output_file.read_text())
    return parse_maigret_results(data, username)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_username_scanner.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add digital_footprint/scanners/username_scanner.py tests/test_username_scanner.py
git commit -m "feat: username scanner with Maigret integration"
```

---

### Task 4: Google Dorking Scanner

**Files:**
- Create: `digital_footprint/scanners/google_dorker.py`
- Create: `tests/test_google_dorker.py`

**Step 1: Write failing tests**

Create `tests/test_google_dorker.py`:

```python
"""Tests for Google dorking scanner."""

import pytest

from digital_footprint.scanners.google_dorker import (
    build_dork_queries,
    DorkResult,
    parse_search_results,
)


def test_build_dork_queries_name_only():
    queries = build_dork_queries(name="John Doe")
    assert len(queries) >= 1
    assert any('"John Doe"' in q for q in queries)


def test_build_dork_queries_with_email():
    queries = build_dork_queries(name="John Doe", email="john@example.com")
    assert any('"john@example.com"' in q for q in queries)
    assert any("site:pastebin.com" in q for q in queries)


def test_build_dork_queries_with_phone():
    queries = build_dork_queries(name="John Doe", phone="555-0100")
    assert any('"555-0100"' in q for q in queries)


def test_build_dork_queries_with_all():
    queries = build_dork_queries(
        name="John Doe",
        email="john@example.com",
        phone="555-0100",
        address="123 Main St",
    )
    assert len(queries) >= 5


def test_dork_result_risk_level():
    paste = DorkResult(
        query="test", url="https://pastebin.com/abc", title="Paste", snippet="data"
    )
    assert paste.risk_level == "high"

    generic = DorkResult(
        query="test", url="https://example.com/page", title="Page", snippet="mention"
    )
    assert generic.risk_level == "medium"

    pdf = DorkResult(
        query="test", url="https://example.com/file.pdf", title="Doc", snippet="name"
    )
    assert pdf.risk_level == "high"


def test_parse_search_results():
    raw_results = [
        {"url": "https://example.com/page1", "title": "Result 1", "snippet": "Found data"},
        {"url": "https://example.com/page2", "title": "Result 2", "snippet": "More data"},
    ]
    results = parse_search_results(raw_results, query='"John Doe"')
    assert len(results) == 2
    assert all(isinstance(r, DorkResult) for r in results)
    assert results[0].query == '"John Doe"'
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_google_dorker.py -v`
Expected: FAIL (module not found)

**Step 3: Implement Google dorker**

Create `digital_footprint/scanners/google_dorker.py`:

```python
"""Google dorking scanner for finding exposed personal data."""

from dataclasses import dataclass
from typing import Optional


HIGH_RISK_DOMAINS = {
    "pastebin.com", "paste.ee", "ghostbin.com", "hastebin.com",
    "doxbin.com", "doxbin.org",
}


@dataclass
class DorkResult:
    query: str
    url: str
    title: str
    snippet: str

    @property
    def risk_level(self) -> str:
        url_lower = self.url.lower()
        if any(domain in url_lower for domain in HIGH_RISK_DOMAINS):
            return "high"
        if url_lower.endswith(".pdf") or url_lower.endswith(".doc") or url_lower.endswith(".docx"):
            return "high"
        return "medium"


def build_dork_queries(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> list[str]:
    """Build Google dork queries for finding exposed personal data."""
    queries = []

    # Name-based queries
    queries.append(f'"{name}"')

    if email:
        queries.append(f'"{name}" "{email}"')
        queries.append(f'site:pastebin.com "{email}"')
        queries.append(f'"{email}"')

    if phone:
        queries.append(f'"{name}" "{phone}"')
        queries.append(f'"{phone}"')

    if address:
        queries.append(f'"{name}" "{address}"')

    # Document exposure
    queries.append(f'filetype:pdf "{name}"')
    queries.append(f'filetype:xls "{name}"')

    return queries


def parse_search_results(
    raw_results: list[dict], query: str
) -> list[DorkResult]:
    """Parse raw search results into DorkResult objects."""
    return [
        DorkResult(
            query=query,
            url=r["url"],
            title=r.get("title", ""),
            snippet=r.get("snippet", ""),
        )
        for r in raw_results
    ]
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_google_dorker.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add digital_footprint/scanners/google_dorker.py tests/test_google_dorker.py
git commit -m "feat: Google dorking scanner for data exposure detection"
```

---

### Task 5: Playwright Broker Scanner

**Files:**
- Create: `digital_footprint/scanners/playwright_scanner.py`
- Create: `digital_footprint/scanners/broker_scanner.py`
- Create: `tests/test_broker_scanner_playwright.py`

**Step 1: Write failing tests**

Create `tests/test_broker_scanner_playwright.py`:

```python
"""Tests for Playwright-based broker scanner."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from digital_footprint.scanners.broker_scanner import (
    BrokerScanResult,
    build_search_url,
    check_name_in_results,
)
from digital_footprint.scanners.playwright_scanner import (
    create_stealth_browser,
)


def test_build_search_url_simple():
    url = build_search_url(
        url_pattern="https://spokeo.com/search?q={first}+{last}",
        first_name="John",
        last_name="Doe",
    )
    assert url == "https://spokeo.com/search?q=John+Doe"


def test_build_search_url_with_location():
    url = build_search_url(
        url_pattern="https://whitepages.com/name/{first}-{last}/{state}",
        first_name="John",
        last_name="Doe",
        state="CA",
    )
    assert url == "https://whitepages.com/name/John-Doe/CA"


def test_build_search_url_missing_optional():
    url = build_search_url(
        url_pattern="https://example.com/search?name={first}+{last}&city={city}",
        first_name="John",
        last_name="Doe",
    )
    assert url == "https://example.com/search?name=John+Doe&city="


def test_check_name_in_results_found():
    page_text = "Results for John Doe in San Francisco, CA. Age 35. Related: Jane Doe."
    assert check_name_in_results(page_text, "John", "Doe") is True


def test_check_name_in_results_not_found():
    page_text = "No results found for your search."
    assert check_name_in_results(page_text, "John", "Doe") is False


def test_check_name_in_results_partial_match():
    page_text = "John Smith found in records."
    assert check_name_in_results(page_text, "John", "Doe") is False


def test_broker_scan_result_properties():
    found = BrokerScanResult(
        broker_slug="spokeo",
        broker_name="Spokeo",
        url="https://spokeo.com/John-Doe",
        found=True,
        page_text="John Doe, age 35",
    )
    assert found.found is True
    assert found.risk_level == "high"

    not_found = BrokerScanResult(
        broker_slug="spokeo",
        broker_name="Spokeo",
        url="https://spokeo.com/John-Doe",
        found=False,
    )
    assert not_found.risk_level == "low"
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_broker_scanner_playwright.py -v`
Expected: FAIL (module not found)

**Step 3: Implement Playwright base scanner**

Create `digital_footprint/scanners/playwright_scanner.py`:

```python
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
```

**Step 4: Implement broker scanner**

Create `digital_footprint/scanners/broker_scanner.py`:

```python
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

    @property
    def risk_level(self) -> str:
        return "high" if self.found else "low"


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
            await page.wait_for_load_state("networkidle", timeout=timeout)
            page_text = await page.inner_text("body")

            found = check_name_in_results(page_text, first_name, last_name)

            return BrokerScanResult(
                broker_slug=broker_slug,
                broker_name=broker_name,
                url=url,
                found=found,
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
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_broker_scanner_playwright.py -v`
Expected: 7 passed

**Step 6: Commit**

```bash
git add digital_footprint/scanners/playwright_scanner.py digital_footprint/scanners/broker_scanner.py tests/test_broker_scanner_playwright.py
git commit -m "feat: Playwright broker scanner with stealth browser support"
```

---

### Task 6: Exposure Report Generator

**Files:**
- Create: `digital_footprint/reporters/__init__.py`
- Create: `digital_footprint/reporters/exposure_report.py`
- Create: `tests/test_exposure_report.py`

**Step 1: Write failing tests**

Create `tests/test_exposure_report.py`:

```python
"""Tests for exposure report generator."""

import pytest

from digital_footprint.reporters.exposure_report import (
    compute_risk_score,
    risk_label,
    generate_exposure_report,
)


def test_compute_risk_score_empty():
    assert compute_risk_score([]) == 0


def test_compute_risk_score_single_critical():
    findings = [{"risk_level": "critical"}]
    assert compute_risk_score(findings) == 25


def test_compute_risk_score_mixed():
    findings = [
        {"risk_level": "critical"},
        {"risk_level": "high"},
        {"risk_level": "medium"},
        {"risk_level": "low"},
    ]
    assert compute_risk_score(findings) == 42  # 25 + 10 + 5 + 2


def test_compute_risk_score_capped_at_100():
    findings = [{"risk_level": "critical"}] * 10  # 250 uncapped
    assert compute_risk_score(findings) == 100


def test_risk_label_critical():
    assert risk_label(75) == "CRITICAL"
    assert risk_label(100) == "CRITICAL"


def test_risk_label_high():
    assert risk_label(50) == "HIGH"
    assert risk_label(74) == "HIGH"


def test_risk_label_moderate():
    assert risk_label(25) == "MODERATE"
    assert risk_label(49) == "MODERATE"


def test_risk_label_low():
    assert risk_label(0) == "LOW"
    assert risk_label(24) == "LOW"


def test_generate_exposure_report_empty():
    report = generate_exposure_report(
        person_name="John Doe",
        broker_results=[],
        breach_results={"hibp_breaches": [], "dehashed_records": [], "total": 0},
        username_results=[],
        dork_results=[],
    )
    assert "John Doe" in report
    assert "LOW" in report
    assert "Risk Score: 0/100" in report


def test_generate_exposure_report_with_findings():
    broker_results = [
        {"broker_name": "Spokeo", "found": True, "risk_level": "high", "url": "https://spokeo.com/john-doe"},
    ]
    breach_results = {
        "hibp_breaches": [
            {"name": "LinkedIn", "breach_date": "2012-05-05", "severity": "critical", "data_classes": ["Passwords"]},
        ],
        "dehashed_records": [],
        "total": 1,
    }
    username_results = [
        {"site_name": "GitHub", "url": "https://github.com/johndoe", "risk_level": "low"},
    ]

    report = generate_exposure_report(
        person_name="John Doe",
        broker_results=broker_results,
        breach_results=breach_results,
        username_results=username_results,
        dork_results=[],
    )
    assert "John Doe" in report
    assert "Spokeo" in report
    assert "LinkedIn" in report
    assert "GitHub" in report
    assert "Risk Score:" in report
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_exposure_report.py -v`
Expected: FAIL (module not found)

**Step 3: Implement exposure report generator**

Create `digital_footprint/reporters/__init__.py`:

```python
"""Report generators for Digital Footprint."""
```

Create `digital_footprint/reporters/exposure_report.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_exposure_report.py -v`
Expected: 10 passed

**Step 5: Commit**

```bash
git add digital_footprint/reporters/ tests/test_exposure_report.py
git commit -m "feat: exposure report generator with risk scoring"
```

---

### Task 7: Wire Up MCP Server Tools

**Files:**
- Create: `digital_footprint/tools/scan_tools.py`
- Modify: `server.py` (replace stubs with real implementations)
- Create: `tests/test_scan_tools.py`

**Step 1: Write failing tests**

Create `tests/test_scan_tools.py`:

```python
"""Tests for scan MCP tools."""

import json
from unittest.mock import patch, AsyncMock
import pytest

from digital_footprint.tools.scan_tools import (
    do_breach_check,
    do_exposure_report,
)


@pytest.mark.asyncio
async def test_do_breach_check_no_api_keys():
    result = await do_breach_check(email="test@example.com")
    parsed = json.loads(result)
    assert parsed["status"] == "no_api_keys"


@pytest.mark.asyncio
async def test_do_breach_check_with_hibp_key():
    mock_results = {
        "email": "test@example.com",
        "hibp_breaches": [],
        "hibp_count": 0,
        "dehashed_records": [],
        "dehashed_count": 0,
        "total": 0,
    }
    with patch("digital_footprint.tools.scan_tools.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        result = await do_breach_check(email="test@example.com", hibp_api_key="key")

    parsed = json.loads(result)
    assert parsed["total"] == 0


def test_do_exposure_report_minimal(tmp_db):
    tmp_db.insert_person(name="John Doe", emails=["john@example.com"])
    report = do_exposure_report(person_id=1, db=tmp_db)
    assert "John Doe" in report
    assert "Risk Score" in report
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_scan_tools.py -v`
Expected: FAIL (module not found)

**Step 3: Implement scan tools**

Create `digital_footprint/tools/scan_tools.py`:

```python
"""MCP scan tools for Digital Footprint."""

import json
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.reporters.exposure_report import generate_exposure_report


async def do_breach_check(
    email: str,
    hibp_api_key: Optional[str] = None,
    dehashed_api_key: Optional[str] = None,
) -> str:
    """Run breach check and return JSON results."""
    if not hibp_api_key and not dehashed_api_key:
        return json.dumps({
            "status": "no_api_keys",
            "message": "Set HIBP_API_KEY and/or DEHASHED_API_KEY in .env to enable breach checking.",
        })

    results = await scan_breaches(
        email=email,
        hibp_api_key=hibp_api_key,
        dehashed_api_key=dehashed_api_key,
    )

    # Serialize dataclass objects
    output = {
        "email": results["email"],
        "hibp_count": results["hibp_count"],
        "dehashed_count": results["dehashed_count"],
        "total": results["total"],
        "hibp_breaches": [
            {
                "name": b.name,
                "title": b.title,
                "breach_date": b.breach_date,
                "data_classes": b.data_classes,
                "severity": b.severity,
            }
            for b in results["hibp_breaches"]
        ],
        "dehashed_records": [
            {
                "database_name": r.database_name,
                "severity": r.severity,
            }
            for r in results["dehashed_records"]
        ],
    }

    return json.dumps(output, indent=2)


def do_exposure_report(
    person_id: int,
    db: Database,
    broker_results: Optional[list] = None,
    breach_results: Optional[dict] = None,
    username_results: Optional[list] = None,
    dork_results: Optional[list] = None,
) -> str:
    """Generate exposure report for a person."""
    person = db.get_person(person_id)
    if not person:
        return f"Person with id {person_id} not found."

    return generate_exposure_report(
        person_name=person.name,
        broker_results=broker_results or [],
        breach_results=breach_results or {"hibp_breaches": [], "dehashed_records": [], "total": 0},
        username_results=username_results or [],
        dork_results=dork_results or [],
    )
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_scan_tools.py -v`
Expected: 3 passed

**Step 5: Update server.py - replace stubs with real tools**

Modify `server.py` to:
1. Import scan tools
2. Replace the Phase 2 stubs with real implementations
3. Keep Phase 3+ stubs unchanged

Replace the stubs section in `server.py` starting from `# --- Stub tools for future phases ---`:

```python
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


# --- Stub tools for future phases ---

@mcp.tool()
def footprint_broker_remove(broker_slug: str, person_id: int = 1) -> str:
    """Submit a removal request to a specific data broker. [Phase 3 - Not yet implemented]"""
    return "Removal engine not yet implemented. Coming in Phase 3."

@mcp.tool()
def footprint_removal_status(person_id: int = None) -> str:
    """Get status of all pending removal requests. [Phase 3 - Not yet implemented]"""
    return "Removal tracking not yet implemented. Coming in Phase 3."

@mcp.tool()
def footprint_dark_web_monitor(email: str = None) -> str:
    """Monitor dark web sources for exposed personal data. [Phase 4 - Not yet implemented]"""
    return "Dark web monitoring not yet implemented. Coming in Phase 4."

@mcp.tool()
def footprint_social_audit(person_id: int = 1) -> str:
    """Audit social media privacy settings and exposure. [Phase 4 - Not yet implemented]"""
    return "Social media audit not yet implemented. Coming in Phase 4."
```

Also add `import json` to the top of server.py if not present.

**Step 6: Run all tests to verify nothing broke**

Run: `.venv/bin/python -m pytest -q`
Expected: All tests pass (33 old + new tests)

**Step 7: Commit**

```bash
git add digital_footprint/tools/scan_tools.py server.py tests/test_scan_tools.py
git commit -m "feat: wire up Phase 2 MCP tools (breach check, username search, dork, report)"
```

---

### Task 8: Add /exposure and /breach Skills

**Files:**
- Create: `.claude/skills/exposure.md`
- Create: `.claude/skills/breach.md`

**Step 1: Create /exposure skill**

Create `.claude/skills/exposure.md`:

```markdown
---
name: exposure
description: Run a comprehensive exposure scan and generate a privacy report
---

# /exposure - Digital Footprint Exposure Scan

Run a full exposure scan for a person and generate a comprehensive report.

## Usage

`/exposure` - Scan the default person (id=1)
`/exposure <name>` - Scan a specific person by name

## What it does

1. Looks up the person in the database
2. Checks data breaches via HIBP and DeHashed (if API keys configured)
3. Searches for usernames across 3,000+ sites via Maigret
4. Builds Google dork queries for manual investigation
5. Generates a risk-scored exposure report

## Steps

1. Call `footprint_list_persons` to find the person
2. Call `footprint_breach_check` with their primary email
3. Call `footprint_username_search` with their usernames
4. Call `footprint_google_dork` with their name
5. Call `footprint_exposure_report` to generate the final report
6. Present the report to the user with actionable next steps
```

**Step 2: Create /breach skill**

Create `.claude/skills/breach.md`:

```markdown
---
name: breach
description: Check if an email has been exposed in data breaches
---

# /breach - Data Breach Check

Check if an email address has been exposed in known data breaches.

## Usage

`/breach` - Check the default person's primary email
`/breach <email>` - Check a specific email address

## What it does

1. Queries Have I Been Pwned API for breach history
2. Queries DeHashed API for exposed credentials
3. Reports severity and recommended actions

## Steps

1. Call `footprint_breach_check` with the email
2. Present results grouped by severity
3. For critical breaches (passwords exposed): recommend immediate password change + 2FA
4. For high breaches (personal data): recommend monitoring
5. For medium breaches (email only): note for awareness

## API Keys Required

- `HIBP_API_KEY` - Get from https://haveibeenpwned.com/API/Key ($3.50/month)
- `DEHASHED_API_KEY` - Get from https://dehashed.com (optional, $5/month)
```

**Step 3: Commit**

```bash
git add .claude/skills/exposure.md .claude/skills/breach.md
git commit -m "feat: /exposure and /breach Claude Code skills"
```

---

### Task 9: Full Test Suite Verification

**Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: All tests pass (33 Phase 1 + new Phase 2 tests)

**Step 2: Verify test count**

Run: `.venv/bin/python -m pytest --co -q | tail -1`
Expected: At least 60 tests collected

**Step 3: Verify no import errors**

Run: `.venv/bin/python -c "from digital_footprint.scanners.breach_scanner import scan_breaches; from digital_footprint.scanners.username_scanner import search_username; from digital_footprint.scanners.google_dorker import build_dork_queries; from digital_footprint.scanners.broker_scanner import scan_broker; from digital_footprint.reporters.exposure_report import generate_exposure_report; print('All Phase 2 imports OK')"`
Expected: `All Phase 2 imports OK`

**Step 4: Verify MCP server starts**

Run: `.venv/bin/python -c "from server import mcp; print(f'Server ready: {mcp.name}')"`
Expected: `Server ready: digital-footprint`

**Step 5: Final commit if any cleanup needed**

```bash
git status
# If clean: done
# If changes: git add -A && git commit -m "chore: Phase 2 cleanup and verification"
```
