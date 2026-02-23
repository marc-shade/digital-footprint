# Phase 1: Foundation Design

**Date**: 2026-02-23
**Status**: Approved
**Scope**: Project scaffolding, database, broker registry, MCP server, person management, `/footprint` skill

---

## Decisions

- **Framework**: FastMCP (matches enhanced-memory-mcp pattern)
- **Location**: `/Volumes/FILES/code/digital-footprint/`
- **Python**: 3.11+ with venv
- **Database**: SQLite at `~/.digital-footprint/footprint.db`
- **Initial scope**: Single person (Marc), 50 broker YAML definitions
- **Registration**: `~/.claude.json` mcpServers entry with venv python path

---

## Project Structure

```
digital-footprint/
  server.py                    # FastMCP server entry point
  requirements.txt             # Dependencies
  .env.example                 # Template for API keys
  CLAUDE.md
  PRD.md
  ARCHITECTURE.md

  digital_footprint/
    __init__.py
    db.py                      # SQLite connection, schema creation, migrations
    models.py                  # Dataclasses: Person, Broker, Finding, Removal, Breach, Scan
    config.py                  # Config loading: .env, XDG paths, defaults
    broker_registry.py         # Load/validate YAML broker files

    brokers/                   # 50 YAML broker definitions
      _schema.yaml
      spokeo.yaml
      beenverified.yaml
      whitepages.yaml
      truepeoplesearch.yaml
      ... (46 more)

    tools/                     # MCP tool implementations
      __init__.py
      person_tools.py          # footprint_add_person, footprint_list_persons, footprint_get_person
      broker_tools.py          # footprint_list_brokers, footprint_get_broker, footprint_broker_stats
      status_tools.py          # footprint_status (main dashboard)
      scan_tools.py            # footprint_scan (stub -> Phase 2)
      removal_tools.py         # footprint_broker_remove (stub -> Phase 3)
      breach_tools.py          # footprint_breach_check (stub -> Phase 2)
      osint_tools.py           # footprint_username_search (stub -> Phase 2)

  tests/
    __init__.py
    conftest.py                # Fixtures: temp DB, sample persons, sample brokers
    test_db.py                 # Schema creation, migrations
    test_models.py             # Dataclass validation
    test_config.py             # Config loading
    test_broker_registry.py    # YAML loading, validation
    test_person_tools.py       # Person CRUD operations
    test_broker_tools.py       # Broker registry queries
    test_status_tools.py       # Status dashboard
```

---

## Database Schema

```sql
CREATE TABLE persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'self',
    emails TEXT DEFAULT '[]',          -- JSON array
    phones TEXT DEFAULT '[]',          -- JSON array
    addresses TEXT DEFAULT '[]',       -- JSON array
    usernames TEXT DEFAULT '[]',       -- JSON array
    date_of_birth TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE brokers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,         -- YAML filename without extension
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    opt_out_method TEXT,               -- web_form|email|api|phone|mail
    opt_out_url TEXT,
    opt_out_email TEXT,
    difficulty TEXT DEFAULT 'medium',  -- easy|medium|hard|manual
    automatable INTEGER DEFAULT 0,    -- boolean
    recheck_days INTEGER DEFAULT 30,
    ccpa_compliant INTEGER DEFAULT 0,
    gdpr_compliant INTEGER DEFAULT 0,
    notes TEXT,
    yaml_hash TEXT,                    -- SHA256 of YAML file for change detection
    loaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    broker_id INTEGER REFERENCES brokers(id),
    source TEXT NOT NULL,              -- broker|breach|osint|social
    finding_type TEXT NOT NULL,        -- profile|listing|breach|username|image
    data_found TEXT DEFAULT '{}',      -- JSON
    risk_level TEXT DEFAULT 'medium',  -- critical|high|medium|low
    url TEXT,
    screenshot_path TEXT,
    status TEXT DEFAULT 'active',      -- active|removal_pending|removed|re_listed
    discovered_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE removals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id),
    person_id INTEGER NOT NULL REFERENCES persons(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    method TEXT NOT NULL,              -- web_form|email|api|phone|mail
    status TEXT DEFAULT 'pending',     -- pending|submitted|confirmed|failed|re_listed
    submitted_at TEXT,
    confirmed_at TEXT,
    last_checked_at TEXT,
    attempts INTEGER DEFAULT 0,
    next_check_at TEXT,
    notes TEXT
);

CREATE TABLE breaches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    breach_name TEXT NOT NULL,
    breach_date TEXT,
    data_types TEXT DEFAULT '[]',      -- JSON array
    source TEXT NOT NULL,              -- hibp|dehashed|breachsense
    severity TEXT DEFAULT 'medium',    -- critical|high|medium|low
    discovered_at TEXT DEFAULT (datetime('now')),
    action_taken TEXT
);

CREATE TABLE scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(id),
    scan_type TEXT NOT NULL,           -- full|broker|breach|osint|social
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    findings_count INTEGER DEFAULT 0,
    new_findings INTEGER DEFAULT 0,
    removed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'      -- running|completed|failed
);

CREATE INDEX idx_findings_person ON findings(person_id);
CREATE INDEX idx_findings_broker ON findings(broker_id);
CREATE INDEX idx_findings_status ON findings(status);
CREATE INDEX idx_removals_status ON removals(status);
CREATE INDEX idx_removals_person ON removals(person_id);
CREATE INDEX idx_breaches_person ON breaches(person_id);
CREATE INDEX idx_brokers_slug ON brokers(slug);
```

