# Phase 5: Scheduling + Reporting Design

**Date**: 2026-02-23
**Status**: Approved
**Scope**: Cron-based scheduler, job definitions, run history, exposure report generation, `/schedule` skill

---

## What Phase 5 Builds

Phase 4 gave us dark web monitoring and social auditing. Phase 5 adds continuous scheduling: a cron-friendly script that checks what's overdue and runs breach re-checks, dark web monitoring, removal verification, and report generation automatically.

---

## Architecture

```
digital_footprint/scheduler/
  __init__.py
  runner.py           # Core job runner: checks overdue, executes jobs
  jobs.py             # Individual job functions
scheduler.py          # CLI entry point for cron (project root)
```

A single `scheduler.py` at the project root is the cron target. It imports the runner, which checks the DB for overdue tasks and executes them sequentially. Results are logged to `~/.digital-footprint/scheduler.log` and stored in a `scheduled_runs` table.

---

## Components

### 1. Job Definitions (`jobs.py`)

Four job types, each a standalone function:

**`job_breach_recheck(db, config)`**
- Re-runs breach check for all persons with emails
- Interval: every 7 days
- Compares results against existing breaches, flags new ones

**`job_dark_web_monitor(db, config)`**
- Re-runs dark web scan (HIBP pastes + Ahmia + holehe) for all persons with emails
- Interval: every 3 days

**`job_verify_removals(db, config)`**
- Calls verification for all persons with pending verifications (where `next_check_at <= now`)
- Interval: every 1 day (only runs if there are due verifications)

**`job_generate_report(db, config)`**
- Generates updated exposure report
- Writes to `~/.digital-footprint/reports/YYYY-MM-DD.md`
- Interval: every 7 days

Each returns a `JobResult` dataclass:
- `job_name`, `started_at`, `completed_at`, `status` (success/failed/skipped), `details` (dict with counts)

### 2. Runner (`runner.py`)

- `get_overdue_jobs(db) -> list[str]` — checks `scheduled_runs` table for what's overdue based on each job's interval
- `run_scheduled_jobs(db, config) -> list[JobResult]` — runs all overdue jobs, stores results
- `get_schedule_status(db) -> dict` — returns last run times, next due times, recent history

### 3. CLI Entry Point (`scheduler.py`)

Standalone script at project root. Initializes config and DB, runs overdue jobs, logs results. Exits 0 on success, 1 on failure.

Cron example: `0 */6 * * * /path/to/venv/python /path/to/scheduler.py`

### 4. Logging

Results written to `~/.digital-footprint/scheduler.log` using Python's `logging` module. One-line JSON per job run for easy parsing.

---

## DB Changes

New `scheduled_runs` table:

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

New DB methods:
- `insert_scheduled_run(job_name, started_at) -> int`
- `update_scheduled_run(run_id, **kwargs)`
- `get_last_run(job_name) -> Optional[dict]`
- `get_run_history(limit=20) -> list[dict]`

---

## MCP Tools

Add:
- `footprint_schedule_status()` — shows last run per job type, next due date, recent history

## Skills

- `/schedule` — interactive scheduling overview, manual job triggers, cron setup instructions

---

## Dependencies

None. Uses stdlib `logging`, `subprocess`, `datetime`. All scanning functions already exist from Phases 2-4.

---

## Verification Criteria

Phase 5 is complete when:
1. `jobs.py` defines all 4 job functions with correct intervals
2. `runner.py` determines overdue jobs and executes them
3. `scheduler.py` works as a standalone CLI script
4. `scheduled_runs` table stores job history correctly
5. `footprint_schedule_status` MCP tool works end-to-end
6. `/schedule` skill orchestrates the workflow
7. All new tests pass
8. Existing 166 tests still pass
