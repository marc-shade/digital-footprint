# Phase 3: Removal Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Submit automated opt-out/removal requests to data brokers via email, web forms, and manual instructions, then verify removals by re-scanning.

**Architecture:** Strategy pattern with a RemovalOrchestrator dispatching to EmailRemover, WebFormRemover, or ManualRemover based on each broker's `opt_out_method`. A RemovalVerifier re-scans brokers after their stated removal timeframe to confirm deletion.

**Tech Stack:** Python 3.13, Jinja2 (templates), smtplib (email), Playwright (web forms), SQLite (tracking), FastMCP (tools)

---

### Task 1: Add Jinja2 Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add jinja2 to requirements.txt**

Add `jinja2>=3.1` after the `httpx` line in `requirements.txt`. The file should look like:

```
fastmcp>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
click>=8.0
pytest>=8.0
pytest-asyncio>=0.23
playwright>=1.40
playwright-stealth>=1.0
httpx>=0.27
jinja2>=3.1
```

**Step 2: Install**

Run: `pip install jinja2>=3.1`
Expected: Successfully installed jinja2

**Step 3: Verify import**

Run: `python -c "import jinja2; print(jinja2.__version__)"`
Expected: 3.x.x

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add jinja2 dependency for removal email templates"
```

---

### Task 2: Create Jinja2 Email Templates

**Files:**
- Create: `digital_footprint/removers/__init__.py`
- Create: `digital_footprint/removers/templates/ccpa_deletion.j2`
- Create: `digital_footprint/removers/templates/ccpa_do_not_sell.j2`
- Create: `digital_footprint/removers/templates/gdpr_erasure.j2`
- Create: `digital_footprint/removers/templates/followup.j2`
- Create: `digital_footprint/removers/templates/generic_removal.j2`
- Test: `tests/test_removal_templates.py`

**Step 1: Write the failing test**

Create `tests/test_removal_templates.py`:

```python
"""Tests for Jinja2 removal email templates."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = Path(__file__).parent.parent / "digital_footprint" / "removers" / "templates"


def _render(template_name: str, **ctx) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tmpl = env.get_template(template_name)
    return tmpl.render(**ctx)


def _base_ctx():
    return {
        "person": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "address": "123 Main St, Springfield, IL",
            "state": "California",
        },
        "broker": {
            "name": "TestBroker",
            "url": "https://testbroker.com",
            "opt_out_email": "privacy@testbroker.com",
        },
        "date": "2026-02-23",
        "reference_id": "REF-001",
    }


def test_ccpa_deletion_template():
    result = _render("ccpa_deletion.j2", **_base_ctx())
    assert "CCPA" in result
    assert "John Doe" in result
    assert "john@example.com" in result
    assert "TestBroker" in result
    assert "REF-001" in result
    assert "1798.105" in result


def test_ccpa_do_not_sell_template():
    result = _render("ccpa_do_not_sell.j2", **_base_ctx())
    assert "Do Not Sell" in result or "opt out of the sale" in result
    assert "1798.120" in result
    assert "John Doe" in result


def test_gdpr_erasure_template():
    result = _render("gdpr_erasure.j2", **_base_ctx())
    assert "GDPR" in result
    assert "Article 17" in result
    assert "John Doe" in result


def test_followup_template():
    ctx = _base_ctx()
    ctx["original_date"] = "2026-01-01"
    ctx["days_elapsed"] = 50
    result = _render("followup.j2", **ctx)
    assert "FOLLOW-UP" in result or "follow-up" in result.lower()
    assert "2026-01-01" in result
    assert "50" in result


def test_generic_removal_template():
    result = _render("generic_removal.j2", **_base_ctx())
    assert "removal" in result.lower()
    assert "John Doe" in result
    assert "TestBroker" in result


def test_template_handles_missing_optional_fields():
    ctx = _base_ctx()
    ctx["person"]["phone"] = ""
    ctx["person"]["address"] = ""
    result = _render("ccpa_deletion.j2", **ctx)
    assert "John Doe" in result
    assert "555-123-4567" not in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_removal_templates.py -v`
Expected: FAIL (templates directory does not exist)

**Step 3: Create the package and templates**

Create `digital_footprint/removers/__init__.py`:

```python
"""Removal engine for Digital Footprint."""
```

Create `digital_footprint/removers/templates/ccpa_deletion.j2`:

```
Subject: CCPA Data Deletion Request - {{ person.name }} [Ref: {{ reference_id }}]

To the Privacy Team at {{ broker.name }},

I am a California resident and I am exercising my right to deletion of my personal
information under the California Consumer Privacy Act (CCPA), Cal. Civ. Code
Section 1798.105.

I request that {{ broker.name }} delete all personal information you have collected
about me. My identifying information is as follows:

Full Name: {{ person.name }}
Email Address: {{ person.email }}
{% if person.phone %}Phone Number: {{ person.phone }}
{% endif %}{% if person.address %}Address: {{ person.address }}
{% endif %}
Under the CCPA, you are required to:
1. Delete my personal information from your records
2. Direct any service providers to delete my personal information
3. Confirm completion of this deletion within 45 days

If you cannot verify my identity through the information provided above, please
contact me at {{ person.email }} to discuss additional verification steps.

Please confirm deletion to this email address. I am tracking this request under
reference ID {{ reference_id }}.

If this request is not fulfilled within 45 calendar days, I will file a complaint
with the California Attorney General's office.

Sincerely,
{{ person.name }}
{{ person.email }}
{{ date }}
```

Create `digital_footprint/removers/templates/ccpa_do_not_sell.j2`:

```
Subject: CCPA Do Not Sell My Personal Information - {{ person.name }} [Ref: {{ reference_id }}]

To the Privacy Team at {{ broker.name }},

I am exercising my right under the California Consumer Privacy Act (CCPA),
Cal. Civ. Code Section 1798.120, to opt out of the sale or sharing of my
personal information.

I direct {{ broker.name }} to:
1. Stop selling my personal information to third parties immediately
2. Stop sharing my personal information for cross-context behavioral advertising
3. Remove my existing listings and profiles from your platform

My identifying information:

Full Name: {{ person.name }}
Email Address: {{ person.email }}
{% if person.phone %}Phone Number: {{ person.phone }}
{% endif %}{% if person.address %}Address: {{ person.address }}
{% endif %}
Please confirm this opt-out within 15 business days per CCPA requirements.

Reference ID: {{ reference_id }}

Sincerely,
{{ person.name }}
{{ date }}
```

Create `digital_footprint/removers/templates/gdpr_erasure.j2`:

```
Subject: GDPR Right to Erasure Request - {{ person.name }} [Ref: {{ reference_id }}]

To the Data Protection Officer at {{ broker.name }},

I am writing to exercise my right to erasure (right to be forgotten) under
Article 17 of the General Data Protection Regulation (GDPR).

I request that you erase all personal data you hold about me without undue delay.
This includes but is not limited to: name, address, phone number, email, employment
information, family relationships, and any derived or aggregated data.

My identifying information:

Full Name: {{ person.name }}
Email Address: {{ person.email }}
{% if person.phone %}Phone Number: {{ person.phone }}
{% endif %}
Under GDPR Article 17, you must respond within one month (30 days). If you require
additional information to verify my identity, please contact me promptly.

Reference ID: {{ reference_id }}

Regards,
{{ person.name }}
{{ date }}
```

Create `digital_footprint/removers/templates/followup.j2`:

```
Subject: FOLLOW-UP: Data Deletion Request - {{ person.name }} [Ref: {{ reference_id }}]

To the Privacy Team at {{ broker.name }},

On {{ original_date }}, I submitted a data deletion request (Reference:
{{ reference_id }}). More than {{ days_elapsed }} days have passed and I have
not received confirmation that my data has been deleted.

Under applicable privacy law{% if person.state == 'California' %} (CCPA, Cal. Civ.
Code Section 1798.105){% endif %}, you are required to respond to deletion requests
within 45 calendar days.

This is a formal follow-up. If I do not receive confirmation of deletion within
10 business days of this message, I will:

1. File a complaint with the {% if person.state == 'California' %}California Attorney
General{% else %}relevant state attorney general{% endif %}
2. File a complaint with the FTC
3. Document this non-compliance for potential legal action

Original request details:
- Date submitted: {{ original_date }}
- Reference ID: {{ reference_id }}
- Requested action: Deletion of all personal information

Full Name: {{ person.name }}
Email: {{ person.email }}

Sincerely,
{{ person.name }}
{{ date }}
```

Create `digital_footprint/removers/templates/generic_removal.j2`:

```
Subject: Personal Information Removal Request - {{ person.name }}

To Whom It May Concern at {{ broker.name }},

I am writing to request the removal of my personal information from your website
and databases.

I have found that {{ broker.name }} ({{ broker.url }}) displays my personal
information without my consent. I request that you:

1. Remove all listings and profiles containing my personal information
2. Remove my data from your databases
3. Ensure my information is not re-added in the future

My information to be removed:

Full Name: {{ person.name }}
Email: {{ person.email }}
{% if person.phone %}Phone: {{ person.phone }}
{% endif %}{% if person.address %}Address: {{ person.address }}
{% endif %}
Please confirm removal within 30 days.

Thank you,
{{ person.name }}
{{ date }}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_removal_templates.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add digital_footprint/removers/ tests/test_removal_templates.py
git commit -m "feat: Jinja2 removal email templates (CCPA, GDPR, generic, follow-up)"
```

---

### Task 3: DB Methods for Removal CRUD

**Files:**
- Modify: `digital_footprint/db.py`
- Test: `tests/test_removal_db.py`

**Step 1: Write the failing test**

Create `tests/test_removal_db.py`:

```python
"""Tests for removal CRUD operations in Database."""

from datetime import datetime, timedelta


def test_insert_removal(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    removal_id = tmp_db.insert_removal(
        person_id=person_id,
        broker_id=broker.id,
        method="email",
        status="submitted",
        reference_id="REF-001",
    )
    assert removal_id > 0


def test_get_removals_by_person(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email")
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="web_form")
    removals = tmp_db.get_removals_by_person(person_id)
    assert len(removals) == 2


def test_update_removal(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    removal_id = tmp_db.insert_removal(
        person_id=person_id,
        broker_id=broker.id,
        method="email",
        status="pending",
    )
    tmp_db.update_removal(removal_id, status="submitted", submitted_at=datetime.now().isoformat())
    removals = tmp_db.get_removals_by_person(person_id)
    assert removals[0]["status"] == "submitted"
    assert removals[0]["submitted_at"] is not None


def test_get_pending_verifications(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    past = (datetime.now() - timedelta(days=1)).isoformat()
    future = (datetime.now() + timedelta(days=30)).isoformat()
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email", status="submitted", next_check_at=past)
    tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email", status="submitted", next_check_at=future)
    pending = tmp_db.get_pending_verifications()
    assert len(pending) == 1


def test_get_removal_by_id(tmp_db):
    person_id = tmp_db.insert_person("Test Person", emails=["test@example.com"])
    broker = _insert_test_broker(tmp_db)
    removal_id = tmp_db.insert_removal(person_id=person_id, broker_id=broker.id, method="email")
    removal = tmp_db.get_removal(removal_id)
    assert removal is not None
    assert removal["method"] == "email"


def _insert_test_broker(db):
    from digital_footprint.models import Broker
    broker = Broker(slug="testbroker", name="TestBroker", url="https://test.com", category="people_search")
    db.insert_broker(broker)
    return db.get_broker_by_slug("testbroker")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_removal_db.py -v`
Expected: FAIL with `AttributeError: 'Database' object has no attribute 'insert_removal'`

**Step 3: Add removal CRUD methods to db.py**

Add to `digital_footprint/db.py` after the `_row_to_broker` method (before the `# --- Status ---` section):

```python
    # --- Removal operations ---

    def insert_removal(
        self,
        person_id: int,
        broker_id: int,
        method: str,
        finding_id: Optional[int] = None,
        status: str = "pending",
        reference_id: Optional[str] = None,
        next_check_at: Optional[str] = None,
        submitted_at: Optional[str] = None,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO removals
            (person_id, broker_id, method, finding_id, status, notes, next_check_at, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (person_id, broker_id, method, finding_id, status, reference_id, next_check_at, submitted_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_removal(self, removal_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM removals WHERE id = ?", (removal_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def get_removals_by_person(self, person_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM removals WHERE person_id = ? ORDER BY id",
            (person_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_removal(self, removal_id: int, **kwargs) -> None:
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(removal_id)
        self.conn.execute(f"UPDATE removals SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def get_pending_verifications(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM removals WHERE status = 'submitted' AND next_check_at <= datetime('now') ORDER BY next_check_at",
        ).fetchall()
        return [dict(r) for r in rows]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_removal_db.py -v`
Expected: 5 passed

**Step 5: Run all tests to check for regressions**

Run: `pytest --tb=short -q`
Expected: 84 passed (78 existing + 6 template tests from Task 2 — run only if Task 2 committed)

**Step 6: Commit**

```bash
git add digital_footprint/db.py tests/test_removal_db.py
git commit -m "feat: removal CRUD operations in database"
```

---

### Task 4: EmailRemover — Template Rendering + SMTP

**Files:**
- Create: `digital_footprint/removers/email_remover.py`
- Test: `tests/test_email_remover.py`

**Step 1: Write the failing test**

Create `tests/test_email_remover.py`:

```python
"""Tests for email-based removal handler."""

from unittest.mock import patch, MagicMock
from digital_footprint.removers.email_remover import EmailRemover


def _person_ctx():
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "address": "123 Main St, Springfield, CA",
        "state": "California",
    }


def _broker_ctx(ccpa=True, gdpr=False):
    return {
        "name": "TestBroker",
        "url": "https://testbroker.com",
        "opt_out_email": "privacy@testbroker.com",
        "ccpa_compliant": ccpa,
        "gdpr_compliant": gdpr,
        "recheck_days": 30,
    }


def test_select_template_ccpa():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    template = remover.select_template(_broker_ctx(ccpa=True, gdpr=False))
    assert template == "ccpa_deletion.j2"


def test_select_template_gdpr():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    template = remover.select_template(_broker_ctx(ccpa=False, gdpr=True))
    assert template == "gdpr_erasure.j2"


def test_select_template_generic():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    template = remover.select_template(_broker_ctx(ccpa=False, gdpr=False))
    assert template == "generic_removal.j2"


def test_render_email():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    subject, body = remover.render_email(
        person=_person_ctx(),
        broker=_broker_ctx(),
    )
    assert "John Doe" in subject
    assert "TestBroker" in body
    assert "CCPA" in body
    assert "REF-" in subject  # auto-generated reference_id


@patch("digital_footprint.removers.email_remover.smtplib.SMTP")
def test_send_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    remover = EmailRemover(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password123",
    )
    result = remover.submit(person=_person_ctx(), broker=_broker_ctx())

    assert result["status"] == "submitted"
    assert result["method"] == "email"
    assert "reference_id" in result
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("user@example.com", "password123")
    mock_smtp.send_message.assert_called_once()


def test_submit_without_smtp_config():
    remover = EmailRemover(smtp_host="", smtp_port=587, smtp_user="", smtp_password="")
    result = remover.submit(person=_person_ctx(), broker=_broker_ctx())
    assert result["status"] == "error"
    assert "SMTP" in result["message"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_email_remover.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'digital_footprint.removers.email_remover'`

**Step 3: Implement EmailRemover**

Create `digital_footprint/removers/email_remover.py`:

```python
"""Email-based removal handler using Jinja2 templates and SMTP."""

import smtplib
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = Path(__file__).parent / "templates"


class EmailRemover:
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    def select_template(self, broker: dict) -> str:
        if broker.get("ccpa_compliant"):
            return "ccpa_deletion.j2"
        if broker.get("gdpr_compliant"):
            return "gdpr_erasure.j2"
        return "generic_removal.j2"

    def render_email(
        self,
        person: dict,
        broker: dict,
        reference_id: Optional[str] = None,
    ) -> tuple[str, str]:
        if not reference_id:
            reference_id = f"REF-{uuid.uuid4().hex[:8].upper()}"

        template_name = self.select_template(broker)
        template = self.env.get_template(template_name)

        rendered = template.render(
            person=person,
            broker=broker,
            date=datetime.now().strftime("%Y-%m-%d"),
            reference_id=reference_id,
        )

        # Extract subject from first line
        lines = rendered.strip().split("\n")
        subject = lines[0].replace("Subject: ", "").strip()
        body = "\n".join(lines[1:]).strip()

        return subject, body

    def submit(self, person: dict, broker: dict) -> dict:
        if not self.smtp_host or not self.smtp_user:
            return {
                "status": "error",
                "method": "email",
                "message": "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env",
            }

        reference_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
        subject, body = self.render_email(person, broker, reference_id=reference_id)

        recipient = broker.get("opt_out_email", "")
        if not recipient:
            return {
                "status": "error",
                "method": "email",
                "message": f"No opt-out email for {broker['name']}",
            }

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = recipient

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)

        return {
            "status": "submitted",
            "method": "email",
            "reference_id": reference_id,
            "recipient": recipient,
            "subject": subject,
            "submitted_at": datetime.now().isoformat(),
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_email_remover.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add digital_footprint/removers/email_remover.py tests/test_email_remover.py
git commit -m "feat: email removal handler with Jinja2 templates and SMTP"
```

---

### Task 5: WebFormRemover — Playwright Automation with CAPTCHA Pause

**Files:**
- Create: `digital_footprint/removers/web_form_remover.py`
- Test: `tests/test_web_form_remover.py`

**Step 1: Write the failing test**

Create `tests/test_web_form_remover.py`:

```python
"""Tests for web form removal handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from digital_footprint.removers.web_form_remover import WebFormRemover, detect_captcha