---

## MCP Tools (Phase 1)

### Implemented Tools

**footprint_add_person** — Register a person for protection
```
Input: name (str), emails (list[str]), phones (list[str], optional),
       addresses (list[str], optional), usernames (list[str], optional),
       date_of_birth (str, optional), relation (str, default="self")
Output: Person record with ID
```

**footprint_list_persons** — List all protected persons
```
Input: none
Output: List of person summaries with stats
```

**footprint_get_person** — Get full details for a person
```
Input: person_id (int) or name (str)
Output: Full person record with finding/removal/breach counts
```

**footprint_update_person** — Update person information
```
Input: person_id (int), fields to update
Output: Updated person record
```

**footprint_list_brokers** — List brokers in registry
```
Input: category (str, optional), difficulty (str, optional), automatable (bool, optional)
Output: List of broker summaries
```

**footprint_get_broker** — Get full broker details
```
Input: slug (str) or name (str)
Output: Full broker record including opt-out steps
```

**footprint_broker_stats** — Registry statistics
```
Input: none
Output: Counts by category, difficulty, method, automation status
```

**footprint_status** — System dashboard
```
Input: none
Output: Protected persons count, total brokers, findings by status,
        pending removals, recent breaches, last scan dates
```

### Stub Tools (Registered but not functional until later phases)

- `footprint_scan` — "Scanning not yet implemented. Coming in Phase 2."
- `footprint_broker_check` — Same
- `footprint_broker_remove` — "Removal engine not yet implemented. Coming in Phase 3."
- `footprint_breach_check` — "Breach checking not yet implemented. Coming in Phase 2."
- `footprint_username_search` — Same
- `footprint_exposure_report` — Same
- `footprint_removal_status` — Same
- `footprint_dark_web_monitor` — "Dark web monitoring not yet implemented. Coming in Phase 4."
- `footprint_social_audit` — Same
- `footprint_google_dork` — Same

---

## Broker Registry — Initial 50

Sourced from Big-Ass Data Broker Opt-Out List and Incogni opt-out guides.

**People Search (20)**: Spokeo, BeenVerified, WhitePages, TruePeopleSearch, FastPeopleSearch, Intelius, PeopleFinder, Radaris, MyLife, USPhoneBook, AnyWho, Addresses.com, PeopleLooker, PeopleSmart, Nuwber, That's Them, SearchPeopleFree, ClustrMaps, Zabasearch, PublicDataUSA

**Background Check (10)**: InstantCheckmate, TruthFinder, CheckPeople, AdvancedBackgroundChecks, SmartBackgroundChecks, CyberBackgroundChecks, InfoTracer, SearchQuarry, SpyFly, PrivateEye

**Marketing/Aggregators (8)**: Acxiom, Oracle Data Cloud, Epsilon, Equifax Marketing, Experian Marketing, TransUnion, CoreLogic, LexisNexis

**Social/Image (7)**: Social Catfish, PimEyes, FaceCheck.id, Classmates.com, FamilyTreeNow, FamilySearch, Ancestry.com

**Property (5)**: Zillow, Redfin, PropertyRecs, Rehold, county assessor (template)

Each YAML file follows the schema in `docs/BROKER_REGISTRY.md`.

---

## /footprint Skill

Basic status view skill for Phase 1:

```
/footprint
  → Shows:
    - Protected persons: 1 (Marc Shade)
    - Broker registry: 50 brokers loaded
    - Findings: 0 active / 0 removed
    - Pending removals: 0
    - Breaches detected: 0
    - Last scan: never
    - Quick actions: [scan] [add person] [list brokers]
```

Skill file at `.claude/skills/footprint.md`.

---

## Dependencies

```
fastmcp>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
click>=8.0          # For future CLI
```

Test dependencies:
```
pytest>=8.0
pytest-asyncio>=0.23
```

---

## Registration in ~/.claude.json

```json
{
  "digital-footprint-mcp": {
    "command": "/Volumes/FILES/code/digital-footprint/.venv/bin/python",
    "args": ["/Volumes/FILES/code/digital-footprint/server.py"]
  }
}
```

---

## Verification Criteria

Phase 1 is complete when:
1. `server.py` starts without errors
2. All 4 implemented tools respond correctly (person CRUD, broker queries, status)
3. All 10 stub tools return their "not yet implemented" messages
4. SQLite DB is created at `~/.digital-footprint/footprint.db` with correct schema
5. 50 broker YAML files load and validate
6. `pytest tests/` passes
7. MCP server registered in `~/.claude.json` and accessible from Claude Code
8. `/footprint` skill shows correct status
