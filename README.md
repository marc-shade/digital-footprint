# Digital Footprint Manager

<p align="center">
  <img src="assets/bigfoot-hacker.png" alt="Bigfoot cleaning up your digital footprint on a 1980s computer" width="600">
</p>

Self-hosted personal data removal and privacy protection system. Replicates the capabilities of online footprint removal services through an MCP server, Claude Code skills, and automated pipelines.

## What It Does

- **Discovers** your exposure across 50 data brokers, breach databases, dark web paste sites, and 3,000+ username registries
- **Removes** your data via automated CCPA/GDPR opt-out emails, web form submissions, and guided manual processes
- **Monitors** for re-listing, new breaches, and dark web appearances on a recurring schedule
- **Escalates** brokers that ignore 2+ requests by drafting an FTC / state-AG complaint (you file it)
- **Alerts** you via email when new threats are detected
- **Reports** your risk score and full exposure in Markdown reports

> **Operational notes.** (1) Live opt-out submissions only fire when you opt
> in (`submit_removals=True`); the default pipeline is a dry run that records
> intended removals without contacting any broker. (2) Automated *discovery*
> and post-removal *verification* require a `search_url_pattern` per broker.
> 4 are live-verified today (radaris, thatsthem, zabasearch, addresses);
> the rest are unpopulated and skipped (logged, never reported as clean).
> (3) Many major people-search sites (Spokeo, FastPeopleSearch,
> TruePeopleSearch, USPhoneBook, ...) serve **anti-bot challenge pages** to
> the headless scanner, so they cannot be auto-discovered from a plain IP.
> The scanner now detects this and reports `blocked` (not a false all-clear);
> reaching those sites needs residential proxies + CAPTCHA solving, or a real
> logged-in browser (the Cowork approach). Blind opt-out submission does not
> need discovery at all.

## Architecture

```
digital_footprint/
  config.py              # Environment-based configuration
  db.py                  # SQLite database (WAL mode)
  models.py              # Person, Broker, Finding, Removal, Breach, Scan
  broker_registry.py     # YAML broker loader
  brokers/               # 50 data broker definitions (YAML)
  scanners/              # Breach, username, dark web, Google dork, Playwright
  removers/              # Email, web form, manual removal + verification + escalation
    templates/           # 6 Jinja2 legal templates (CCPA, GDPR, followup, complaint)
  monitors/              # Dark web monitoring orchestrator
  reporters/             # Exposure report generator with risk scoring
  scheduler/             # Cron-based job runner (breach, dark web, verify, report)
  pipeline/              # End-to-end protection orchestrator + email alerter
  tools/                 # MCP tool implementations
server.py                # FastMCP server entry point
scheduler.py             # Cron CLI entry point
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Claude Code](https://claude.ai/code) (for MCP integration and skills)

### Install

```bash
git clone https://github.com/marc-shade/digital-footprint.git
cd digital-footprint
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"      # runtime + test deps; drop [dev] for runtime only
playwright install chromium  # browser for broker scanning / form submission
```

This installs the `dfp` command:

```bash
dfp --help
dfp scan dorks "Your Name" --email you@example.com
dfp broker list
dfp report 1 --format pdf --output exposure.pdf   # markdown|json|html|pdf
```

### Configure

Create a `.env` file:

```bash
# Required for breach checking
HIBP_API_KEY=your_hibp_key              # haveibeenpwned.com ($3.50/mo)

# Optional: enhanced breach data
DEHASHED_API_KEY=your_dehashed_key      # dehashed.com ($5/mo)
DEHASHED_EMAIL=your_email

# Optional: automated email removals
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_app_password

# Optional: alert notifications
ALERT_EMAIL=alerts@yourdomain.com

# Optional: CAPTCHA solving for web form removals
CAPTCHA_API_KEY=your_2captcha_key

