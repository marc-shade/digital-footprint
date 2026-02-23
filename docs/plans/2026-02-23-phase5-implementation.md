# Phase 5: Scheduling + Reporting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add cron-based scheduling so breach checks, dark web monitoring, removal verification, and report generation run automatically on configurable intervals.

**Architecture:** A `scheduler/` package contains job definitions and a runner. A `scheduler.py` CLI entry point at the project root is the cron target. Jobs check the DB for what's overdue, execute it, and log results to a `scheduled_runs` table. One new MCP tool and one skill provide visibility.

**Tech Stack:** Python stdlib (logging, datetime, subprocess), existing scanner/monitor/removal functions from Phases 2-4, SQLite.

---

### Task 1: DB Schema + Methods for Scheduled Runs

**Files:**
- Modify: `digital_footprint/db.py`
- Test: `tests/test_scheduled_runs_db.py`

**Step 1: Write the failing tests**

Create `tests/test_scheduled_runs_db.py`:

```python
"""Tests for scheduled_runs DB operations."""

import json
from datetime import datetime

from digital_footprint.db import Database
from tests.conftest import make_test_db


def test_insert_scheduled_run():
    db = make_test_db()
    run_id = db.insert_scheduled_run(
        job_name="breach_recheck",
        started_at="2026-02-23 10:00:00",
    )
    assert run_id > 0


def test_update_scheduled_run():
    db = make_test_db()
    run_id = db.insert_scheduled_run(
        job_name="breach_recheck",
        started_at="2026-02-23 10:00:00",
    )
    db.update_scheduled_run(
        run_id,
        status="success",
        completed_at="2026-02-23 10:01:00",
        details=json.dumps({"breaches_checked": 5}),
    )
    run = db.get_scheduled_run(run_id)
    assert run["status"] == "success"
    assert run["completed_at"] == "2026-02-23 10:01:00"


def test_get_last_run():
    db = make_test_db()
    db.insert_scheduled_run(job_name="breach_recheck", started_at="2026-02-23 08:00:00")
    db.update_scheduled_run(1, status="success", completed_at="2026-02-23 08:01:00")
    db.insert_scheduled_run(job_name="breach_recheck", started_at="2026-02-23 14:00:00")
    db.update_scheduled_run(2, status="success", completed_at="2026-02-23 14:01:00")

    last = db.get_last_run("breach_recheck")
    assert last is not None
    assert last["started_at"] == "2026-02-23 14:00:00"


def test_get_last_run_no_history():
    db = make_test_db()
    assert db.get_last_run("nonexistent_job") is None


def test_get_run_history():
    db = make_test_db()
    for i in range(5):
        db.insert_scheduled_run(job_name="dark_web", started_at=f"2026-02-{20+i} 10:00:00")
        db.update_scheduled_run(i + 1, status="success", completed_at=f"2026-02-{20+i} 10:01:00")

    history = db.get_run_history(limit=3)
    assert len(history) == 3
    # Most recent first
    assert history[0]["started_at"] == "2026-02-24 10:00:00"


def test_get_run_history_default_limit():
    db = make_test_db()
    db.insert_scheduled_run(job_name="test", started_at="2026-02-23 10:00:00")
    history = db.get_run_history()
    assert len(history) == 1
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduled_runs_db.py -v`
Expected: FAIL — `AttributeError: 'Database' object has no attribute 'insert_scheduled_run'`

**Step 3: Add schema and methods to db.py**

