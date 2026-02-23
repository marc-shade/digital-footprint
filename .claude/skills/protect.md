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
1. **Breach check** -- HIBP + DeHashed for all emails
2. **Dark web scan** -- Paste sites + Ahmia.fi + holehe for all emails
3. **Username search** -- Discovered account count
4. **Report generation** -- Full Markdown exposure report with risk score

## Alert Setup

If the user hasn't configured alerts yet, suggest:
```
Set ALERT_EMAIL=your@email.com in .env to receive email alerts when new threats are found.
```
