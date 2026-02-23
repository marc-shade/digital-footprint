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