Add to the `SCHEMA` string in `digital_footprint/db.py` (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS scheduled_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    details TEXT DEFAULT '{}',
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_scheduled_runs_job ON scheduled_runs(job_name);
```

Add these methods to the `Database` class after the existing removal operations section:

```python
    # --- Scheduled run operations ---

    def insert_scheduled_run(self, job_name: str, started_at: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO scheduled_runs (job_name, started_at) VALUES (?, ?)",
            (job_name, started_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_scheduled_run(self, run_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM scheduled_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def update_scheduled_run(self, run_id: int, **kwargs) -> None:
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(run_id)
        self.conn.execute(f"UPDATE scheduled_runs SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def get_last_run(self, job_name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM scheduled_runs WHERE job_name = ? ORDER BY started_at DESC LIMIT 1",
            (job_name,),
        ).fetchone()
        return dict(row) if row else None

    def get_run_history(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM scheduled_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduled_runs_db.py -v`
Expected: All 6 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: All 172+ tests PASS (166 existing + 6 new)

**Step 6: Commit**

```bash
git add digital_footprint/db.py tests/test_scheduled_runs_db.py
git commit -m "feat: scheduled_runs DB table and CRUD methods"
```

---

### Task 2: Job Definitions

**Files:**
- Create: `digital_footprint/scheduler/__init__.py`
- Create: `digital_footprint/scheduler/jobs.py`
- Test: `tests/test_scheduler_jobs.py`

**Step 1: Write the failing tests**

Create `digital_footprint/scheduler/__init__.py` (empty file).

Create `tests/test_scheduler_jobs.py`:

```python
"""Tests for scheduled job definitions."""

import json
from unittest.mock import patch, AsyncMock

from digital_footprint.scheduler.jobs import (
    JobResult,
    JOB_INTERVALS,
    job_breach_recheck,
    job_dark_web_monitor,
    job_verify_removals,
    job_generate_report,
)
from tests.conftest import make_test_db


def test_job_result_dataclass():
    result = JobResult(
        job_name="test",
        started_at="2026-02-23 10:00:00",
        completed_at="2026-02-23 10:01:00",
        status="success",
        details={"count": 5},
    )
    assert result.job_name == "test"
    assert result.status == "success"
    assert result.details["count"] == 5


def test_job_intervals_defined():
    assert "breach_recheck" in JOB_INTERVALS
    assert "dark_web_monitor" in JOB_INTERVALS
    assert "verify_removals" in JOB_INTERVALS
    assert "generate_report" in JOB_INTERVALS
    assert JOB_INTERVALS["breach_recheck"] == 7
    assert JOB_INTERVALS["dark_web_monitor"] == 3
    assert JOB_INTERVALS["verify_removals"] == 1
    assert JOB_INTERVALS["generate_report"] == 7


def test_job_breach_recheck_no_persons():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_breach_recheck(db, config)
    assert result.job_name == "breach_recheck"
    assert result.status == "success"
    assert result.details["persons_checked"] == 0


def test_job_breach_recheck_with_person():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()
    config.hibp_api_key = "test-key"

    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "hibp_breaches": [],
            "hibp_count": 0,
            "dehashed_records": [],
            "dehashed_count": 0,
            "total": 0,
        }
        result = job_breach_recheck(db, config)

    assert result.status == "success"
    assert result.details["persons_checked"] == 1


def test_job_dark_web_monitor_no_persons():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_dark_web_monitor(db, config)
    assert result.job_name == "dark_web_monitor"
    assert result.status == "success"
    assert result.details["persons_checked"] == 0


def test_job_dark_web_monitor_with_person():
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()

    with patch("digital_footprint.scheduler.jobs.run_dark_web_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "email": "test@example.com",
            "pastes": [], "ahmia_results": [], "holehe_results": [],
            "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0,
        }
        result = job_dark_web_monitor(db, config)

    assert result.status == "success"
    assert result.details["persons_checked"] == 1


def test_job_verify_removals_no_pending():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_verify_removals(db, config)
    assert result.job_name == "verify_removals"
    assert result.status == "skipped"


def test_job_generate_report_no_persons():
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()
    result = job_generate_report(db, config)
    assert result.job_name == "generate_report"
    assert result.status == "success"
    assert result.details["persons_reported"] == 0


def test_job_generate_report_with_person(tmp_path):
    db = make_test_db()
    db.insert_person(name="Test User", emails=["test@example.com"])
    from digital_footprint.config import Config
    config = Config()
    config.db_path = tmp_path / "test.db"

    result = job_generate_report(db, config)
    assert result.status == "success"
    assert result.details["persons_reported"] == 1
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.scheduler.jobs'`

**Step 3: Implement jobs.py**

Create `digital_footprint/scheduler/jobs.py`:

```python
"""Scheduled job definitions for Digital Footprint."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scanners.breach_scanner import scan_breaches
from digital_footprint.monitors.dark_web_monitor import run_dark_web_scan
from digital_footprint.reporters.exposure_report import generate_exposure_report

logger = logging.getLogger("digital_footprint.scheduler")

# Intervals in days
JOB_INTERVALS = {
    "breach_recheck": 7,
    "dark_web_monitor": 3,
    "verify_removals": 1,
    "generate_report": 7,
}


@dataclass
class JobResult:
    job_name: str
    started_at: str
    completed_at: str = ""
    status: str = "success"
    details: dict[str, Any] = field(default_factory=dict)
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


def job_breach_recheck(db: Database, config: Config) -> JobResult:
    """Re-check all persons for new breaches."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persons = db.list_persons()
    persons_with_email = [p for p in persons if p.emails]

    if not persons_with_email:
        return JobResult(
            job_name="breach_recheck",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="success",
            details={"persons_checked": 0, "new_breaches": 0},
        )

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

    return JobResult(
        job_name="breach_recheck",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "new_breaches": total_new},
    )


def job_dark_web_monitor(db: Database, config: Config) -> JobResult:
    """Re-run dark web monitoring for all persons."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persons = db.list_persons()
    persons_with_email = [p for p in persons if p.emails]

    if not persons_with_email:
        return JobResult(
            job_name="dark_web_monitor",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="success",
            details={"persons_checked": 0, "total_findings": 0},
        )

    total_findings = 0
    for person in persons_with_email:
        email = person.emails[0]
        try:
            results = _run_async(run_dark_web_scan(email, hibp_api_key=config.hibp_api_key))
            total_findings += results.get("total", 0)
        except Exception as e:
            logger.error(f"Dark web scan failed for {email}: {e}")

    return JobResult(
        job_name="dark_web_monitor",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_checked": len(persons_with_email), "total_findings": total_findings},
    )


def job_verify_removals(db: Database, config: Config) -> JobResult:
    """Verify pending removal requests."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pending = db.get_pending_verifications()

    if not pending:
        return JobResult(
            job_name="verify_removals",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="skipped",
            details={"pending_count": 0, "message": "No removals due for verification"},
        )

    verified = 0
    for removal in pending:
        db.update_removal(removal["id"], last_checked_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        verified += 1

    return JobResult(
        job_name="verify_removals",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"pending_count": len(pending), "verified": verified},
    )


def job_generate_report(db: Database, config: Config) -> JobResult:
    """Generate exposure reports for all persons."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persons = db.list_persons()

    if not persons:
        return JobResult(
            job_name="generate_report",
            started_at=started,
            completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="success",
            details={"persons_reported": 0},
        )

    reports_dir = config.db_path.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    for person in persons:
        report = generate_exposure_report(
            person_name=person.name,
            broker_results=[],
            breach_results={"hibp_breaches": [], "dehashed_records": [], "total": 0},
            username_results=[],
            dork_results=[],
        )
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = reports_dir / f"{date_str}-{person.name.lower().replace(' ', '-')}.md"
        report_path.write_text(report)
        logger.info(f"Report written to {report_path}")

    return JobResult(
        job_name="generate_report",
        started_at=started,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="success",
        details={"persons_reported": len(persons)},
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler_jobs.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add digital_footprint/scheduler/__init__.py digital_footprint/scheduler/jobs.py tests/test_scheduler_jobs.py
git commit -m "feat: scheduled job definitions (breach, dark web, verify, report)"
```

---

### Task 3: Runner (Overdue Detection + Execution)

**Files:**
- Create: `digital_footprint/scheduler/runner.py`
- Test: `tests/test_scheduler_runner.py`

**Step 1: Write the failing tests**

Create `tests/test_scheduler_runner.py`:

```python
"""Tests for scheduler runner."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from digital_footprint.scheduler.runner import (
    get_overdue_jobs,
    run_scheduled_jobs,
    get_schedule_status,
)
from digital_footprint.scheduler.jobs import JOB_INTERVALS
from tests.conftest import make_test_db


def test_get_overdue_jobs_no_history():
    """All jobs overdue when never run."""
    db = make_test_db()
    overdue = get_overdue_jobs(db)
    assert set(overdue) == set(JOB_INTERVALS.keys())


def test_get_overdue_jobs_recently_run():
    """Jobs not overdue when recently completed."""
    db = make_test_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for job_name in JOB_INTERVALS:
        run_id = db.insert_scheduled_run(job_name=job_name, started_at=now)
        db.update_scheduled_run(run_id, status="success", completed_at=now)

    overdue = get_overdue_jobs(db)
    assert len(overdue) == 0


def test_get_overdue_jobs_old_run():
    """Jobs overdue when last run is past interval."""
    db = make_test_db()
    old_time = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at=old_time)
    db.update_scheduled_run(run_id, status="success", completed_at=old_time)

    overdue = get_overdue_jobs(db)
    assert "breach_recheck" in overdue


def test_run_scheduled_jobs_records_results():
    """Runner stores results in DB."""
    db = make_test_db()
    from digital_footprint.config import Config
    config = Config()

    with patch("digital_footprint.scheduler.runner.JOB_FUNCTIONS") as mock_fns:
        mock_fns.__contains__ = lambda self, k: True
        mock_fns.__getitem__ = lambda self, k: lambda db, config: __import__(
            "digital_footprint.scheduler.jobs", fromlist=["JobResult"]
        ).JobResult(
            job_name=k,
            started_at="2026-02-23 10:00:00",
            completed_at="2026-02-23 10:01:00",
            status="success",
            details={"test": True},
        )
        mock_fns.keys = lambda self: ["breach_recheck"]

        results = run_scheduled_jobs(db, config)

    assert len(results) >= 1
    history = db.get_run_history(limit=10)
    assert len(history) >= 1


def test_get_schedule_status_empty():
    db = make_test_db()
    status = get_schedule_status(db)
    assert "jobs" in status
    assert len(status["jobs"]) == len(JOB_INTERVALS)
    for job in status["jobs"]:
        assert job["last_run"] is None
        assert job["status"] == "never_run"


def test_get_schedule_status_with_history():
    db = make_test_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at=now)
    db.update_scheduled_run(run_id, status="success", completed_at=now)

    status = get_schedule_status(db)
    breach_job = next(j for j in status["jobs"] if j["name"] == "breach_recheck")
    assert breach_job["last_run"] is not None
    assert breach_job["status"] == "success"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.scheduler.runner'`

**Step 3: Implement runner.py**

Create `digital_footprint/scheduler/runner.py`:

```python
"""Scheduler runner: determines overdue jobs and executes them."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.scheduler.jobs import (
    JOB_INTERVALS,
    JobResult,
    job_breach_recheck,
    job_dark_web_monitor,
    job_verify_removals,
    job_generate_report,
)

logger = logging.getLogger("digital_footprint.scheduler")

JOB_FUNCTIONS = {
    "breach_recheck": job_breach_recheck,
    "dark_web_monitor": job_dark_web_monitor,
    "verify_removals": job_verify_removals,
    "generate_report": job_generate_report,
}


def get_overdue_jobs(db: Database) -> list[str]:
    """Return list of job names that are overdue for execution."""
    overdue = []
    now = datetime.now()

    for job_name, interval_days in JOB_INTERVALS.items():
        last_run = db.get_last_run(job_name)
        if last_run is None:
            overdue.append(job_name)
            continue

        last_time = datetime.strptime(last_run["started_at"], "%Y-%m-%d %H:%M:%S")
        if now - last_time >= timedelta(days=interval_days):
            overdue.append(job_name)

    return overdue


def run_scheduled_jobs(db: Database, config: Config) -> list[JobResult]:
    """Run all overdue jobs and store results."""
    overdue = get_overdue_jobs(db)
    results = []

    for job_name in overdue:
        if job_name not in JOB_FUNCTIONS:
            continue

        logger.info(f"Running scheduled job: {job_name}")
        run_id = db.insert_scheduled_run(
            job_name=job_name,
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        try:
            result = JOB_FUNCTIONS[job_name](db, config)
            db.update_scheduled_run(
                run_id,
                status=result.status,
                completed_at=result.completed_at,
                details=json.dumps(result.details),
            )
            results.append(result)
            logger.info(f"Job {job_name} completed: {result.status}")
        except Exception as e:
            error_msg = str(e)
            db.update_scheduled_run(
                run_id,
                status="failed",
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error=error_msg,
            )
            results.append(JobResult(
                job_name=job_name,
                started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status="failed",
                error=error_msg,
            ))
            logger.error(f"Job {job_name} failed: {e}")

    return results


def get_schedule_status(db: Database) -> dict:
    """Get status of all scheduled jobs."""
    now = datetime.now()
    jobs = []

    for job_name, interval_days in JOB_INTERVALS.items():
        last_run = db.get_last_run(job_name)
        if last_run is None:
            jobs.append({
                "name": job_name,
                "interval_days": interval_days,
                "last_run": None,
                "next_due": "now",
                "status": "never_run",
            })
        else:
            last_time = datetime.strptime(last_run["started_at"], "%Y-%m-%d %H:%M:%S")
            next_due = last_time + timedelta(days=interval_days)
            is_overdue = now >= next_due
            jobs.append({
                "name": job_name,
                "interval_days": interval_days,
                "last_run": last_run["started_at"],
                "next_due": next_due.strftime("%Y-%m-%d %H:%M:%S"),
                "status": last_run.get("status", "unknown"),
                "overdue": is_overdue,
            })

    recent = db.get_run_history(limit=10)
    return {
        "jobs": jobs,
        "recent_runs": recent,
    }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler_runner.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add digital_footprint/scheduler/runner.py tests/test_scheduler_runner.py
git commit -m "feat: scheduler runner with overdue detection and job execution"
```

---

### Task 4: CLI Entry Point (scheduler.py)

**Files:**
- Create: `scheduler.py` (project root)
- Test: `tests/test_scheduler_cli.py`

**Step 1: Write the failing tests**

Create `tests/test_scheduler_cli.py`:

```python
"""Tests for scheduler CLI entry point."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_scheduler_script_exists():
    script = Path(__file__).parent.parent / "scheduler.py"
    assert script.exists(), "scheduler.py must exist at project root"


def test_scheduler_imports():
    """Verify scheduler.py can be imported without errors."""
    import importlib
    spec = importlib.util.spec_from_file_location(
        "scheduler_cli",
        str(Path(__file__).parent.parent / "scheduler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Don't execute, just verify it parses
    assert spec is not None


def test_scheduler_main_function():
    """Verify scheduler has a main() function."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "scheduler_cli",
        str(Path(__file__).parent.parent / "scheduler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"), "scheduler.py must have a main() function"


def test_scheduler_main_runs():
    """Test that main() executes without error (with test DB)."""
    import importlib.util
    import os

    os.environ["DIGITAL_FOOTPRINT_DB_PATH"] = ":memory:"
    spec = importlib.util.spec_from_file_location(
        "scheduler_cli",
        str(Path(__file__).parent.parent / "scheduler.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    with patch.dict(os.environ, {"DIGITAL_FOOTPRINT_DB_PATH": ":memory:"}):
        spec.loader.exec_module(mod)
        # Patch out actual job execution
        with patch("digital_footprint.scheduler.runner.run_scheduled_jobs") as mock_run:
            mock_run.return_value = []
            exit_code = mod.main()
            assert exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_cli.py -v`
Expected: FAIL — `AssertionError: scheduler.py must exist at project root`

**Step 3: Implement scheduler.py**

Create `scheduler.py` at the project root:

```python
#!/usr/bin/env python3
"""
Cron-friendly scheduler for Digital Footprint.

Checks for overdue jobs and runs them. Exits 0 on success, 1 on failure.

Usage:
    python scheduler.py

Cron example (every 6 hours):
    0 */6 * * * /path/to/venv/bin/python /path/to/scheduler.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from digital_footprint.config import get_config
from digital_footprint.db import Database
from digital_footprint.broker_registry import load_all_brokers
from digital_footprint.scheduler.runner import run_scheduled_jobs, get_overdue_jobs


def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure logging to file and stderr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "scheduler.log"

    logger = logging.getLogger("digital_footprint.scheduler")
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(str(log_path))
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    ))
    logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    return logger


def main() -> int:
    """Run overdue scheduled jobs. Returns 0 on success, 1 on failure."""
    config = get_config()
    db = Database(config)
    db.initialize()

    # Load brokers
    brokers = load_all_brokers(config.brokers_dir)
    for broker in brokers:
        db.insert_broker(broker)

    logger = setup_logging(config.db_path.parent)

    overdue = get_overdue_jobs(db)
    if not overdue:
        logger.info("No overdue jobs.")
        db.close()
        return 0

    logger.info(f"Overdue jobs: {', '.join(overdue)}")
    results = run_scheduled_jobs(db, config)

    failed = [r for r in results if r.status == "failed"]
    succeeded = [r for r in results if r.status in ("success", "skipped")]

    logger.info(f"Completed: {len(succeeded)} succeeded, {len(failed)} failed")
    for r in results:
        logger.info(json.dumps({
            "job": r.job_name,
            "status": r.status,
            "details": r.details,
        }))

    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler_cli.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add scheduler.py tests/test_scheduler_cli.py
git commit -m "feat: cron-friendly scheduler CLI entry point"
```

---

### Task 5: MCP Tool (footprint_schedule_status)

**Files:**
- Create: `digital_footprint/tools/schedule_tools.py`
- Modify: `server.py`
- Test: `tests/test_schedule_tools.py`

**Step 1: Write the failing tests**

Create `tests/test_schedule_tools.py`:

```python
"""Tests for schedule MCP tool helpers."""

import json

from digital_footprint.tools.schedule_tools import do_schedule_status
from tests.conftest import make_test_db


def test_do_schedule_status_empty():
    db = make_test_db()
    result = do_schedule_status(db)
    parsed = json.loads(result)
    assert "jobs" in parsed
    assert len(parsed["jobs"]) == 4
    for job in parsed["jobs"]:
        assert job["status"] == "never_run"


def test_do_schedule_status_with_history():
    db = make_test_db()
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at="2026-02-23 10:00:00")
    db.update_scheduled_run(run_id, status="success", completed_at="2026-02-23 10:01:00")

    result = do_schedule_status(db)
    parsed = json.loads(result)

    breach_job = next(j for j in parsed["jobs"] if j["name"] == "breach_recheck")
    assert breach_job["status"] == "success"
    assert breach_job["last_run"] is not None


def test_do_schedule_status_recent_runs():
    db = make_test_db()
    for i in range(3):
        run_id = db.insert_scheduled_run(job_name="dark_web_monitor", started_at=f"2026-02-{20+i} 10:00:00")
        db.update_scheduled_run(run_id, status="success", completed_at=f"2026-02-{20+i} 10:01:00")

    result = do_schedule_status(db)
    parsed = json.loads(result)
    assert len(parsed["recent_runs"]) == 3
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_schedule_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.tools.schedule_tools'`

**Step 3: Implement schedule_tools.py**

Create `digital_footprint/tools/schedule_tools.py`:

```python
"""MCP schedule tool helpers."""

import json

from digital_footprint.db import Database
from digital_footprint.scheduler.runner import get_schedule_status


def do_schedule_status(db: Database) -> str:
    """Get scheduler status as JSON."""
    status = get_schedule_status(db)
    return json.dumps(status, indent=2, default=str)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_schedule_tools.py -v`
Expected: All 3 tests PASS

**Step 5: Wire up the MCP tool in server.py**

Add at the end of `server.py`, before the `if __name__` block:

```python
# --- Phase 5: Scheduling tools ---

from digital_footprint.tools.schedule_tools import do_schedule_status

@mcp.tool()
def footprint_schedule_status() -> str:
    """View scheduler status: last run times, next due dates, and recent job history."""
    return do_schedule_status(db)
```

**Step 6: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add digital_footprint/tools/schedule_tools.py server.py tests/test_schedule_tools.py
git commit -m "feat: footprint_schedule_status MCP tool"
```

---

### Task 6: /schedule Skill

**Files:**
- Create: `.claude/skills/schedule.md`

**Step 1: Create the skill file**

Create `.claude/skills/schedule.md`:

```markdown
---
name: schedule
description: View and manage Digital Footprint scheduled jobs
---

# /schedule - Scheduling Management

## Workflow

1. **Check scheduler status**: Call `footprint_schedule_status()` to see all job statuses
2. **Review output**: Show the user which jobs are overdue, when they last ran, and recent history
3. **Offer actions**:
   - If jobs are overdue: suggest running the scheduler manually
   - If all jobs are current: show next due dates
   - Show cron setup instructions if not yet configured

## Cron Setup Instructions

Tell the user to add this to their crontab (`crontab -e`):

```
# Digital Footprint scheduler - runs every 6 hours
0 */6 * * * /path/to/venv/bin/python /path/to/digital-footprint/scheduler.py
```

Replace `/path/to/venv/bin/python` with the actual venv Python path and `/path/to/digital-footprint/scheduler.py` with the actual script path.

## Manual Run

To run all overdue jobs immediately:
```bash
/path/to/venv/bin/python /path/to/digital-footprint/scheduler.py
```

## Job Types

| Job | Interval | What It Does |
|-----|----------|-------------|
| breach_recheck | 7 days | Re-checks HIBP + DeHashed for all persons |
| dark_web_monitor | 3 days | Scans paste sites + Ahmia + holehe |
| verify_removals | 1 day | Verifies pending removal requests |
| generate_report | 7 days | Generates exposure reports to ~/.digital-footprint/reports/ |
```

**Step 2: Commit**

```bash
git add .claude/skills/schedule.md
git commit -m "feat: /schedule skill for scheduling management"
```

---

### Task 7: Integration Test

**Files:**
- Test: `tests/test_scheduler_integration.py`

**Step 1: Write integration test**

Create `tests/test_scheduler_integration.py`:

```python
"""Integration tests for the full scheduler pipeline."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from digital_footprint.config import Config
from digital_footprint.scheduler.jobs import JOB_INTERVALS
from digital_footprint.scheduler.runner import get_overdue_jobs, run_scheduled_jobs, get_schedule_status
from tests.conftest import make_test_db


def test_full_scheduler_cycle():
    """Test: no history -> all overdue -> run all -> none overdue."""
    db = make_test_db()
    config = Config()

    # 1. All jobs should be overdue initially
    overdue = get_overdue_jobs(db)
    assert len(overdue) == len(JOB_INTERVALS)

    # 2. Run all jobs (mock external calls)
    with patch("digital_footprint.scheduler.jobs.scan_breaches", new_callable=AsyncMock) as mock_breach, \
         patch("digital_footprint.scheduler.jobs.run_dark_web_scan", new_callable=AsyncMock) as mock_dark:
        mock_breach.return_value = {"email": "x", "hibp_breaches": [], "hibp_count": 0, "dehashed_records": [], "dehashed_count": 0, "total": 0}
        mock_dark.return_value = {"email": "x", "pastes": [], "ahmia_results": [], "holehe_results": [], "paste_count": 0, "ahmia_count": 0, "holehe_count": 0, "total": 0}
        results = run_scheduled_jobs(db, config)

    # 3. All jobs should have run
    assert len(results) == len(JOB_INTERVALS)
    for r in results:
        assert r.status in ("success", "skipped")

    # 4. No jobs should be overdue now
    overdue = get_overdue_jobs(db)
    assert len(overdue) == 0

    # 5. Status should show all jobs with last_run
    status = get_schedule_status(db)
    for job in status["jobs"]:
        assert job["last_run"] is not None


def test_scheduler_partial_failure():
    """Test that one job failing doesn't prevent others from running."""
    db = make_test_db()
    config = Config()

    def failing_job(db, config):
        raise RuntimeError("Simulated failure")

    with patch("digital_footprint.scheduler.runner.JOB_FUNCTIONS", {
        "breach_recheck": failing_job,
        "dark_web_monitor": lambda db, cfg: __import__(
            "digital_footprint.scheduler.jobs", fromlist=["JobResult"]
        ).JobResult(
            job_name="dark_web_monitor",
            started_at="2026-02-23 10:00:00",
            completed_at="2026-02-23 10:01:00",
            status="success",
            details={},
        ),
    }):
        with patch("digital_footprint.scheduler.runner.JOB_INTERVALS", {"breach_recheck": 7, "dark_web_monitor": 3}):
            results = run_scheduled_jobs(db, config)

    statuses = {r.job_name: r.status for r in results}
    assert statuses["breach_recheck"] == "failed"
    assert statuses["dark_web_monitor"] == "success"

    # Both should be recorded in DB
    history = db.get_run_history(limit=10)
    assert len(history) == 2


def test_scheduler_respects_intervals():
    """Test that jobs run on correct intervals."""
    db = make_test_db()

    # Simulate breach_recheck ran 2 days ago (interval = 7, should NOT be overdue)
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="breach_recheck", started_at=two_days_ago)
    db.update_scheduled_run(run_id, status="success", completed_at=two_days_ago)

    # Simulate dark_web_monitor ran 5 days ago (interval = 3, SHOULD be overdue)
    five_days_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    run_id = db.insert_scheduled_run(job_name="dark_web_monitor", started_at=five_days_ago)
    db.update_scheduled_run(run_id, status="success", completed_at=five_days_ago)

    overdue = get_overdue_jobs(db)
    assert "breach_recheck" not in overdue
    assert "dark_web_monitor" in overdue
    # verify_removals and generate_report have never run, so they're overdue
    assert "verify_removals" in overdue
    assert "generate_report" in overdue
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler_integration.py -v`
Expected: All 3 tests PASS

**Step 3: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS (166 existing + ~28 new)

**Step 4: Commit**

```bash
git add tests/test_scheduler_integration.py
git commit -m "feat: scheduler integration tests (full cycle, partial failure, intervals)"
```

---

### Task 8: Final Verification

**Step 1: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

**Step 2: Verify scheduler.py runs standalone**

Run: `python scheduler.py`
Expected: Exits with 0, logs "No overdue jobs" or runs jobs

**Step 3: Verify MCP server loads**

Run: `python -c "import server; print('Server loaded OK')" 2>/dev/null`
Expected: `Server loaded OK`

**Step 4: Commit any final fixes if needed**

If all passes, no commit needed.