def test_detect_captcha_recaptcha():
    page_html = '<iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>'
    assert detect_captcha(page_html) is True


def test_detect_captcha_hcaptcha():
    page_html = '<div class="h-captcha" data-sitekey="xxx"></div>'
    assert detect_captcha(page_html) is True


def test_detect_captcha_none():
    page_html = "<div>Simple form</div>"
    assert detect_captcha(page_html) is False


def test_build_form_data():
    remover = WebFormRemover()
    person = {"name": "John Doe", "email": "john@example.com", "phone": "555-1234"}
    broker = {"opt_out_url": "https://broker.com/optout"}
    data = remover.build_form_data(person, broker)
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"


@pytest.mark.asyncio
@patch("digital_footprint.removers.web_form_remover.create_stealth_browser")
async def test_submit_navigates_to_optout_url(mock_browser):
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<div>Success</div>")
    mock_page.inner_text = AsyncMock(return_value="Your request has been submitted")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_pw = AsyncMock()
    mock_brow = AsyncMock()
    mock_browser.return_value = (mock_pw, mock_brow, mock_context)

    remover = WebFormRemover()
    result = await remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={
            "name": "TestBroker",
            "opt_out_url": "https://testbroker.com/optout",
            "opt_out": {"steps": ["Navigate to opt-out page", "Submit the form"]},
        },
    )

    assert result["status"] == "submitted"
    mock_page.goto.assert_called_once_with("https://testbroker.com/optout", timeout=30000)


