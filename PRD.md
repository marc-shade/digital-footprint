# Digital Footprint: Personal Data Removal & Privacy Protection System

## Product Requirements Document (PRD)

**Project**: Digital Footprint
**Owner**: Marc Shade / 2 Acre Studios
**Date**: 2026-02-23
**Status**: Planning

---

## 1. Executive Summary

Digital Footprint is a self-hosted, agentic privacy protection system that replicates and extends the capabilities of commercial services like VanishID ($5K-$50K+/year enterprise pricing). It automates personal data discovery, data broker opt-out/removal, dark web breach monitoring, social media exposure analysis, and ongoing surveillance — all operated through Claude Code skills, MCP servers, CLI tools, and autonomous agents.

**Why build this?** Commercial services charge $100-$50,000+/year, offer limited transparency, and require trusting a third party with your most sensitive personal information. Our solution runs locally, costs nothing beyond API fees for breach databases, and integrates directly into our existing agentic infrastructure.

---

## 2. Problem Statement

Personal data is exposed across 1,000+ data broker sites, dark web breach dumps, social media platforms, and public records. This data enables:

- **Social engineering attacks** — phishing, spear-phishing, pretexting
- **Identity theft** — credential stuffing, account takeover
- **Physical threats** — doxxing, stalking, swatting
- **Financial fraud** — synthetic identity creation

Manual opt-out takes 300+ hours for a single pass and must be repeated quarterly as brokers re-list data.

---

## 3. Competitive Landscape

| Service | Price/yr | Brokers | Dark Web | OSINT | Family | Self-Hosted |
|---------|----------|---------|----------|-------|--------|-------------|
| VanishID CEO | ~$50K+ | 1000+ | Yes | Quarterly OSINT hunts | 25 members | No |
| VanishID Exec | ~$10K+ | 1000+ | Yes | Annual OSINT hunt | 5 members | No |
| DeleteMe | $129 | 750+ | No | No | Add-on | No |
| Incogni | $90 | 180+ | No | No | No | No |
| Optery | $249 | 350+ | No | No | Add-on | No |
| **Digital Footprint** | **$0 (self-hosted)** | **1000+** | **Yes** | **Continuous** | **Unlimited** | **Yes** |

---

## 4. System Architecture

```
                    ┌──────────────────────────────────┐
                    │     Claude Code Skills Layer      │
                    │  /footprint  /vanish  /exposure   │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴───────────────────┐
                    │      Orchestrator Agent           │
                    │  (digital-footprint-agent)        │
                    └──┬──────┬──────┬──────┬─────────┘
                       │      │      │      │
              ┌────────┴┐ ┌───┴────┐ ┌┴─────┐ ┌┴────────────┐
              │ Scanner  │ │Remover │ │Monitor│ │ Reporter    │
              │ Agent    │ │ Agent  │ │ Agent │ │ Agent       │
              └────┬─────┘ └───┬────┘ └──┬───┘ └──┬──────────┘
                   │           │         │        │
    ┌──────────────┴───────────┴─────────┴────────┴──────────┐
    │                    MCP Server Layer                      │
    │  digital-footprint-mcp                                  │
    │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────┐  │
    │  │ Broker  │ │ Breach   │ │ OSINT   │ │ Removal     │  │
    │  │ Scanner │ │ Monitor  │ │ Recon   │ │ Engine      │  │
    │  └─────────┘ └──────────┘ └─────────┘ └─────────────┘  │
    └──────────────────────────┬──────────────────────────────┘
                               │
    ┌──────────────────────────┴──────────────────────────────┐
    │                   Data & Integration Layer               │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
    │  │ SQLite   │ │ HIBP API │ │ Sherlock │ │ Playwright │ │
    │  │ State DB │ │ Dehashed │ │ Maigret  │ │ Automation │ │
    │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
    │  │ CA DROP  │ │ SMTP     │ │ Enhanced │ │ Broker     │ │
    │  │ API      │ │ Engine   │ │ Memory   │ │ Registry   │ │
    │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
    └─────────────────────────────────────────────────────────┘
```

---

## 5. Core Capabilities

### 5.1 Data Broker Discovery & Removal

**Goal**: Continuously find and remove personal data from 1,000+ data broker sites.

