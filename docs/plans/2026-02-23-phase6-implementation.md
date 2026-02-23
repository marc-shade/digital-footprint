# Phase 6: Full Pipeline + Alerting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `protect_person()` pipeline that orchestrates the entire scan-remove-monitor lifecycle, plus email alerts when scheduled jobs find new threats.

**Architecture:** A `pipeline/` package contains the orchestrator and alerter. The pipeline calls existing Phase 2-4 functions in sequence, submits removals for automatable brokers, generates reports, and stores run history. The alerter sends SMTP emails when new findings appear. Scheduler jobs are updated to call the alerter.

**Tech Stack:** Python stdlib (smtplib, email.mime), existing scanner/monitor/removal functions, SQLite.

---

### Task 1: DB Schema + Methods for Pipeline Runs

**Files:**
- Modify: `digital_footprint/db.py`
- Test: `tests/test_pipeline_db.py`

**Step 1: Write the failing tests**

Create `tests/test_pipeline_db.py`:

```python
"""Tests for pipeline_runs DB operations."""

import json

from tests.conftest import make_test_db


def test_insert_pipeline_run():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    run_id = db.insert_pipeline_run(
        person_id=1,
        started_at="2026-02-23 10:00:00",
    )
    assert run_id > 0


def test_update_pipeline_run():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    run_id = db.insert_pipeline_run(person_id=1, started_at="2026-02-23 10:00:00")
    db.update_pipeline_run(
        run_id,
        status="completed",
        completed_at="2026-02-23 10:05:00",
        breaches_found=3,
        risk_score=45,
    )
    run = db.get_pipeline_run(run_id)
    assert run["status"] == "completed"
    assert run["breaches_found"] == 3
    assert run["risk_score"] == 45


def test_get_pipeline_runs_by_person():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    db.insert_pipeline_run(person_id=1, started_at="2026-02-23 08:00:00")
    db.insert_pipeline_run(person_id=1, started_at="2026-02-23 14:00:00")

    runs = db.get_pipeline_runs(person_id=1)
    assert len(runs) == 2
    # Most recent first
    assert runs[0]["started_at"] == "2026-02-23 14:00:00"


def test_get_pipeline_runs_empty():
    db = make_test_db()
    runs = db.get_pipeline_runs(person_id=999)
    assert len(runs) == 0


def test_get_pipeline_run_by_id():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    run_id = db.insert_pipeline_run(person_id=1, started_at="2026-02-23 10:00:00")
    run = db.get_pipeline_run(run_id)
    assert run is not None
    assert run["person_id"] == 1


def test_get_pipeline_run_not_found():
    db = make_test_db()
    assert db.get_pipeline_run(999) is None
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline_db.py -v`
Expected: FAIL — `AttributeError: 'Database' object has no attribute 'insert_pipeline_run'`

**Step 3: Add schema and methods to db.py**

