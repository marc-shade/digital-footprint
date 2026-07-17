# Digital Footprint — CLAUDE.md

## Project Overview
Self-hosted personal data removal and privacy protection system. Replicates VanishID/DeleteMe/Incogni capabilities through MCP servers, Claude Code skills, and autonomous agents.

## Architecture
- **MCP Server**: `digital-footprint-mcp` (Python/FastMCP) — core tools for scanning, removal, monitoring
- **CLI**: `dfp` command (Python/Click) — quick access to all features
- **Skills**: `/footprint`, `/vanish`, `/exposure`, `/breach`, `/privacy-audit`
- **Agents**: orchestrator, broker-scanner, broker-remover, breach-monitor, osint-recon, exposure-reporter
- **Database**: SQLite at `~/.digital-footprint/footprint.db`
- **Broker Registry**: YAML files in `brokers/` directory

## Commands
```bash
python -m digital_footprint              # Run MCP server
python -m digital_footprint.cli scan     # CLI scan
python -m pytest tests/                  # Run tests
```

## Key Directories (actual layout)
```
digital_footprint/
  __init__.py            # `python -m digital_footprint` -> MCP server (server.py)
  cli.py                 # CLI entry (Click): python -m digital_footprint.cli
  db.py                  # SQLite manager (schema + all queries)
  models.py              # Person, Broker, Finding, Removal, Breach, Scan
  config.py              # env-based Config
  broker_registry.py     # YAML broker loader
  brokers/               # YAML broker registry files (50)
  scanners/              # broker/breach/username/dork/darkweb scanners
  removers/              # email/web_form/manual removal + verification + escalation
    templates/           # Jinja2 legal templates (CCPA/GDPR/followup/complaint)
  monitors/              # dark web monitoring orchestrator
  reporters/             # exposure report generator
  scheduler/             # cron job runner (breach/darkweb/verify/report)
  pipeline/              # end-to-end orchestrator + email alerter
  tools/                 # MCP tool implementations
server.py                # FastMCP server
scheduler.py             # cron CLI
.claude/skills/          # Claude Code skill definitions (7)
tests/                   # Test suite (262 tests)
```

## Conventions
- Python 3.11+, type hints throughout
- Playwright for browser automation (stealth mode)
- Rate limit all external requests
- YAML for broker definitions, Jinja2 for templates
- SQLite (WAL) for state, enhanced-memory-mcp for cross-session knowledge

## Known constraints (do not overstate in docs)
- **PII encryption at rest is available but OFF by default.** Enable with
  `DIGITAL_FOOTPRINT_ENCRYPT=1` (generates a chmod-600 key file next to the
  DB) or `DIGITAL_FOOTPRINT_DB_KEY=<fernet key>`. When on, PII columns
  (names, emails, phones, addresses, DOB, finding URLs/blobs) are Fernet-
  encrypted; the DB file shows no personal data to `strings`. When off, the
  DB is plaintext and logs a warning on open. Scope: field-level, not
  full-file — schema/column names/timestamps/status stay visible; breach
  rows are pseudonymous (person_id FK only). SQLCipher was rejected because
  its native lib does not pip-install cleanly here. Migrate an existing
  plaintext DB with `Database.migrate_to_encrypted()`.
- **Automated broker discovery/verification needs `search_url_pattern`** in
  each broker YAML. Most brokers do not have it yet, so the discovery scanner
  skips them (logged, not silent). Blind opt-out submission does not need it.
- Live broker removals only fire when the pipeline is called with
  `submit_removals=True`; the default is a dry run that records intended
  removals without contacting brokers. Likewise the verify job resubmits a
  still-listed removal (once, before escalating) only when
  `DIGITAL_FOOTPRINT_AUTO_RESUBMIT=1`; otherwise it records `resubmit_pending`.
  Resubmit re-dispatches via `RemovalOrchestrator.resubmit()` (no new removal
  row); escalation still wins once the attempt threshold is reached.
- **Re-listing re-removal** (scheduler job `recheck_confirmed`, weekly):
  re-scans confirmed removals due per the broker's `recheck_days`; on a
  re-listing it marks the old removal `re_listed`, records a `relisting`
  finding, and opens a fresh `pending` removal (not auto-submitted). A
  blocked/errored scan keeps the removal confirmed (never a false re-listing).
- **Email confirmation loop** (`removers/confirmation.py`, scheduler job
  `process_confirmations`): polls the IMAP inbox, matches "confirm your
  removal" emails to pending removals (by reference id / sender domain /
  person email), extracts the link, and — only when
  `DIGITAL_FOOTPRINT_AUTO_CONFIRM=1` — visits it. Security invariant: a link
  is visited only if it is on the broker's own registrable domain, so a
  phishing email in the inbox can't turn it into a click bot. The IMAP fetch
  layer (`ImapFetcher.fetch_recent`) is real imaplib but is NOT yet verified
  against a live mailbox; everything downstream of the fetch is tested.