**Broker Categories**:
- People search sites (BeenVerified, Spokeo, WhitePages, Radaris, Intelius, TruePeopleSearch, etc.)
- Public records aggregators (Acxiom, LexisNexis, CoreLogic)
- Marketing data brokers (Oracle Data Cloud, Epsilon, Equifax Marketing)
- Background check services (Checkr, GoodHire, Sterling)
- Reverse lookup services (AnyWho, USPhoneBook, FastPeopleSearch)
- Property/real estate data (Zillow, Redfin, county assessors)
- Social media aggregators (Social Catfish, PimEyes, FaceCheck.id)

**Removal Methods** (per-broker, stored in registry):
1. **Web form submission** — Playwright-automated form fills with CAPTCHA solving
2. **Email opt-out** — Templated CCPA/GDPR deletion requests via SMTP
3. **API-based** — Direct API calls where available (CA DROP portal Aug 2026)
4. **Phone verification** — Flag for manual action with instructions
5. **Mail/fax** — Generate PDF letters for physical mailing

**Process**:
1. Scan broker sites for target person's data (name, address, phone, email)
2. Record findings with screenshots/evidence in state DB
3. Submit removal requests via appropriate method per broker
4. Track request status (submitted → pending → confirmed → re-check)
5. Re-scan on schedule (weekly for top brokers, monthly for others)
6. Alert on re-listings

### 5.2 Dark Web & Breach Monitoring

**Goal**: Continuous monitoring for exposed credentials and personal data in breaches.

**Data Sources**:
- Have I Been Pwned API (email breach checks, password exposure)
- DeHashed API (comprehensive breach search by email, name, phone, username)
- Breachsense API (dark web marketplaces, infostealer logs)
- Local breach database indexing (for offline analysis)

**Monitored Data Points**:
- Email addresses (personal + work)
- Phone numbers
- Usernames across platforms
- Password hashes / plaintext passwords
- Physical addresses
- SSN fragments (if detected in breaches)

**Actions on Detection**:
- Immediate notification (Slack, email, CLI alert)
- Credential rotation recommendations
- Affected service identification
- Historical breach timeline

### 5.3 OSINT Reconnaissance & Exposure Mapping

**Goal**: Map the complete digital footprint — what an attacker can find about you.

**Discovery Vectors**:
- **Username enumeration**: Sherlock (400+ sites), Maigret (3,000+ sites), Blackbird (600+ sites)
- **Email enumeration**: holehe, email2phone, OSINT Industries
- **Social media scraping**: Public profiles on LinkedIn, Twitter/X, Facebook, Instagram, GitHub
- **Image search**: PimEyes (reverse facial recognition), TinEye, Google Images
- **Domain/WHOIS**: Domain ownership exposure
- **Public records**: Court records, property records, voter registration, business filings
- **Google dorking**: Site-specific searches for name + PII combinations

**Output**: Exposure report with risk scoring per finding:
- CRITICAL: Home address, SSN, financial accounts exposed
- HIGH: Phone number, email, family member names
- MEDIUM: Employment history, social profiles, username patterns
- LOW: Archived/cached pages, historical records

### 5.4 Social Media Privacy Hardening

**Goal**: Identify and fix privacy misconfigurations across social platforms.

**Checks**:
- Profile visibility settings (public vs. private)
- Location data in posts/photos (EXIF metadata)
- Tagged photos exposing location patterns
- Friend/connection list visibility
- Username reuse across platforms (credential stuffing risk)
- Impersonation account detection

### 5.5 Reporting & Analytics

**Goal**: Clear, actionable reports on privacy posture over time.

**Report Types**:
- **Exposure Report**: Full OSINT reconnaissance output with risk scores
- **Removal Status Report**: Broker-by-broker removal tracking
- **Breach Report**: Credential exposure history and current status
- **Trend Report**: Privacy posture improvement over time
- **Family Report**: Multi-person aggregate view

**Formats**: Markdown, HTML, PDF, JSON (for API consumption)

---

## 6. Technical Components

### 6.1 MCP Server: `digital-footprint-mcp`

The core MCP server providing tools to Claude Code and agents.

**Tools**:

