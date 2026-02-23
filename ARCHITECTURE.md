# Digital Footprint — Architecture

## System Layers

### Layer 1: User Interface
```
Claude Code Skills        CLI Tool (dfp)        Agents (autonomous)
  /footprint               dfp scan              orchestrator
  /vanish                  dfp remove            scanner
  /exposure                dfp breach            remover
  /breach                  dfp report            monitor
  /privacy-audit           dfp status            reporter
```

### Layer 2: MCP Server (`digital-footprint-mcp`)
Central coordination layer exposing tools to Claude Code and agents.

**Tools provided:**
- `footprint_scan` — Full person scan (orchestrates sub-scanners)
- `footprint_broker_check` — Check single broker for person data
- `footprint_broker_remove` — Submit removal to specific broker
- `footprint_breach_check` — Query breach databases
- `footprint_username_search` — Username enumeration (Maigret)
- `footprint_exposure_report` — Generate comprehensive report
- `footprint_removal_status` — Track all pending removals
- `footprint_add_person` — Register person for protection
- `footprint_schedule_scan` — Configure scan automation
- `footprint_dark_web_monitor` — Dark web surveillance
- `footprint_social_audit` — Social media privacy check
- `footprint_google_dork` — Targeted search exposure check

### Layer 3: Engines

#### Broker Scanner Engine
```
Input: Person PII (name, email, phone, address)
Process:
  1. Load broker registry (YAML files)
  2. For each broker:
     a. Search broker site for person (Playwright headless)
     b. Parse results for PII matches
     c. Screenshot evidence
     d. Score risk level
     e. Store finding in DB
Output: List of findings with risk scores
```

#### Removal Engine
```
Input: Finding (broker + person + evidence)
Process:
  1. Load broker's opt-out configuration (YAML)
  2. Select removal method:
     - web_form: Playwright script specific to broker
     - email: SMTP with CCPA/GDPR template
     - api: Direct API call (CA DROP, etc.)
     - phone/mail: Flag for manual + generate instructions
  3. Submit removal request
  4. Track confirmation
  5. Schedule re-check (broker.recheck_days)
Output: Removal record with status
```

#### Breach Monitor Engine
```
Input: Person emails, phones, usernames
Process:
  1. Query HIBP API (email → breaches)
  2. Query DeHashed API (email, phone, username → breach records)
  3. Diff against known breaches in DB
  4. Score new findings by severity
  5. Generate alerts for new breaches
Output: Breach findings with severity and recommended actions
```

#### OSINT Reconnaissance Engine
```
Input: Person identifiers (name, email, username, phone)
Process:
  1. Username search (Maigret → 3,000+ sites)
  2. Email enumeration (holehe → registered services)
  3. Google dorking (name + PII patterns)
  4. Public records search
  5. Social media profile discovery
  6. Aggregate and deduplicate
  7. Risk score each finding
Output: Comprehensive exposure map
```

### Layer 4: Data

#### SQLite Database (`~/.digital-footprint/footprint.db`)
- `persons` — Protected individuals
- `brokers` — Data broker registry (mirrors YAML for queries)
- `findings` — Discovered data exposure
- `removals` — Removal request tracking
- `breaches` — Breach detection history
- `scans` — Scan execution log

#### Broker Registry (`brokers/*.yaml`)
Human-readable, version-controlled broker definitions with:
- Opt-out method and URL
- Step-by-step removal instructions
- Playwright automation script reference
- Difficulty rating and automation status
- Re-check interval

#### Enhanced Memory (MCP)
Cross-session persistence for:
- Scan results summaries
- Removal success patterns
- Broker behavior changes
- Person protection status

### Layer 5: External Services

| Service | Purpose | Auth | Cost |
|---------|---------|------|------|
| Have I Been Pwned | Breach detection | API key | $3.50/mo |
| DeHashed | Deep breach search | API key | $5/mo |
| Breachsense | Dark web monitoring | API key | Varies |
| 2Captcha | CAPTCHA solving | API key | ~$3/1000 |
| CA DROP API | Batch broker deletion | Free (CA residents) | Free |
| Residential proxies | Anti-detection | Subscription | ~$10/mo |

## Data Flow: Full Scan

```
User: /exposure marc@example.com
  │
  ├─→ footprint_scan(email="marc@example.com")
  │     │
  │     ├─→ Broker Scanner (parallel)
  │     │     ├─→ Spokeo → found: name, address, phone
  │     │     ├─→ BeenVerified → found: name, relatives
  │     │     ├─→ WhitePages → not found
  │     │     └─→ ... (50+ brokers)
  │     │
  │     ├─→ Breach Monitor (parallel)
  │     │     ├─→ HIBP → 3 breaches found
  │     │     └─→ DeHashed → 5 records with passwords
  │     │
  │     ├─→ OSINT Recon (parallel)
  │     │     ├─→ Maigret → 47 accounts found
  │     │     ├─→ Google dorks → 12 results
  │     │     └─→ holehe → 23 registered services
  │     │
  │     └─→ Aggregate & Score
  │           ├─→ Store findings in DB
  │           └─→ Generate exposure report
  │
  └─→ Display: Risk summary + actionable recommendations
```

## Data Flow: Removal

```
User: /vanish --broker spokeo
  │
  ├─→ footprint_broker_remove(broker="spokeo", person_id=1)
  │     │
  │     ├─→ Load broker config (brokers/spokeo.yaml)
  │     ├─→ Method: web_form
  │     │     ├─→ Launch Playwright (stealth mode)
  │     │     ├─→ Navigate to opt-out URL
  │     │     ├─→ Search for profile
  │     │     ├─→ Submit opt-out form
  │     │     ├─→ Solve CAPTCHA if needed
  │     │     ├─→ Screenshot confirmation
  │     │     └─→ Close browser
  │     │
  │     ├─→ Wait for confirmation email
  │     │     └─→ IMAP monitor → click confirmation link
  │     │
  │     ├─→ Update removal status: submitted → confirmed
  │     └─→ Schedule re-check in 30 days
  │
  └─→ Display: Removal confirmed, next re-check date
```

## Agent Orchestration

```
Orchestrator Agent (cron: daily)
  │
  ├─→ Check scan schedule
  │     └─→ Spawn Scanner Agent for due persons
  │
  ├─→ Check removal status
  │     └─→ Re-check confirmed removals past recheck_days
  │           └─→ If re-listed: Spawn Remover Agent
  │
  ├─→ Run breach monitor
  │     └─→ Spawn Monitor Agent for all persons
  │
  └─→ Weekly: Spawn Reporter Agent
        └─→ Generate and deliver exposure report
```
