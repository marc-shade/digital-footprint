# Digital Footprint Manager

<p align="center">
  <img src="assets/bigfoot-hacker.png" alt="Bigfoot cleaning up your digital footprint on a 1980s computer" width="600">
</p>

Self-hosted personal data removal and privacy protection system. Replicates the capabilities of VanishID, DeleteMe, and Incogni through an MCP server, Claude Code skills, and automated pipelines.

## What It Does

- **Discovers** your exposure across 51 data brokers, breach databases, dark web paste sites, and 3,000+ username registries
- **Removes** your data via automated CCPA/GDPR opt-out emails, web form submissions, and guided manual processes
- **Monitors** for re-listing, new breaches, and dark web appearances on a recurring schedule
- **Alerts** you via email when new threats are detected
- **Reports** your risk score and full exposure in Markdown reports

## Architecture

```
digital_footprint/
  config.py              # Environment-based configuration
  db.py                  # SQLite database (WAL mode)
  models.py              # Person, Broker, Finding, Removal, Breach, Scan
  broker_registry.py     # YAML broker loader
  brokers/               # 51 data broker definitions (YAML)
  scanners/              # Breach, username, dark web, Google dork, Playwright
  removers/              # Email, web form, manual removal + verification
    templates/           # 5 Jinja2 legal templates (CCPA, GDPR)
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
pip install -r requirements.txt
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
```

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

This runs breach rechecks (weekly), dark web monitoring (every 3 days), removal verification (daily), and report generation (weekly).

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

51 broker definitions in YAML covering:

- **People search engines** (BeenVerified, Spokeo, WhitePages, Intelius, etc.)
- **Background check services** (TruthFinder, InstantCheckmate, etc.)
- **Marketing data brokers** (Acxiom, Oracle Data Cloud, Epsilon, etc.)
- **Social/genealogy** (Ancestry, Classmates, MyLife, etc.)

Each broker definition includes opt-out method, URL, difficulty rating, CCPA/GDPR compliance, and recheck interval.

## Legal Templates

Five Jinja2 templates for automated opt-out emails:

- `ccpa_deletion.j2` — California Consumer Privacy Act deletion request
- `ccpa_do_not_sell.j2` — CCPA Do Not Sell My Personal Information
- `gdpr_erasure.j2` — GDPR Right to Erasure (Article 17)
- `generic_removal.j2` — General data removal request
- `followup.j2` — Follow-up for unresponsive brokers

## Risk Scoring

Exposure reports include a 0-100 risk score based on weighted findings:

| Severity | Weight | Examples |
|----------|--------|----------|
| Critical | 25 | Passwords in breaches, SSN exposure |
| High | 10 | Email in dark web pastes, financial data |
| Medium | 5 | Name/address on people-search sites |
| Low | 2 | Username found on social platforms |

Scores map to labels: **CRITICAL** (75+), **HIGH** (50-74), **MODERATE** (25-49), **LOW** (0-24).

## Tests

```bash
python -m pytest tests/ -v
```

233 tests covering all modules. Zero external API calls in tests — all external services are mocked.

## External Services

| Service | Purpose | Cost |
|---------|---------|------|
| [Have I Been Pwned](https://haveibeenpwned.com/API/v3) | Breach and paste monitoring | $3.50/mo |
| [DeHashed](https://dehashed.com) | Enhanced breach data | $5/mo |
| [Maigret](https://github.com/soxoj/maigret) | Username search (3,000+ sites) | Free (local) |
| [Ahmia.fi](https://ahmia.fi) | Tor hidden service search | Free |
| [holehe](https://github.com/megadose/holehe) | Email registration check | Free (local) |

## License

MIT