| Tool | Description |
|------|-------------|
| `footprint_scan` | Full OSINT scan for a person (name, email, phone, location) |
| `footprint_broker_check` | Check specific data broker for person's data |
| `footprint_broker_remove` | Submit removal request to specific broker |
| `footprint_breach_check` | Check email/username against breach databases |
| `footprint_username_search` | Search username across 3,000+ sites |
| `footprint_exposure_report` | Generate comprehensive exposure report |
| `footprint_removal_status` | Get status of all pending removals |
| `footprint_add_person` | Add person to protection (self, family member) |
| `footprint_schedule_scan` | Configure automated scan schedule |
| `footprint_dark_web_monitor` | Check dark web sources for exposed data |
| `footprint_social_audit` | Audit social media privacy settings |
| `footprint_google_dork` | Run targeted Google searches for data exposure |

### 6.2 Claude Code Skills

| Skill | Trigger | Description |
|-------|---------|-------------|
| `/footprint` | Main entry | Full system status, quick actions menu |
| `/vanish` | Removal workflow | Interactive broker removal workflow |
| `/exposure` | Scan & report | Run exposure scan and generate report |
| `/breach` | Breach check | Check for credential exposure |
| `/privacy-audit` | Social audit | Audit social media & online accounts |

### 6.3 Agents

| Agent | Type | Purpose |
|-------|------|---------|
| `digital-footprint-orchestrator` | Orchestrator | Coordinates all sub-agents, schedules scans |
| `broker-scanner` | Scanner | Discovers person's data across broker sites |
| `broker-remover` | Executor | Submits and tracks removal requests |
| `breach-monitor` | Monitor | Continuous breach database surveillance |
| `osint-recon` | Researcher | Deep OSINT reconnaissance |
| `exposure-reporter` | Reporter | Generates reports and risk assessments |

### 6.4 CLI Commands

```bash
# Quick commands
dfp scan <name> [--email EMAIL] [--phone PHONE]    # Run full scan
dfp status                                           # Show protection status
dfp remove --broker spokeo                           # Remove from specific broker
dfp remove --all                                     # Submit all pending removals
dfp breach <email>                                   # Check for breaches
dfp report [--format html|pdf|md|json]               # Generate report
dfp schedule [--weekly|--monthly]                     # Configure auto-scan
dfp persons                                          # List protected persons
dfp add-person <name> --relation self|spouse|child   # Add person
```

### 6.5 Data Storage

**SQLite Database** (`~/.digital-footprint/footprint.db`):

```sql
-- Protected persons
CREATE TABLE persons (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    relation TEXT DEFAULT 'self',
    emails TEXT,           -- JSON array
    phones TEXT,           -- JSON array
    addresses TEXT,        -- JSON array
    usernames TEXT,        -- JSON array
    date_of_birth TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data broker registry
CREATE TABLE brokers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT,
    opt_out_method TEXT,   -- web_form|email|api|phone|mail
    opt_out_url TEXT,
    opt_out_email TEXT,
    difficulty TEXT,       -- easy|medium|hard|manual
    recheck_days INTEGER DEFAULT 30,
    notes TEXT
);

-- Scan results (findings)
CREATE TABLE findings (
    id INTEGER PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    broker_id INTEGER REFERENCES brokers(id),
    source TEXT,           -- broker|breach|osint|social
    finding_type TEXT,     -- profile|listing|breach|username|image
    data_found TEXT,       -- JSON of discovered data
    risk_level TEXT,       -- critical|high|medium|low
    screenshot_path TEXT,
    url TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active'  -- active|removal_pending|removed|re_listed
);

-- Removal requests
CREATE TABLE removals (
    id INTEGER PRIMARY KEY,
    finding_id INTEGER REFERENCES findings(id),
    person_id INTEGER REFERENCES persons(id),
    broker_id INTEGER REFERENCES brokers(id),
    method TEXT,           -- web_form|email|api|phone|mail
    status TEXT DEFAULT 'pending',  -- pending|submitted|confirmed|failed|re_listed
    submitted_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    notes TEXT
);

-- Breach findings
CREATE TABLE breaches (
    id INTEGER PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    breach_name TEXT,
    breach_date TEXT,
    data_types TEXT,       -- JSON array: email, password, phone, etc.
    source TEXT,           -- hibp|dehashed|breachsense
    severity TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action_taken TEXT
);

-- Scan history
CREATE TABLE scans (
    id INTEGER PRIMARY KEY,
    person_id INTEGER,
    scan_type TEXT,        -- full|broker|breach|osint|social
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    findings_count INTEGER,
    new_findings INTEGER,
    removed_count INTEGER
);
```