# Optional: encrypt PII at rest (off by default)
DIGITAL_FOOTPRINT_ENCRYPT=1
```

### Encryption at rest

Personal data (names, emails, phones, addresses, dates of birth, finding
URLs) can be encrypted at rest. It is **off by default** — the database is
plaintext and logs a warning on open. Turn it on with either:

- `DIGITAL_FOOTPRINT_ENCRYPT=1` — generates and loads a key file next to the
  DB (`db.key`, `chmod 600`). Keep that file safe; losing it makes the data
  unrecoverable.
- `DIGITAL_FOOTPRINT_DB_KEY=<fernet key>` — bring your own key
  (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).

When enabled, PII columns are Fernet-encrypted (AES-128-CBC + HMAC) and the DB
file shows no personal data to `strings`. This is field-level encryption:
schema, column names, timestamps and status values remain visible; breach rows
are pseudonymous (linked only by an integer id). To encrypt an existing
plaintext database, enable a key and call `Database.migrate_to_encrypted()`.

### Run the MCP Server

```bash
python -m digital_footprint
```

Or add to your Claude Code MCP config (`~/.claude.json`):

```json
{
  "mcpServers": {
    "digital-footprint": {
      "command": "python",
      "args": ["-m", "digital_footprint"],
      "cwd": "/path/to/digital-footprint"
    }
  }
}
```

### Schedule Recurring Scans

Add to your crontab (`crontab -e`):

```cron
0 3 * * * cd /path/to/digital-footprint && /path/to/venv/bin/python scheduler.py >> scheduler.log 2>&1
```

This runs breach rechecks (weekly), dark web monitoring (every 3 days), removal verification (daily), confirmation-inbox processing (daily), re-listing re-checks (weekly), and report generation (weekly). When a broker still lists you after a removal, the verify job resubmits the opt-out (once), then drafts an FTC / state-AG complaint if it is still ignored — set `DIGITAL_FOOTPRINT_AUTO_RESUBMIT=1` to have it re-send automatically, otherwise it records that a resubmit is due. When a broker you'd already cleared re-lists you, the re-listing re-check reopens a fresh removal automatically.

### Email confirmation loop

Many brokers email a "click to confirm your removal" link; without it the
opt-out never completes. Set `IMAP_HOST` / `IMAP_USER` / `IMAP_PASSWORD` (a
dedicated inbox) and the `process_confirmations` scheduler job polls it,
matches each message to a pending removal, and extracts the confirmation link.
With `DIGITAL_FOOTPRINT_AUTO_CONFIRM=1` it visits the link automatically;
otherwise it records the link on the removal for you to click. For safety, a
link is only ever visited if it is on the broker's own domain — a phishing
message in the inbox is never clicked.

## MCP Tools

| Tool | Description |
|------|-------------|
| `footprint_protect` | Run the full protection pipeline: scan, remove, monitor, report |
| `footprint_scan` | Full exposure scan for a person |
| `footprint_breach_check` | Check email against HIBP and DeHashed breach databases |
| `footprint_username_search` | Search username across 3,000+ sites via Maigret |
| `footprint_google_dork` | Generate Google dork queries for finding exposed data |
| `footprint_broker_check` | Check a specific data broker for a person's data |
| `footprint_exposure_report` | Generate a comprehensive exposure report |
| `footprint_broker_remove` | Submit a removal request to a data broker |
| `footprint_removal_status` | View status of pending removal requests |
| `footprint_verify_removals` | Re-scan brokers to verify removals completed |
| `footprint_dark_web_monitor` | Monitor dark web paste sites, Ahmia.fi, and holehe |
| `footprint_social_audit` | Audit social media privacy settings |
| `footprint_schedule_status` | View scheduler status and job history |

## Claude Code Skills

| Skill | Description |
|-------|-------------|
| `/protect` | Full protection pipeline workflow |
| `/exposure` | Run exposure scan and generate report |
| `/breach` | Check for credential exposure in breaches |
| `/removal` | Submit and track data broker removals |
| `/monitor` | Dark web and social media monitoring |
| `/schedule` | View and manage scheduled jobs |
| `/footprint` | Overview of all capabilities |

## Data Broker Registry

50 broker definitions in YAML covering:

- **People search engines** (BeenVerified, Spokeo, WhitePages, Intelius, etc.)
- **Background check services** (TruthFinder, InstantCheckmate, etc.)
- **Marketing data brokers** (Acxiom, Oracle Data Cloud, Epsilon, etc.)
- **Social/genealogy** (Ancestry, Classmates, MyLife, etc.)

Each broker definition includes opt-out method, URL, difficulty rating, CCPA/GDPR compliance, and recheck interval.

## Legal Templates

Six Jinja2 templates for automated opt-out emails and escalation:

- `ccpa_deletion.j2` — California Consumer Privacy Act deletion request
- `ccpa_do_not_sell.j2` — CCPA Do Not Sell My Personal Information
- `gdpr_erasure.j2` — GDPR Right to Erasure (Article 17)
- `generic_removal.j2` — General data removal request
- `followup.j2` — Follow-up (second request) for unresponsive brokers
- `regulatory_complaint.j2` — FTC / state-AG complaint draft, generated after a broker ignores 2+ requests

## Risk Scoring

Exposure reports include a 0-100 risk score based on weighted findings:

| Severity | Weight | Examples |
|----------|--------|----------|
| Critical | 25 | Passwords in breaches, SSN exposure |
| High | 10 | Email in dark web pastes, financial data |
| Medium | 5 | Name/address on people-search sites |
| Low | 2 | Username found on social platforms |

Scores map to labels: **CRITICAL** (75+), **HIGH** (50-74), **MODERATE** (25-49), **LOW** (0-24).

Reports render in **markdown, JSON, HTML, or PDF** (`dfp report <id> --format …`,
or the `footprint_exposure_report` MCP tool with a `format` argument). PDF uses
fpdf2 (pure-Python, no native dependencies).

## Tests

```bash
python -m pytest tests/ -v
```

339 tests covering all modules. Zero external API calls in tests — all external services are mocked. This includes an end-to-end MCP suite that drives the server's tools through the real FastMCP client.

## External Services

| Service | Purpose | Cost |
|---------|---------|------|
| [Have I Been Pwned](https://haveibeenpwned.com/API/v3) | Breach and paste monitoring | $3.50/mo |
| [DeHashed](https://dehashed.com) | Enhanced breach data | $5/mo |
| [Maigret](https://github.com/soxoj/maigret) | Username search (3,000+ sites) | Free (local) |
| [Ahmia.fi](https://ahmia.fi) | Tor hidden service search | Free |
| [holehe](https://github.com/megadose/holehe) | Email registration check | Free (local) |

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Marc Shade.

## Disclaimer

This is a self-hosted tool for exercising your own data-privacy rights (CCPA,
GDPR, and similar). Use it only against your own personal information, or on
behalf of someone who has authorized you. Automated access to third-party
sites may be subject to their terms of service; you are responsible for how
you operate it. Provided "as is," without warranty (see LICENSE).
