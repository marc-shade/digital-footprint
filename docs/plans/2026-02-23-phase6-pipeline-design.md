# Phase 6: Full Pipeline + Alerting Design

**Date**: 2026-02-23
**Status**: Approved
**Scope**: End-to-end protection pipeline, email alerts for new findings, pipeline run history, `/protect` skill

---

## What Phase 6 Builds

Phases 1-5 gave us individual capabilities: discovery, removal, monitoring, scheduling. Phase 6 ties them into a single "protect this person" pipeline that orchestrates the full lifecycle and alerts when new threats appear.

---

## Architecture

```
digital_footprint/pipeline/
  __init__.py
  pipeline.py         # protect_person() end-to-end orchestrator
  alerter.py          # Email alerts for new findings via SMTP
```

---

## Components

### 1. Pipeline Orchestrator (`pipeline.py`)

`protect_person(person_id, db, config) -> PipelineResult`

Runs the full lifecycle in sequence:
1. **Breach check** — `scan_breaches()` for each email
2. **Dark web scan** — `run_dark_web_scan()` for each email
3. **Username search** — `search_username()` for each username
4. **Auto-remove** — `RemovalOrchestrator.submit_removal()` for automatable brokers (email + web_form)
5. **Generate report** — `generate_exposure_report()` with all results

Returns `PipelineResult` dataclass:
- `person_id`, `started_at`, `completed_at`
- `breaches_found`, `dark_web_findings`, `accounts_found`
- `removals_submitted`, `risk_score`
- `report` (Markdown string)

Stores result in `pipeline_runs` DB table.

### 2. Alerter (`alerter.py`)

`check_and_alert(job_name, new_count, previous_count, person_name, config) -> bool`

- Compares new scan results against previous counts
- If new findings detected: sends alert email via SMTP
- Simple f-string email body (no Jinja2 needed)
- Returns True if alert was sent

`send_alert(subject, body, to_email, config)` — low-level SMTP send, reuses Phase 3 SMTP config.

**Scheduler integration:** Existing scheduler jobs call `check_and_alert()` after each scan when new findings exceed previous counts.

### 3. Config Change

New field: `alert_email` loaded from `ALERT_EMAIL` env var. The email address to receive alerts.

### 4. DB Changes

New `pipeline_runs` table:

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

New DB methods: `insert_pipeline_run()`, `get_pipeline_runs(person_id)`, `update_pipeline_run()`.

---

## MCP Tools

Add:
- `footprint_protect(person_id)` — runs full pipeline, returns summary

## Skills

- `/protect` — interactive full protection workflow

---

## Dependencies

None new. SMTP via stdlib, all scanner functions from Phases 2-4.

---

## Verification Criteria

Phase 6 is complete when:
1. `protect_person()` orchestrates all 5 stages end-to-end
2. `PipelineResult` contains accurate counts and risk score
3. `pipeline_runs` table stores history
4. Alerter sends email when new findings detected
5. Scheduler jobs integrate alert checking
6. `footprint_protect` MCP tool works
7. `/protect` skill orchestrates the workflow
8. All new tests pass
9. Existing 197 tests still pass