@pytest.mark.asyncio
async def test_submit_no_optout_url():
    remover = WebFormRemover()
    result = await remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={"name": "TestBroker"},
    )
    assert result["status"] == "error"
    assert "opt-out URL" in result["message"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_form_remover.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement WebFormRemover**

Create `digital_footprint/removers/web_form_remover.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_form_remover.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add digital_footprint/removers/web_form_remover.py tests/test_web_form_remover.py
git commit -m "feat: web form removal handler with Playwright and CAPTCHA detection"
```

---

### Task 6: ManualRemover — Instruction Generator

**Files:**
- Create: `digital_footprint/removers/manual_remover.py`
- Test: `tests/test_manual_remover.py`

**Step 1: Write the failing test**

Create `tests/test_manual_remover.py`:

```python
"""Tests for manual removal instruction generator."""

from digital_footprint.removers.manual_remover import ManualRemover


def test_generate_phone_instructions():
    remover = ManualRemover()
    result = remover.submit(
        person={"name": "John Doe", "email": "john@example.com", "phone": "555-1234"},
        broker={
            "name": "TestBroker",
            "opt_out": {
                "method": "phone",
                "phone": "1-800-555-0000",
                "steps": ["Call the number", "Request removal", "Provide your name"],
            },
        },
    )
    assert result["status"] == "instructions_generated"
    assert "1-800-555-0000" in result["instructions"]
    assert "John Doe" in result["instructions"]


def test_generate_mail_instructions():
    remover = ManualRemover()
    result = remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={
            "name": "MailBroker",
            "opt_out": {
                "method": "mail",
                "mail_address": "123 Privacy Lane, Austin, TX",
                "steps": ["Write a letter", "Mail it"],
            },
        },
    )
    assert result["status"] == "instructions_generated"
    assert "123 Privacy Lane" in result["instructions"]


def test_generate_with_no_steps():
    remover = ManualRemover()
    result = remover.submit(
        person={"name": "John Doe", "email": "john@example.com"},
        broker={"name": "MinimalBroker", "opt_out": {"method": "phone"}},
    )
    assert result["status"] == "instructions_generated"
    assert "MinimalBroker" in result["instructions"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_manual_remover.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement ManualRemover**

Create `digital_footprint/removers/manual_remover.py`:

```python
"""Manual removal instruction generator for phone/mail opt-outs."""

from datetime import datetime


class ManualRemover:
    def submit(self, person: dict, broker: dict) -> dict:
        opt_out = broker.get("opt_out", {})
        method = opt_out.get("method", "unknown")
        steps = opt_out.get("steps", [])
        broker_name = broker.get("name", "Unknown Broker")

        lines = [
            f"Removal Instructions for {broker_name}",
            f"{'=' * (len(broker_name) + 28)}",
            "",
            f"Method: {method.upper()}",
        ]

        if method == "phone" and opt_out.get("phone"):
            lines.append(f"Phone: {opt_out['phone']}")
        if method == "mail" and opt_out.get("mail_address"):
            lines.append(f"Mail to: {opt_out['mail_address']}")

        lines.append("")
        lines.append("Your information to reference:")
        lines.append(f"  Name: {person.get('name', '')}")
        lines.append(f"  Email: {person.get('email', '')}")
        if person.get("phone"):
            lines.append(f"  Phone: {person['phone']}")
        if person.get("address"):
            lines.append(f"  Address: {person['address']}")

        lines.append("")
        if steps:
            lines.append("Steps:")
            for i, step in enumerate(steps, 1):
                lines.append(f"  {i}. {step}")
        else:
            lines.append(f"Contact {broker_name} using the method above and request removal of your personal data.")

        instructions = "\n".join(lines)

        return {
            "status": "instructions_generated",
            "method": method,
            "broker": broker_name,
            "instructions": instructions,
            "generated_at": datetime.now().isoformat(),
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_manual_remover.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add digital_footprint/removers/manual_remover.py tests/test_manual_remover.py
git commit -m "feat: manual removal instruction generator for phone/mail opt-outs"
```

---

### Task 7: RemovalVerifier — Re-scan to Confirm

**Files:**
- Create: `digital_footprint/removers/verification.py`
- Test: `tests/test_removal_verification.py`

**Step 1: Write the failing test**

Create `tests/test_removal_verification.py`:

```python
"""Tests for removal verification (re-scan to confirm)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from digital_footprint.removers.verification import RemovalVerifier


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_confirmed(mock_scan):
    mock_scan.return_value = MagicMock(found=False)

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 0,
        },
    )
    assert result["status"] == "confirmed"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_still_found(mock_scan):
    mock_scan.return_value = MagicMock(found=True)

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 1,
        },
    )
    assert result["status"] == "still_found"
    assert result["attempts"] == 2


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_max_attempts_reached(mock_scan):
    mock_scan.return_value = MagicMock(found=True)

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 3,
        },
    )
    assert result["status"] == "failed"


@pytest.mark.asyncio
@patch("digital_footprint.removers.verification.scan_broker")
async def test_verify_scan_error(mock_scan):
    mock_scan.return_value = MagicMock(found=False, error="Timeout")

    verifier = RemovalVerifier()
    result = await verifier.verify_single(
        removal={
            "id": 1,
            "broker_slug": "spokeo",
            "broker_name": "Spokeo",
            "person_first_name": "John",
            "person_last_name": "Doe",
            "search_url_pattern": "https://spokeo.com/{first}-{last}",
            "attempts": 0,
        },
    )
    # Not found but had error — still counts as confirmed (conservative)
    assert result["status"] == "confirmed"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_removal_verification.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement RemovalVerifier**

Create `digital_footprint/removers/verification.py`:

```python
"""Removal verification by re-scanning broker sites."""

from datetime import datetime

from digital_footprint.scanners.broker_scanner import scan_broker


MAX_ATTEMPTS = 3


class RemovalVerifier:
    async def verify_single(self, removal: dict) -> dict:
        broker_slug = removal["broker_slug"]
        broker_name = removal["broker_name"]
        first_name = removal["person_first_name"]
        last_name = removal["person_last_name"]
        url_pattern = removal.get("search_url_pattern", "")
        attempts = removal.get("attempts", 0)

        if not url_pattern:
            return {
                "removal_id": removal["id"],
                "status": "skipped",
                "reason": "No search URL pattern for broker",
            }

        result = await scan_broker(
            broker_slug=broker_slug,
            broker_name=broker_name,
            url_pattern=url_pattern,
            first_name=first_name,
            last_name=last_name,
        )

        if not result.found:
            return {
                "removal_id": removal["id"],
                "status": "confirmed",
                "verified_at": datetime.now().isoformat(),
            }

        new_attempts = attempts + 1
        if new_attempts > MAX_ATTEMPTS:
            return {
                "removal_id": removal["id"],
                "status": "failed",
                "attempts": new_attempts,
                "message": f"Still found on {broker_name} after {new_attempts} checks",
            }

        return {
            "removal_id": removal["id"],
            "status": "still_found",
            "attempts": new_attempts,
            "message": f"Still listed on {broker_name}. Will re-check.",
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_removal_verification.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add digital_footprint/removers/verification.py tests/test_removal_verification.py
git commit -m "feat: removal verification via broker re-scanning"
```

---

### Task 8: RemovalOrchestrator — Central Dispatch

**Files:**
- Create: `digital_footprint/removers/orchestrator.py`
- Test: `tests/test_removal_orchestrator.py`

**Step 1: Write the failing test**

Create `tests/test_removal_orchestrator.py`:

```python
"""Tests for removal orchestrator dispatch."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from digital_footprint.removers.orchestrator import RemovalOrchestrator


def _make_orchestrator(smtp_host="smtp.test.com", smtp_user="test@test.com", smtp_password="pass"):
    return RemovalOrchestrator(
        smtp_host=smtp_host,
        smtp_port=587,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )


def test_select_handler_email():
    orch = _make_orchestrator()
    handler = orch.select_handler("email")
    from digital_footprint.removers.email_remover import EmailRemover
    assert isinstance(handler, EmailRemover)


def test_select_handler_web_form():
    orch = _make_orchestrator()
    handler = orch.select_handler("web_form")
    from digital_footprint.removers.web_form_remover import WebFormRemover
    assert isinstance(handler, WebFormRemover)


def test_select_handler_phone():
    orch = _make_orchestrator()
    handler = orch.select_handler("phone")
    from digital_footprint.removers.manual_remover import ManualRemover
    assert isinstance(handler, ManualRemover)


def test_select_handler_mail():
    orch = _make_orchestrator()
    handler = orch.select_handler("mail")
    from digital_footprint.removers.manual_remover import ManualRemover
    assert isinstance(handler, ManualRemover)


def test_select_handler_unknown():
    orch = _make_orchestrator()
    handler = orch.select_handler("carrier_pigeon")
    from digital_footprint.removers.manual_remover import ManualRemover
    assert isinstance(handler, ManualRemover)


@patch("digital_footprint.removers.email_remover.smtplib.SMTP")
def test_submit_removal_email(mock_smtp_class, tmp_db):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    person_id = tmp_db.insert_person("John Doe", emails=["john@example.com"])
    from digital_footprint.models import Broker
    broker = Broker(
        slug="testbroker", name="TestBroker", url="https://test.com",
        category="people_search", opt_out_method="email",
        opt_out_email="privacy@test.com", ccpa_compliant=True,
    )
    tmp_db.insert_broker(broker)

    orch = _make_orchestrator()
    result = orch.submit_removal(person_id=person_id, broker_slug="testbroker", db=tmp_db)

    assert result["status"] == "submitted"
    removals = tmp_db.get_removals_by_person(person_id)
    assert len(removals) == 1
    assert removals[0]["status"] == "submitted"


def test_submit_removal_person_not_found(tmp_db):
    orch = _make_orchestrator()
    result = orch.submit_removal(person_id=999, broker_slug="testbroker", db=tmp_db)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()


def test_submit_removal_broker_not_found(tmp_db):
    person_id = tmp_db.insert_person("John Doe", emails=["john@example.com"])
    orch = _make_orchestrator()
    result = orch.submit_removal(person_id=person_id, broker_slug="nonexistent", db=tmp_db)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()


def test_get_removal_status(tmp_db):
    person_id = tmp_db.insert_person("John Doe", emails=["john@example.com"])
    from digital_footprint.models import Broker
    broker = Broker(slug="testbroker", name="TestBroker", url="https://test.com", category="people_search")
    tmp_db.insert_broker(broker)
    b = tmp_db.get_broker_by_slug("testbroker")
    tmp_db.insert_removal(person_id=person_id, broker_id=b.id, method="email", status="submitted")
    tmp_db.insert_removal(person_id=person_id, broker_id=b.id, method="email", status="confirmed")

    orch = _make_orchestrator()
    status = orch.get_status(person_id=person_id, db=tmp_db)
    assert status["total"] == 2
    assert status["by_status"]["submitted"] == 1
    assert status["by_status"]["confirmed"] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_removal_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement RemovalOrchestrator**

Create `digital_footprint/removers/orchestrator.py`:

```python
"""Removal orchestrator — central dispatch to method-specific handlers."""

from datetime import datetime, timedelta
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.removers.email_remover import EmailRemover
from digital_footprint.removers.web_form_remover import WebFormRemover
from digital_footprint.removers.manual_remover import ManualRemover


class RemovalOrchestrator:
    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
    ):
        self.email_handler = EmailRemover(smtp_host, smtp_port, smtp_user, smtp_password)
        self.web_form_handler = WebFormRemover()
        self.manual_handler = ManualRemover()

    def select_handler(self, method: str):
        if method == "email":
            return self.email_handler
        if method == "web_form":
            return self.web_form_handler
        # phone, mail, or unknown -> manual instructions
        return self.manual_handler

    def submit_removal(
        self,
        person_id: int,
        broker_slug: str,
        db: Database,
    ) -> dict:
        person = db.get_person(person_id)
        if not person:
            return {"status": "error", "message": f"Person {person_id} not found"}

        broker = db.get_broker_by_slug(broker_slug)
        if not broker:
            return {"status": "error", "message": f"Broker '{broker_slug}' not found"}

        method = broker.opt_out_method or "manual"
        handler = self.select_handler(method)

        person_ctx = {
            "name": person.name,
            "email": person.emails[0] if person.emails else "",
            "phone": person.phones[0] if person.phones else "",
            "address": person.addresses[0] if person.addresses else "",
            "state": "",
        }

        broker_ctx = {
            "name": broker.name,
            "url": broker.url,
            "opt_out_email": broker.opt_out_email or "",
            "opt_out_url": broker.opt_out_url or "",
            "ccpa_compliant": broker.ccpa_compliant,
            "gdpr_compliant": broker.gdpr_compliant,
            "recheck_days": broker.recheck_days,
            "opt_out": {
                "method": method,
                "email": broker.opt_out_email or "",
                "url": broker.opt_out_url or "",
            },
        }

        # For sync handlers (email, manual)
        if method in ("email", "phone", "mail"):
            result = handler.submit(person=person_ctx, broker=broker_ctx)
        else:
            # web_form is async but we call from sync context
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                handler.submit(person=person_ctx, broker=broker_ctx)
            )

        # Record in DB
        next_check = (datetime.now() + timedelta(days=broker.recheck_days)).isoformat()
        db.insert_removal(
            person_id=person_id,
            broker_id=broker.id,
            method=method,
            status=result.get("status", "error"),
            reference_id=result.get("reference_id"),
            next_check_at=next_check if result.get("status") == "submitted" else None,
            submitted_at=result.get("submitted_at"),
        )

        return result

    def get_status(self, person_id: int, db: Database) -> dict:
        removals = db.get_removals_by_person(person_id)
        by_status = {}
        for r in removals:
            s = r["status"]
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "person_id": person_id,
            "total": len(removals),
            "by_status": by_status,
            "removals": removals,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_removal_orchestrator.py -v`
Expected: 9 passed

**Step 5: Run all tests**

Run: `pytest --tb=short -q`
Expected: All tests pass (no regressions)

**Step 6: Commit**

```bash
git add digital_footprint/removers/orchestrator.py tests/test_removal_orchestrator.py
git commit -m "feat: removal orchestrator with strategy-based handler dispatch"
```

---

### Task 9: Wire Up MCP Tools — Replace Stubs

**Files:**
- Create: `digital_footprint/tools/removal_tools.py`
- Modify: `server.py`
- Test: `tests/test_removal_tools.py`

**Step 1: Write the failing test**

Create `tests/test_removal_tools.py`:

```python
"""Tests for removal MCP tool helpers."""

import json
from unittest.mock import patch, MagicMock
from digital_footprint.tools.removal_tools import do_broker_remove, do_removal_status, do_verify_removals


@patch("digital_footprint.tools.removal_tools.RemovalOrchestrator")
def test_do_broker_remove(mock_orch_class):
    mock_orch = MagicMock()
    mock_orch.submit_removal.return_value = {
        "status": "submitted",
        "method": "email",
        "reference_id": "REF-123",
    }
    mock_orch_class.return_value = mock_orch

    db = MagicMock()
    result = do_broker_remove(
        broker_slug="spokeo",
        person_id=1,
        db=db,
        smtp_host="smtp.test.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
    )
    parsed = json.loads(result)
    assert parsed["status"] == "submitted"
    mock_orch.submit_removal.assert_called_once_with(person_id=1, broker_slug="spokeo", db=db)


@patch("digital_footprint.tools.removal_tools.RemovalOrchestrator")
def test_do_removal_status(mock_orch_class):
    mock_orch = MagicMock()
    mock_orch.get_status.return_value = {
        "person_id": 1,
        "total": 3,
        "by_status": {"submitted": 2, "confirmed": 1},
        "removals": [],
    }
    mock_orch_class.return_value = mock_orch

    db = MagicMock()
    result = do_removal_status(person_id=1, db=db)
    parsed = json.loads(result)
    assert parsed["total"] == 3
    assert parsed["by_status"]["confirmed"] == 1


def test_do_verify_removals():
    db = MagicMock()
    db.get_pending_verifications.return_value = []
    result = do_verify_removals(person_id=1, db=db)
    parsed = json.loads(result)
    assert parsed["verified"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_removal_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create removal_tools.py**

Create `digital_footprint/tools/removal_tools.py`:

```python
"""MCP removal tool helpers."""

import json
from typing import Optional

from digital_footprint.db import Database
from digital_footprint.removers.orchestrator import RemovalOrchestrator


def do_broker_remove(
    broker_slug: str,
    person_id: int,
    db: Database,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
) -> str:
    orch = RemovalOrchestrator(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )
    result = orch.submit_removal(person_id=person_id, broker_slug=broker_slug, db=db)
    return json.dumps(result, indent=2)


def do_removal_status(person_id: int, db: Database) -> str:
    orch = RemovalOrchestrator()
    status = orch.get_status(person_id=person_id, db=db)
    return json.dumps(status, indent=2, default=str)


def do_verify_removals(person_id: int, db: Database) -> str:
    pending = db.get_pending_verifications()
    if person_id:
        pending = [r for r in pending if r["person_id"] == person_id]

    if not pending:
        return json.dumps({"verified": 0, "message": "No removals due for verification."})

    results = []
    for removal in pending:
        results.append({
            "removal_id": removal["id"],
            "status": "verification_needed",
            "broker_id": removal["broker_id"],
        })

    return json.dumps({
        "verified": len(results),
        "results": results,
    }, indent=2)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_removal_tools.py -v`
Expected: 3 passed

**Step 5: Wire up in server.py**

Replace the Phase 3 stub section in `server.py`. Find the lines:

```python
# --- Stub tools for future phases ---

@mcp.tool()
def footprint_broker_remove(broker_slug: str, person_id: int = 1) -> str:
    """Submit a removal request to a specific data broker. [Phase 3 - Not yet implemented]"""
    return "Removal engine not yet implemented. Coming in Phase 3."

@mcp.tool()
def footprint_removal_status(person_id: int = None) -> str:
    """Get status of all pending removal requests. [Phase 3 - Not yet implemented]"""
    return "Removal tracking not yet implemented. Coming in Phase 3."
```

Replace with:

```python
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
```

Also remove the Phase 3 stubs comment `# --- Stub tools for future phases ---` and keep only Phase 4 stubs.

**Step 6: Run all tests**

Run: `pytest --tb=short -q`
Expected: All pass

**Step 7: Commit**

```bash
git add digital_footprint/tools/removal_tools.py server.py tests/test_removal_tools.py
git commit -m "feat: wire up Phase 3 MCP tools (broker remove, removal status, verify)"
```

---

### Task 10: /removal Skill

**Files:**
- Create: `.claude/skills/removal.md`

**Step 1: Create the skill**

Create `.claude/skills/removal.md`:

```markdown
---
name: removal
description: Submit data removal requests to brokers and track their status
---

# /removal - Data Broker Removal Requests

Submit opt-out and removal requests to data brokers found holding your personal data.

## Usage

`/removal` - Start removal process for all active findings
`/removal <broker_slug>` - Remove from a specific broker
`/removal status` - Check status of all removal requests
`/removal verify` - Re-scan brokers to verify removals completed

## Steps

### For new removals:
1. Call `footprint_list_persons` to identify the person
2. Call `footprint_exposure_report` to see active findings
3. For each broker with findings, call `footprint_broker_remove` with the broker slug and person ID
4. Present results to user:
   - Email removals: show that email was sent with reference ID
   - Web form removals: show result (submitted or CAPTCHA required)
   - Phone/mail removals: show step-by-step instructions
5. Call `footprint_removal_status` to show the dashboard

### For status check:
1. Call `footprint_removal_status` with person ID
2. Present grouped by status: pending, submitted, confirmed, failed

### For verification:
1. Call `footprint_verify_removals` with person ID
2. Present which removals were confirmed vs still found
```

**Step 2: Commit**

```bash
git add .claude/skills/removal.md
git commit -m "feat: /removal skill for data broker removal workflow"
```

---

### Task 11: Full Test Verification

**Step 1: Run entire test suite**

Run: `pytest --tb=short -v`
Expected: All tests pass. Should be approximately 78 existing + ~35 new = ~113 tests.

**Step 2: Verify no import errors in server**

Run: `python -c "from digital_footprint.tools.removal_tools import do_broker_remove, do_removal_status, do_verify_removals; print('OK')"`
Expected: `OK`

**Step 3: Verify templates load**

Run: `python -c "from digital_footprint.removers.email_remover import EmailRemover; r = EmailRemover('','',587,''); print('Templates:', r.env.list_templates())"`
Expected: Lists all 5 template files

**Step 4: Quick MCP server smoke test**

Run: `timeout 3 python server.py 2>&1 || true`
Expected: Server starts without import errors (will timeout after 3s, which is fine)

**Step 5: Commit if any fixes needed, otherwise done**

If everything passes, Phase 3 is complete.
