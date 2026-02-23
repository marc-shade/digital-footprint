# Agent Definitions

## Overview

Six specialized agents handle different aspects of the digital footprint protection system. All agents coordinate through `agent-runtime-mcp` task queues and store persistent knowledge in `enhanced-memory-mcp`.

---

## 1. Digital Footprint Orchestrator

**File**: `agents/digital-footprint-orchestrator.md`
**Type**: Orchestrator
**Schedule**: Daily (cron)

**Responsibilities**:
- Coordinate all sub-agents
- Manage scan schedules per person
- Detect overdue re-checks and spawn remover agents
- Trigger weekly/monthly report generation
- Escalate failed removals
- Maintain system health

**Decision Logic**:
```
FOR each protected person:
  IF scan_due(person):
    spawn broker-scanner(person)
    spawn breach-monitor(person)

  IF has_pending_removals(person):
    FOR each removal WHERE last_checked > recheck_days:
      spawn broker-scanner(person, broker)  # re-check
      IF re_listed:
        spawn broker-remover(person, broker)

  IF weekly_report_due(person):
    spawn exposure-reporter(person)
```

---

## 2. Broker Scanner

**File**: `agents/broker-scanner.md`
**Type**: Scanner / Researcher
**Trigger**: Orchestrator schedule or manual `/exposure` command

**Responsibilities**:
- Search data broker sites for a person's information
- Use Playwright with stealth mode for web scraping
- Take evidence screenshots
- Parse and extract discovered PII
- Risk-score each finding
- Store results in database
- Compare with previous scan to detect changes

**Tools Used**:
- `footprint_broker_check` (per broker)
- `footprint_username_search` (Maigret)
- `footprint_google_dork` (search exposure)
- Playwright (browser automation)

**Output**: Findings list with risk scores, stored in `findings` table

---

## 3. Broker Remover

**File**: `agents/broker-remover.md`
**Type**: Executor
**Trigger**: Orchestrator or manual `/vanish` command

**Responsibilities**:
- Execute removal requests per broker's configured method
- Handle web form automation (Playwright scripts)
- Send CCPA/GDPR email requests (SMTP)
- Monitor confirmation emails (IMAP)
- Click confirmation links
- Track removal status through lifecycle
- Escalate non-responsive brokers (follow-up template)
- Schedule re-checks

**Tools Used**:
- `footprint_broker_remove` (per broker)
- Playwright (form automation)
- SMTP (email sending)
- IMAP (confirmation monitoring)

**Output**: Removal records with status updates in `removals` table

---

## 4. Breach Monitor

**File**: `agents/breach-monitor.md`
**Type**: Monitor
**Trigger**: Orchestrator daily schedule

**Responsibilities**:
- Query breach databases for all protected persons' identifiers
- Detect new breaches since last check
- Score severity (plaintext passwords = critical, hashes = high, email only = medium)
- Generate immediate alerts for critical findings
- Track breach history over time
- Recommend credential rotation

**Tools Used**:
- `footprint_breach_check` (HIBP, DeHashed)
- `footprint_dark_web_monitor` (Breachsense)
- Slack/email notifications

**Output**: Breach findings in `breaches` table, alerts via notification channels

---

## 5. OSINT Recon

**File**: `agents/osint-recon.md`
**Type**: Researcher
**Trigger**: Manual `/exposure` command or orchestrator schedule

**Responsibilities**:
- Deep OSINT reconnaissance on a target person
- Username enumeration across 3,000+ sites (Maigret)
- Email-to-account mapping (holehe)
- Google dorking for PII exposure
- Social media profile discovery and privacy assessment
- Public records search
- Reverse image search (if photo provided)
- Compile comprehensive exposure map

**Tools Used**:
- `footprint_username_search` (Maigret)
- `footprint_google_dork` (custom queries)
- `footprint_social_audit` (social media)
- External OSINT tools (SpiderFoot, holehe)

**Output**: Comprehensive exposure report with risk-scored findings

---

## 6. Exposure Reporter

**File**: `agents/exposure-reporter.md`
**Type**: Reporter
**Trigger**: Post-scan or weekly schedule

**Responsibilities**:
- Aggregate findings from all sources (brokers, breaches, OSINT)
- Generate risk scores per finding and overall
- Produce formatted reports (Markdown, HTML, PDF)
- Track trends over time (improving/degrading)
- Compare current state vs. previous reports
- Highlight new threats and successful removals
- Deliver reports via configured channels

**Tools Used**:
- `footprint_exposure_report` (report generation)
- Database queries across all tables
- Jinja2 templates for formatting
- WeasyPrint for PDF generation

**Output**: Exposure report files + delivery to notification channels

---

## Agent Communication Pattern

```
Orchestrator
  │
  ├─→ [Task Queue] Scanner Agent
  │     └─→ [DB Write] findings
  │     └─→ [Notify] Orchestrator: "scan complete, N new findings"
  │
  ├─→ [Task Queue] Remover Agent
  │     └─→ [DB Write] removals
  │     └─→ [Notify] Orchestrator: "removal submitted/confirmed/failed"
  │
  ├─→ [Task Queue] Monitor Agent
  │     └─→ [DB Write] breaches
  │     └─→ [Notify] Orchestrator: "N new breaches detected"
  │     └─→ [Alert] User (if critical)
  │
  ├─→ [Task Queue] OSINT Recon Agent
  │     └─→ [DB Write] findings
  │     └─→ [Notify] Orchestrator: "recon complete"
  │
  └─→ [Task Queue] Reporter Agent
        └─→ [File Write] reports/
        └─→ [Notify] User: "weekly report ready"
```

## Agent Runtime Configuration

Each agent registers with `agent-runtime-mcp` for:
- Task creation and assignment
- Status reporting
- Scheduling (cron expressions)
- Dependency management (reporter waits for scanner completion)

## Failure Handling

| Failure | Agent | Recovery |
|---------|-------|----------|
| Broker site down | Scanner | Retry in 1 hour, max 3 attempts, then skip |
| CAPTCHA unsolvable | Remover | Flag for manual, notify user |
| API rate limit | Monitor | Exponential backoff, resume next cycle |
| Playwright crash | Scanner/Remover | Restart browser context, retry |
| Email delivery failure | Remover | Retry with alternate SMTP, then flag |
| Report generation fail | Reporter | Retry, fallback to Markdown-only |