### 6.6 Broker Registry Format

Each broker stored as a YAML file in `brokers/` directory:

```yaml
name: Spokeo
url: https://www.spokeo.com
category: people_search
opt_out:
  method: web_form
  url: https://www.spokeo.com/optout
  steps:
    - Search for your profile on spokeo.com
    - Copy the profile URL
    - Go to spokeo.com/optout
    - Paste profile URL
    - Enter email for confirmation
    - Click confirmation link in email
  captcha: true
  email_verification: true
  time_to_removal: "24-72 hours"
recheck_days: 30
difficulty: easy
automatable: true
playwright_script: spokeo_optout.py
notes: "Retains data for paid subscribers even after opt-out"
```

---

## 7. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| MCP Server | Python + FastMCP | Consistent with existing MCP servers |
| CLI Tool | Python (Click) | Quick scripting, rich library ecosystem |
| Browser Automation | Playwright | Headless browser for form submission, stealth mode |
| Username Search | Maigret (Python) | 3,000+ sites, more comprehensive than Sherlock |
| Email Templates | Jinja2 | CCPA/GDPR templated legal requests |
| Database | SQLite | Local, no server needed, portable |
| Breach APIs | HIBP, DeHashed | Industry standard breach databases |
| OSINT Framework | SpiderFoot + custom | Automated reconnaissance |
| Scheduling | Cron + agent-runtime-mcp | Periodic scans and re-checks |
| Reports | Jinja2 + WeasyPrint | HTML/PDF report generation |
| State | enhanced-memory-mcp | Cross-session knowledge persistence |
| Notifications | Slack/Email hooks | Real-time alerting |

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Project scaffolding (Python project, pyproject.toml)
- [ ] SQLite database schema and migration system
- [ ] Broker registry format and initial population (top 50 brokers)
- [ ] MCP server skeleton with basic tools
- [ ] Person management (add/list/update protected persons)
- [ ] `/footprint` skill — basic status view

### Phase 2: Discovery (Week 3-4)
- [ ] Broker scanner — check top 50 brokers for person's data
- [ ] Playwright automation framework with stealth mode
- [ ] Username search integration (Maigret)
- [ ] HIBP breach check integration
- [ ] Google dorking engine
- [ ] `/exposure` skill — run scan, show results
- [ ] Exposure report generation (Markdown)

### Phase 3: Removal Engine (Week 5-6)
- [ ] Email-based removal engine (SMTP + Jinja2 templates)
- [ ] Web form automation for top 20 brokers (Playwright scripts)
- [ ] Removal request tracking and status management
- [ ] Confirmation email parsing (IMAP monitoring)
- [ ] `/vanish` skill — interactive removal workflow
- [ ] Re-check scheduling for removed listings

### Phase 4: Monitoring (Week 7-8)
- [ ] Dark web monitoring (DeHashed/Breachsense integration)
- [ ] Continuous broker re-scan scheduling
- [ ] Re-listing detection and auto-removal
- [ ] Notification system (Slack + email)
- [ ] `/breach` skill — breach check workflow
- [ ] Social media privacy audit

### Phase 5: Agents & Automation (Week 9-10)
- [ ] Orchestrator agent definition
- [ ] Scanner agent (autonomous broker discovery)
- [ ] Remover agent (autonomous removal submission)
- [ ] Monitor agent (continuous surveillance)
- [ ] Reporter agent (periodic report generation)
- [ ] Integration with agent-runtime-mcp for scheduling

### Phase 6: Scale & Polish (Week 11-12)
- [ ] Expand broker registry to 200+ brokers
- [ ] CA DROP API integration (when available Aug 2026)
- [ ] PDF report generation
- [ ] Family/multi-person dashboard
- [ ] Historical trend tracking
- [ ] CLI tool packaging and distribution

---

## 9. Data Broker Registry — Initial Target List

### Priority 1: High-Traffic People Search (automated removal)
1. Spokeo
2. BeenVerified
3. WhitePages / WhitePages Premium
4. TruePeopleSearch
5. FastPeopleSearch
6. Intelius
7. PeopleFinder
8. Radaris
9. MyLife
10. USPhoneBook
11. AnyWho
12. Addresses.com
13. PeopleLooker
14. PeopleSmart
15. Nuwber
16. That's Them
17. SearchPeopleFree
18. ClustrMaps
19. Zabasearch
20. PublicDataUSA