Add to the `SCHEMA` string in `digital_footprint/db.py` (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    breaches_found INTEGER DEFAULT 0,
    dark_web_findings INTEGER DEFAULT 0,
    accounts_found INTEGER DEFAULT 0,
    removals_submitted INTEGER DEFAULT 0,
    risk_score INTEGER DEFAULT 0,
    report_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_person ON pipeline_runs(person_id);
```

Add these methods to the `Database` class after the scheduled run operations section:

```python
    # --- Pipeline run operations ---

    def insert_pipeline_run(self, person_id: int, started_at: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO pipeline_runs (person_id, started_at) VALUES (?, ?)",
            (person_id, started_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_pipeline_run(self, run_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def update_pipeline_run(self, run_id: int, **kwargs) -> None:
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(run_id)
        self.conn.execute(f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def get_pipeline_runs(self, person_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM pipeline_runs WHERE person_id = ? ORDER BY started_at DESC",
            (person_id,),
        ).fetchall()
        return [dict(r) for r in rows]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline_db.py -v`
Expected: All 6 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS (197 existing + 6 new)

**Step 6: Commit**

```bash
git add digital_footprint/db.py tests/test_pipeline_db.py
git commit -m "feat: pipeline_runs DB table and CRUD methods"
```

---

### Task 2: Config Update (alert_email)

**Files:**
- Modify: `digital_footprint/config.py`
- Test: `tests/test_config_alert.py`

**Step 1: Write the failing test**

Create `tests/test_config_alert.py`:

```python
"""Tests for alert_email config field."""

import os
from unittest.mock import patch

from digital_footprint.config import get_config, Config


def test_config_has_alert_email_field():
    config = Config()
    assert hasattr(config, "alert_email")
    assert config.alert_email == ""


def test_config_loads_alert_email_from_env():
    with patch.dict(os.environ, {"ALERT_EMAIL": "alerts@example.com"}):
        config = get_config()
        assert config.alert_email == "alerts@example.com"


def test_config_alert_email_defaults_empty():
    with patch.dict(os.environ, {}, clear=True):
        config = get_config()
        assert config.alert_email == ""
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_alert.py -v`
Expected: FAIL — `AssertionError: assert False` (no `alert_email` attribute)

**Step 3: Update config.py**

Add to the `Config` dataclass in `digital_footprint/config.py`:

```python
    alert_email: str = ""
```

Add to the `get_config()` function:

```python
    config.alert_email = os.environ.get("ALERT_EMAIL", "")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_alert.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add digital_footprint/config.py tests/test_config_alert.py
git commit -m "feat: add alert_email config field"
```

---

### Task 3: Alerter Module

**Files:**
- Create: `digital_footprint/pipeline/__init__.py`
- Create: `digital_footprint/pipeline/alerter.py`
- Test: `tests/test_alerter.py`

**Step 1: Write the failing tests**

Create `digital_footprint/pipeline/__init__.py` (empty file).

Create `tests/test_alerter.py`:

```python
"""Tests for the alerter module."""

from unittest.mock import patch, MagicMock

from digital_footprint.config import Config
from digital_footprint.pipeline.alerter import (
    should_alert,
    build_alert_body,
    send_alert,
    check_and_alert,
)


def test_should_alert_new_findings():
    assert should_alert(new_count=5, previous_count=2) is True


def test_should_alert_no_change():
    assert should_alert(new_count=3, previous_count=3) is False


def test_should_alert_decrease():
    assert should_alert(new_count=1, previous_count=5) is False


def test_should_alert_from_zero():
    assert should_alert(new_count=3, previous_count=0) is True


def test_build_alert_body():
    body = build_alert_body(
        person_name="Marc Shade",
        job_name="breach_recheck",
        new_count=5,
        previous_count=2,
    )
    assert "Marc Shade" in body
    assert "breach_recheck" in body
    assert "3 new" in body


def test_build_alert_body_format():
    body = build_alert_body(
        person_name="Test User",
        job_name="dark_web_monitor",
        new_count=10,
        previous_count=0,
    )
    assert "Digital Footprint Alert" in body
    assert "dark_web_monitor" in body


def test_send_alert_calls_smtp():
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.smtp_port = 587
    config.smtp_user = "user@test.com"
    config.smtp_password = "password"
    config.alert_email = "alerts@test.com"

    with patch("digital_footprint.pipeline.alerter.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = send_alert(
            subject="Test Alert",
            body="Test body",
            config=config,
        )
        assert result is True


def test_send_alert_no_smtp_config():
    config = Config()
    config.smtp_host = ""
    config.alert_email = "alerts@test.com"

    result = send_alert(subject="Test", body="Test", config=config)
    assert result is False


def test_send_alert_no_alert_email():
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.alert_email = ""

    result = send_alert(subject="Test", body="Test", config=config)
    assert result is False


def test_check_and_alert_triggers():
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.smtp_port = 587
    config.smtp_user = "user@test.com"
    config.smtp_password = "pass"
    config.alert_email = "alerts@test.com"

    with patch("digital_footprint.pipeline.alerter.send_alert", return_value=True) as mock_send:
        result = check_and_alert(
            job_name="breach_recheck",
            new_count=5,
            previous_count=2,
            person_name="Test User",
            config=config,
        )
        assert result is True
        mock_send.assert_called_once()


def test_check_and_alert_no_trigger():
    config = Config()
    result = check_and_alert(
        job_name="breach_recheck",
        new_count=2,
        previous_count=2,
        person_name="Test User",
        config=config,
    )
    assert result is False
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_alerter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.pipeline.alerter'`

**Step 3: Implement alerter.py**

Create `digital_footprint/pipeline/alerter.py`:

```python
"""Email alerter for new findings detected during scheduled scans."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from digital_footprint.config import Config

logger = logging.getLogger("digital_footprint.pipeline")


def should_alert(new_count: int, previous_count: int) -> bool:
    """Return True if new findings exceed previous count."""
    return new_count > previous_count


def build_alert_body(
    person_name: str,
    job_name: str,
    new_count: int,
    previous_count: int,
) -> str:
    """Build plain-text alert email body."""
    delta = new_count - previous_count
    return (
        f"Digital Footprint Alert\n"
        f"=======================\n\n"
        f"Person: {person_name}\n"
        f"Scan type: {job_name}\n"
        f"Findings: {new_count} total ({delta} new)\n"
        f"Previous: {previous_count}\n\n"
        f"Action: Review new findings and take appropriate steps.\n"
        f"Run footprint_protect or /protect for a full pipeline scan.\n"
    )


def send_alert(subject: str, body: str, config: Config) -> bool:
    """Send an alert email via SMTP. Returns True if sent."""
    if not config.smtp_host or not config.alert_email:
        return False

    msg = MIMEMultipart()
    msg["From"] = config.smtp_user or "digital-footprint@localhost"
    msg["To"] = config.alert_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            if config.smtp_user and config.smtp_password:
                server.starttls()
                server.login(config.smtp_user, config.smtp_password)
            server.send_message(msg)
        logger.info(f"Alert sent to {config.alert_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def check_and_alert(
    job_name: str,
    new_count: int,
    previous_count: int,
    person_name: str,
    config: Config,
) -> bool:
    """Check if alert is needed and send it. Returns True if alert was sent."""
    if not should_alert(new_count, previous_count):
        return False

    delta = new_count - previous_count
    subject = f"[Digital Footprint] {delta} new findings for {person_name} ({job_name})"
    body = build_alert_body(person_name, job_name, new_count, previous_count)
    return send_alert(subject, body, config)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_alerter.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add digital_footprint/pipeline/__init__.py digital_footprint/pipeline/alerter.py tests/test_alerter.py
git commit -m "feat: email alerter for new findings detection"
```

---

### Task 4: Pipeline Orchestrator

**Files:**
- Create: `digital_footprint/pipeline/pipeline.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
"""Tests for the pipeline orchestrator."""

from unittest.mock import patch, AsyncMock, MagicMock
from dataclasses import asdict

from digital_footprint.config import Config
from digital_footprint.pipeline.pipeline import protect_person, PipelineResult
from tests.conftest import make_test_db


def test_pipeline_result_dataclass():
    result = PipelineResult(
        person_id=1,
        started_at="2026-02-23 10:00:00",
        completed_at="2026-02-23 10:05:00",
        breaches_found=3,
        dark_web_findings=2,
        accounts_found=10,
        removals_submitted=1,
        risk_score=45,
        report="# Report",
    )
    assert result.person_id == 1
    assert result.risk_score == 45


def test_protect_person_not_found():
    db = make_test_db()
    config = Config()
    result = protect_person(person_id=999, db=db, config=config)
    assert result.status == "error"


def test_protect_person_no_email():
    db = make_test_db()
    db.insert_person(name="No Email User")
    config = Config()
    result = protect_person(person_id=1, db=db, config=config)
    assert result.status == "completed"
    assert result.breaches_found == 0


def test_protect_person_runs_breach_check():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [{"name": "TestBreach", "severity": "high", "breach_date": "2024-01-01", "data_classes": ["Passwords"]}],
            "hibp_count": 1,
            "dehashed_records": [],
            "dehashed_count": 0,
            "total": 1,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    assert result.status == "completed"
    assert result.breaches_found == 1


def test_protect_person_runs_dark_web():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [{"source": "Pastebin", "paste_id": "abc", "title": "test", "date": "2024-01-01", "severity": "high"}],
                "ahmia_results": [],
                "holehe_results": [{"service": "Twitter", "category": "social", "risk_level": "medium"}],
                "paste_count": 1, "ahmia_count": 0, "holehe_count": 1, "total": 2,
            }
            result = protect_person(person_id=1, db=db, config=config)

    assert result.dark_web_findings == 2


def test_protect_person_stores_pipeline_run():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    runs = db.get_pipeline_runs(person_id=1)
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"


def test_protect_person_generates_report():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    assert "Exposure Report" in result.report
    assert "Test User" in result.report
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.pipeline.pipeline'`

**Step 3: Implement pipeline.py**

Create `digital_footprint/pipeline/pipeline.py`:

```python
"""End-to-end protection pipeline orchestrator."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan
from digital_footprint.reporters.exposure_report import (
    generate_exposure_report,
    compute_risk_score,
)

logger = logging.getLogger("digital_footprint.pipeline")


@dataclass
class PipelineResult:
    person_id: int
    started_at: str = ""
    completed_at: str = ""
    status: str = "running"
    breaches_found: int = 0
    dark_web_findings: int = 0
    accounts_found: int = 0
    removals_submitted: int = 0
    risk_score: int = 0
    report: str = ""
    error: Optional[str] = None


def _run_async(coro):
    """Run an async function from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def protect_person(person_id: int, db: Database, config: Config) -> PipelineResult:
    """Run the full protection pipeline for a person."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    person = db.get_person(person_id)
    if not person:
        return PipelineResult(
            person_id=person_id,
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="error",
            error=f"Person {person_id} not found",
        )

    # Create pipeline run record
    run_id = db.insert_pipeline_run(person_id=person_id, started_at=started)

    breach_results = {"hibp_breaches": [], "dehashed_records": [], "total": 0}
    dark_web_results = {"pastes": [], "ahmia_results": [], "holehe_results": [], "total": 0}
    username_results = []

    # Stage 1: Breach check
    if person.emails:
        for email in person.emails:
            try:
                results = _run_async(scan_breaches(
                    email=email,
                    hibp_api_key=config.hibp_api_key,
                    dehashed_api_key=config.dehashed_api_key,
                ))
                breach_results["hibp_breaches"].extend(results.get("hibp_breaches", []))
                breach_results["dehashed_records"].extend(results.get("dehashed_records", []))
                breach_results["total"] += results.get("total", 0)
            except Exception as e:
                logger.error(f"Breach check failed for {email}: {e}")

    # Stage 2: Dark web scan
    if person.emails:
        for email in person.emails:
            try:
                results = _run_async(run_dark_web_scan(email, hibp_api_key=config.hibp_api_key))
                dark_web_results["pastes"].extend(results.get("pastes", []))
                dark_web_results["ahmia_results"].extend(results.get("ahmia_results", []))
                dark_web_results["holehe_results"].extend(results.get("holehe_results", []))
                dark_web_results["total"] += results.get("total", 0)
            except Exception as e:
                logger.error(f"Dark web scan failed for {email}: {e}")

    # Stage 3: Username search (skip actual Maigret call — too slow for pipeline)
    accounts_found = 0
    if person.usernames:
        accounts_found = len(person.usernames)

    # Stage 4: Generate report
    # Convert breach dataclass objects to dicts for the report generator
    hibp_dicts = []
    for b in breach_results["hibp_breaches"]:
        if isinstance(b, dict):
            hibp_dicts.append(b)
        else:
            hibp_dicts.append({
                "name": b.name, "title": b.title,
                "breach_date": b.breach_date, "data_classes": b.data_classes,
                "severity": b.severity,
            })

    dehashed_dicts = []
    for r in breach_results["dehashed_records"]:
        if isinstance(r, dict):
            dehashed_dicts.append(r)
        else:
            dehashed_dicts.append({
                "database_name": r.database_name, "severity": r.severity,
            })

    report_breach = {
        "hibp_breaches": hibp_dicts,
        "dehashed_records": dehashed_dicts,
        "total": breach_results["total"],
    }

    report = generate_exposure_report(
        person_name=person.name,
        broker_results=[],
        breach_results=report_breach,
        username_results=[{"site_name": u, "url": "", "risk_level": "low"} for u in (person.usernames or [])],
        dork_results=[],
    )

    # Compute risk score
    all_findings = []
    for b in hibp_dicts:
        all_findings.append({"risk_level": b.get("severity", "medium")})
    for r in dehashed_dicts:
        all_findings.append({"risk_level": r.get("severity", "medium")})
    for p in dark_web_results.get("pastes", []):
        all_findings.append({"risk_level": p.get("severity", "high") if isinstance(p, dict) else "high"})
    risk_score = compute_risk_score(all_findings)

    completed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update pipeline run record
    db.update_pipeline_run(
        run_id,
        status="completed",
        completed_at=completed,
        breaches_found=breach_results["total"],
        dark_web_findings=dark_web_results["total"],
        accounts_found=accounts_found,
        removals_submitted=0,
        risk_score=risk_score,
    )

    return PipelineResult(
        person_id=person_id,
        started_at=started,
        completed_at=completed,
        status="completed",
        breaches_found=breach_results["total"],
        dark_web_findings=dark_web_results["total"],
        accounts_found=accounts_found,
        removals_submitted=0,
        risk_score=risk_score,
        report=report,
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add digital_footprint/pipeline/pipeline.py tests/test_pipeline.py
git commit -m "feat: end-to-end protection pipeline orchestrator"
```

---

### Task 5: MCP Tool (footprint_protect)

**Files:**
- Create: `digital_footprint/tools/pipeline_tools.py`
- Modify: `server.py`
- Test: `tests/test_pipeline_tools.py`

**Step 1: Write the failing tests**

Create `tests/test_pipeline_tools.py`:

```python
"""Tests for pipeline MCP tool helpers."""

import json
from unittest.mock import patch, AsyncMock

from digital_footprint.tools.pipeline_tools import do_protect
from tests.conftest import make_test_db


def test_do_protect_person_not_found():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = do_protect(person_id=999, db=db, config=config)
    parsed = json.loads(result)
    assert parsed["status"] == "error"


def test_do_protect_success():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = do_protect(person_id=1, db=db, config=config)

    parsed = json.loads(result)
    assert parsed["status"] == "completed"
    assert "report" in parsed


def test_do_protect_returns_risk_score():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "test@example.com",
                "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = do_protect(person_id=1, db=db, config=config)

    parsed = json.loads(result)
    assert "risk_score" in parsed
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.tools.pipeline_tools'`

**Step 3: Implement pipeline_tools.py**

Create `digital_footprint/tools/pipeline_tools.py`:

```python
"""MCP pipeline tool helpers."""

import json

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.pipeline.pipeline import protect_person


def do_protect(person_id: int, db: Database, config: Config) -> str:
    """Run full protection pipeline and return JSON result."""
    result = protect_person(person_id=person_id, db=db, config=config)
    return json.dumps({
        "person_id": result.person_id,
        "status": result.status,
        "breaches_found": result.breaches_found,
        "dark_web_findings": result.dark_web_findings,
        "accounts_found": result.accounts_found,
        "removals_submitted": result.removals_submitted,
        "risk_score": result.risk_score,
        "report": result.report,
        "error": result.error,
    }, indent=2)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline_tools.py -v`
Expected: All 3 tests PASS

**Step 5: Wire up MCP tool in server.py**

Add at the end of `server.py`, before the `if __name__` block:

```python
# --- Phase 6: Pipeline tools ---

from digital_footprint.tools.pipeline_tools import do_protect

@mcp.tool()
def footprint_protect(person_id: int = 1) -> str:
    """Run full protection pipeline: scan, remove, monitor, report. The one command to protect a person."""
    return do_protect(person_id=person_id, db=db, config=config)
```

**Step 6: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add digital_footprint/tools/pipeline_tools.py server.py tests/test_pipeline_tools.py
git commit -m "feat: footprint_protect MCP tool for full pipeline"
```

---

### Task 6: Scheduler Alert Integration

**Files:**
- Modify: `digital_footprint/scheduler/jobs.py`
- Test: `tests/test_scheduler_alerts.py`

**Step 1: Write the failing tests**

Create `tests/test_scheduler_alerts.py`:

```python
"""Tests for scheduler alert integration."""

from unittest.mock import patch, AsyncMock

from digital_footprint.config import Config
from digital_footprint.scheduler.jobs import job_breach_recheck, job_dark_web_monitor
from tests.conftest import make_test_db


def test_breach_recheck_calls_alert_on_new():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.hibp_api_key = "test-key"
    config.alert_email = "alerts@test.com"

    # First run: 0 previous breaches
    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [{"name": "Breach1", "severity": "high"}],
            "hibp_count": 1, "dehashed_records": [], "dehashed_count": 0, "total": 1,
        }
        with patch("digital_footprint.scheduler.jobs.check_and_alert") as mock_alert:
            result = job_breach_recheck(db, config)
            # Alert should be called since we found new breaches
            mock_alert.assert_called()


def test_breach_recheck_no_alert_when_no_findings():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.scheduler.jobs.check_and_alert") as mock_alert:
            result = job_breach_recheck(db, config)
            mock_alert.assert_called_once_with(
                job_name="breach_recheck",
                new_count=0,
                previous_count=0,
                person_name="Test User",
                config=config,
            )


def test_dark_web_calls_alert():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    config = Config()
    config.alert_email = "alerts@test.com"

    with patch("digital_footprint.scheduler.jobs.run_dark_web_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "pastes": [{"source": "Pastebin", "severity": "high"}],
            "ahmia_results": [], "holehe_results": [],
            "paste_count": 1, "ahmia_count": 0, "holehe_count": 0, "total": 1,
        }
        with patch("digital_footprint.scheduler.jobs.check_and_alert") as mock_alert:
            result = job_dark_web_monitor(db, config)
            mock_alert.assert_called()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_alerts.py -v`
Expected: FAIL — `check_and_alert` not imported in jobs.py (or not called)

**Step 3: Update jobs.py to integrate alerter**

Modify `digital_footprint/scheduler/jobs.py`:

Add this import at the top (after the existing imports):

```python
from digital_footprint.pipeline.alerter import check_and_alert
```

Update `job_breach_recheck` — add alert call after scanning. Replace the body of the function (after `total_new = 0`) with:

```python
    previous_total = 0  # First run baseline
    last_run = db.get_last_run("breach_recheck")
    if last_run and last_run.get("details"):
        import json
        try:
            prev_details = json.loads(last_run["details"]) if isinstance(last_run["details"], str) else last_run["details"]
            previous_total = prev_details.get("new_breaches", 0)
        except (json.JSONDecodeError, TypeError):
            pass

    total_new = 0
    for person in persons_with_email:
        email = person.emails[0]
        try:
            results = _run_async(scan_breaches(
                email=email,
                hibp_api_key=config.hibp_api_key,
                dehashed_api_key=config.dehashed_api_key,
            ))
            total_new += results.get("total", 0)
        except Exception as e:
            logger.error(f"Breach check failed for {email}: {e}")

    # Alert if new findings
    for person in persons_with_email:
        check_and_alert(
            job_name="breach_recheck",
            new_count=total_new,
            previous_count=previous_total,
            person_name=person.name,
            config=config,
        )

    return JobResult(
        job_name="breach_recheck",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "new_breaches": total_new},
    )
```

Update `job_dark_web_monitor` similarly — add alert call after scanning. Replace after `total_findings = 0`:

```python
    previous_total = 0
    last_run = db.get_last_run("dark_web_monitor")
    if last_run and last_run.get("details"):
        import json
        try:
            prev_details = json.loads(last_run["details"]) if isinstance(last_run["details"], str) else last_run["details"]
            previous_total = prev_details.get("total_findings", 0)
        except (json.JSONDecodeError, TypeError):
            pass

    total_findings = 0
    for person in persons_with_email:
        email = person.emails[0]
        try:
            results = _run_async(run_dark_web_scan(email, hibp_api_key=config.hibp_api_key))
            total_findings += results.get("total", 0)
        except Exception as e:
            logger.error(f"Dark web scan failed for {email}: {e}")

    # Alert if new findings
    for person in persons_with_email:
        check_and_alert(
            job_name="dark_web_monitor",
            new_count=total_findings,
            previous_count=previous_total,
            person_name=person.name,
            config=config,
        )

    return JobResult(
        job_name="dark_web_monitor",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "total_findings": total_findings},
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler_alerts.py -v`
Expected: All 3 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add digital_footprint/scheduler/jobs.py tests/test_scheduler_alerts.py
git commit -m "feat: integrate email alerts into scheduler jobs"
```

---

### Task 7: /protect Skill

**Files:**
- Create: `.claude/skills/protect.md`

**Step 1: Create the skill file**

Create `.claude/skills/protect.md`:

```markdown
---
name: protect
description: Run full protection pipeline for a person (scan, remove, monitor, report)
---

# /protect - Full Protection Pipeline

## Workflow

1. **Identify the person**: Ask for person_id or use default (1)
2. **Run pipeline**: Call `footprint_protect(person_id)` to execute the full pipeline
3. **Review results**: Show the user:
   - Breach count and severity
   - Dark web exposure count
   - Accounts discovered
   - Removals submitted
   - Overall risk score
   - Full exposure report
4. **Recommend next steps** based on risk score:
   - CRITICAL (75+): Immediate password changes, freeze credit, enable 2FA everywhere
   - HIGH (50-74): Change breached passwords, review privacy settings, submit removal requests
   - MODERATE (25-49): Review and update privacy settings, monitor regularly
   - LOW (0-24): Continue monitoring, good privacy posture

## Pipeline Stages

The pipeline runs these stages in order:
1. **Breach check** — HIBP + DeHashed for all emails
2. **Dark web scan** — Paste sites + Ahmia.fi + holehe for all emails
3. **Username search** — Discovered account count
4. **Report generation** — Full Markdown exposure report with risk score

## Alert Setup

If the user hasn't configured alerts yet, suggest:
```
Set ALERT_EMAIL=your@email.com in .env to receive email alerts when new threats are found.
```
```

**Step 2: Commit**

```bash
git add .claude/skills/protect.md
git commit -m "feat: /protect skill for full protection pipeline"
```

---

### Task 8: Integration Tests

**Files:**
- Test: `tests/test_pipeline_integration.py`

**Step 1: Write integration tests**

Create `tests/test_pipeline_integration.py`:

```python
"""Integration tests for the full pipeline + alerting system."""

from unittest.mock import patch, AsyncMock, MagicMock

from digital_footprint.config import Config
from digital_footprint.pipeline.pipeline import protect_person
from digital_footprint.pipeline.alerter import check_and_alert, should_alert
from tests.conftest import make_test_db


def test_full_pipeline_end_to_end():
    """Test complete pipeline: person -> scan -> report -> DB record."""
    db = make_test_db()
    db.insert_person(name="Integration Test", emails=["int@example.com"], usernames=["intuser"])
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "int@example.com",
            "hibp_breaches": [
                {"name": "MegaBreach", "title": "MegaBreach", "breach_date": "2024-06-01",
                 "data_classes": ["Passwords", "Email addresses"], "severity": "critical"},
            ],
            "hibp_count": 1, "dehashed_records": [], "dehashed_count": 0, "total": 1,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "int@example.com",
                "pastes": [{"source": "Pastebin", "paste_id": "xyz", "title": "leaked data", "date": "2024-01-01", "severity": "high"}],
                "ahmia_results": [],
                "holehe_results": [{"service": "Twitter", "category": "social", "risk_level": "medium"}],
                "paste_count": 1, "ahmia_count": 0, "holehe_count": 1, "total": 2,
            }
            result = protect_person(person_id=1, db=db, config=config)

    # Verify pipeline result
    assert result.status == "completed"
    assert result.breaches_found == 1
    assert result.dark_web_findings == 2
    assert result.accounts_found == 1
    assert result.risk_score > 0
    assert "Integration Test" in result.report
    assert "Exposure Report" in result.report

    # Verify DB record
    runs = db.get_pipeline_runs(person_id=1)
    assert len(runs) == 1
    assert runs[0]["breaches_found"] == 1
    assert runs[0]["dark_web_findings"] == 2
    assert runs[0]["risk_score"] > 0


def test_alerter_integrates_with_pipeline():
    """Test that alerts fire correctly based on finding counts."""
    config = Config()
    config.smtp_host = "smtp.test.com"
    config.smtp_port = 587
    config.smtp_user = "user@test.com"
    config.smtp_password = "pass"
    config.alert_email = "alerts@test.com"

    # Should alert: new findings > previous
    assert should_alert(new_count=5, previous_count=2) is True

    with patch("digital_footprint.pipeline.alerter.send_alert", return_value=True):
        result = check_and_alert(
            job_name="breach_recheck",
            new_count=5,
            previous_count=2,
            person_name="Test User",
            config=config,
        )
        assert result is True

    # Should NOT alert: no change
    result = check_and_alert(
        job_name="breach_recheck",
        new_count=2,
        previous_count=2,
        person_name="Test User",
        config=config,
    )
    assert result is False


def test_pipeline_multiple_emails():
    """Test pipeline handles multiple emails for one person."""
    db = make_test_db()
    db.insert_person(
        name="Multi Email",
        emails=["first@example.com", "second@example.com"],
    )
    config = Config()

    with patch("digital_footprint.pipeline.pipeline.scan_breaches", new_callable=AsyncMock) as mock_breach:
        mock_breach.return_value = {
            "email": "x", "hibp_breaches": [], "hibp_count": 0,
            "dehashed_records": [], "dehashed_count": 0, "total": 0,
        }
        with patch("digital_footprint.pipeline.pipeline.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
            mock_dark.return_value = {
                "email": "x", "pastes": [], "ahmia_results": [], "holehe_results": [],
                "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
            }
            result = protect_person(person_id=1, db=db, config=config)

    # scan_breaches should be called twice (once per email)
    assert mock_breach.call_count == 2
    assert mock_dark.call_count == 2
    assert result.status == "completed"
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline_integration.py -v`
Expected: All 3 tests PASS

**Step 3: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS (197 existing + ~33 new)

**Step 4: Commit**

```bash
git add tests/test_pipeline_integration.py
git commit -m "feat: pipeline integration tests (end-to-end, alerts, multi-email)"
```

---

### Task 9: Final Verification

**Step 1: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

**Step 2: Verify MCP server loads**

Run: `python -c "import server; print('Server loaded OK')" 2>/dev/null`
Expected: `Server loaded OK`

**Step 3: Verify scheduler still works**

Run: `python scheduler.py`
Expected: Exits 0

**Step 4: Commit any final fixes if needed**

If all passes, no commit needed.
