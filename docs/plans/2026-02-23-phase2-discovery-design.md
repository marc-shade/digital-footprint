# Phase 2: Discovery Design

**Date**: 2026-02-23
**Status**: Approved
**Scope**: Broker scanning (Playwright), username search (Maigret), breach checking (HIBP + DeHashed), Google dorking, `/exposure` skill, report generation

---

## What Phase 2 Builds

Phase 1 gave us the database, broker registry, and MCP server. Phase 2 makes it actually useful: we can now **scan** broker sites, **search** for usernames, **check** breaches, and **generate reports**.

---

## Components

### 1. Playwright Scanner Framework

Headless browser with stealth mode for checking broker sites.

**Architecture:**
```
digital_footprint/scanners/
  __init__.py
  playwright_scanner.py   # Base scanner with stealth browser
  broker_scanner.py       # Scan broker sites for person data
  google_dorker.py        # Google search exposure checks
```

**Key design decisions:**
- Use `playwright-stealth` to avoid bot detection
- One browser context per scan session, pages per broker
- Rate limit: 2-5 second random delay between requests
- Screenshot evidence of each finding
- Timeout: 30s per broker page

**broker_scanner.py** logic:
1. Load broker registry from DB
2. For each broker with a `search.url_pattern`:
   - Build search URL from person's name/location
   - Navigate, wait for results
   - Check if results contain person's PII (fuzzy name match)
   - If found: screenshot, extract data, create Finding
   - If not found: record as "not found" (no Finding created)
3. Return scan results

### 2. Username Search (Maigret Integration)

**Architecture:**
```
digital_footprint/scanners/
  username_scanner.py     # Maigret wrapper
```

Wraps Maigret CLI as a subprocess:
```bash
maigret <username> --json /tmp/maigret_<username>.json --timeout 10
```

Parse JSON output → create Findings for each discovered account.

### 3. Breach Checking (HIBP + DeHashed)

**Architecture:**
```
digital_footprint/scanners/
  breach_scanner.py       # HIBP + DeHashed integration
```

**HIBP** (per email):
- `GET /api/v3/breachedaccount/{email}` → list of breaches
- `GET /api/v3/pasteaccount/{email}` → pastes
- Rate: 10 req/min with API key

**DeHashed** (per email/phone/username):
- `GET /search?query=email:{value}` → full breach records
- Returns plaintext/hashed passwords, addresses, phones
- Rate: varies by plan

Both → deduplicated Breach records in DB.

### 4. Google Dorking

**Architecture:**
```
digital_footprint/scanners/
  google_dorker.py        # Google search for PII exposure
```

Dork patterns:
- `"Full Name" "email@example.com"`
- `"Full Name" "phone number"`
- `"Full Name" "street address"`
- `site:pastebin.com "email@example.com"`
- `filetype:pdf "Full Name"`

Uses Playwright to search Google (with delays to avoid rate limiting).

### 5. Report Generator

**Architecture:**
```
digital_footprint/reporters/
  __init__.py
  exposure_report.py      # Markdown/JSON report from scan results
```

Generates a structured report:
- Risk score (0-100) computed from findings
- Findings grouped by source (broker, breach, OSINT)
- Critical items highlighted
- Actionable recommendations

### 6. /exposure Skill

Interactive skill that orchestrates a full scan and presents results.

---

## Risk Scoring Algorithm

```
score = 0
for finding in findings:
    if finding.risk_level == "critical": score += 25
    elif finding.risk_level == "high": score += 10
    elif finding.risk_level == "medium": score += 5
    elif finding.risk_level == "low": score += 2

# Cap at 100
risk_score = min(score, 100)

# Risk label
if risk_score >= 75: "CRITICAL"
elif risk_score >= 50: "HIGH"
elif risk_score >= 25: "MODERATE"
else: "LOW"
```

---

## Dependencies (New)

```
playwright>=1.40
playwright-stealth>=1.0
maigret>=0.4       # Username search
httpx>=0.27        # Async HTTP for APIs
```

---

## Verification Criteria

Phase 2 is complete when:
1. `footprint_scan` runs a broker scan for a person and creates Findings
2. `footprint_breach_check` queries HIBP and DeHashed, creates Breach records
3. `footprint_username_search` runs Maigret and creates Findings
4. `footprint_google_dork` runs Google searches and creates Findings
5. `footprint_exposure_report` generates a Markdown report
6. `/exposure` skill orchestrates scan → report
7. All new tests pass
8. Existing 33 tests still pass