### Priority 2: Background Check / Records
21. InstantCheckmate
22. TruthFinder
23. CheckPeople
24. Advanced Background Checks
25. SmartBackgroundChecks
26. Cyber Background Checks
27. InfoTracer
28. SearchQuarry
29. SpyFly
30. PrivateEye

### Priority 3: Marketing & Aggregators
31. Acxiom
32. Oracle Data Cloud
33. Epsilon
34. Equifax Marketing Services
35. Experian Marketing Services
36. TransUnion (signal sharing)
37. CoreLogic
38. LexisNexis

### Priority 4: Social / Image
39. Social Catfish
40. PimEyes
41. FaceCheck.id
42. Classmates.com
43. FamilyTreeNow
44. FamilySearch
45. Ancestry.com

### Priority 5: Property / Financial
46. Zillow (owner info)
47. Redfin (owner info)
48. County assessor portals (varies)
49. PropertyRecs
50. Rehold

---

## 10. Legal Framework

All removal requests leverage existing privacy regulations:

- **CCPA/CPRA** (California): Right to delete, right to opt-out of sale
- **GDPR** (EU/UK): Right to erasure (Article 17)
- **Virginia CDPA**: Consumer data protection
- **Colorado Privacy Act**: Opt-out rights
- **Connecticut Data Privacy Act**: Deletion rights
- **CA DELETE Act / DROP**: Single-request broker deletion (Aug 2026)

**Email template types**:
- CCPA deletion request
- CCPA do-not-sell request
- GDPR erasure request (Article 17)
- Generic privacy removal request
- Follow-up / escalation template
- Regulatory complaint template (for non-compliant brokers)

---

## 11. Security Considerations

- **All PII stored encrypted at rest** (SQLite + encryption extension)
- **API keys stored in .env**, never committed
- **Playwright runs in stealth mode** to avoid bot detection
- **Rate limiting** on all broker requests to avoid IP bans
- **Proxy rotation** available for high-volume scanning
- **No cloud dependencies** — everything runs locally
- **Audit log** of all actions taken

---

## 12. Success Metrics

| Metric | Target |
|--------|--------|
| Brokers with automated removal | 50+ in Phase 3, 200+ by Phase 6 |
| Scan coverage (OSINT sources) | 3,000+ sites |
| Removal success rate | >80% automated |
| Time from discovery to removal request | <1 hour (automated) |
| Re-listing detection time | <7 days |
| Breach notification latency | <24 hours |
| Total cost | $0 base + ~$50/yr for premium breach APIs |

---

## 13. Open Source References

| Project | URL | Use |
|---------|-----|-----|
| JustVanish | github.com/AnalogJ/justvanish | Email-based broker removal (Go, MIT) |
| Big-Ass Data Broker Opt-Out List | github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List | Broker registry reference |
| Maigret | github.com/soxoj/maigret | Username search across 3,000+ sites |
| Sherlock | github.com/sherlock-project/sherlock | Username search across 400+ sites |
| Blackbird | github.com/p1ngul1n0/blackbird | Username search across 600+ sites |
| SpiderFoot | github.com/smicallef/spiderfoot | OSINT automation framework |
| databroker_remover | github.com/visible-cx/databroker_remover | Removal email generation |
| PrivacyBot | privacybot.io | Email-based removal automation |
| holehe | github.com/megadose/holehe | Email-to-account enumeration |
| CA DROP | privacy.ca.gov/drop | California broker deletion portal |

---

## 14. Risk & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bot detection on broker sites | Removal requests blocked | Stealth Playwright, human-like delays, proxy rotation |
| CAPTCHA on opt-out forms | Automation blocked | 2Captcha/Anti-Captcha API integration, flag for manual |
| Broker non-compliance | Data stays listed | Escalation templates, regulatory complaint filing |
| API rate limits (HIBP, etc.) | Incomplete breach data | Caching, intelligent request scheduling |
| Data re-listing after removal | Ongoing exposure | Continuous monitoring with auto-re-removal |
| IP blocking from scanning | Scanner disabled | Residential proxy pool, Tor circuit rotation |
