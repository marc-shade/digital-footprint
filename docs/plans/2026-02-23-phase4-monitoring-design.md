# Phase 4: Dark Web Monitoring + Social Media Audit Design

**Date**: 2026-02-23
**Status**: Approved
**Scope**: HIBP paste monitoring, Ahmia.fi dark web search, holehe email registration check, Playwright social profile scraping, `/monitor` skill

---

## What Phase 4 Builds

Phase 3 gave us the removal engine. Phase 4 adds continuous monitoring and social media privacy auditing: we detect exposure on dark web paste sites, check which services know your email, and audit what your social profiles reveal publicly.

---

## Architecture

```
digital_footprint/scanners/
  dark_web_scanner.py    # HIBP paste endpoint + Ahmia.fi clearnet search
  social_auditor.py      # Playwright scraping of public social profiles
  holehe_scanner.py      # holehe CLI wrapper for email registration check
digital_footprint/monitors/
  __init__.py
  dark_web_monitor.py    # Orchestrates dark web scans, persists to DB
```

Follows the Phase 2 scanner pattern: one module per source, independent, testable.

---

## Components

### 1. Dark Web Scanner (`dark_web_scanner.py`)

Two surface-accessible sources — no Tor required:

**HIBP Pastes:**
- `GET /api/v3/pasteaccount/{email}` with `hibp-api-key` header
- Returns pastes (Pastebin, Ghostbin, etc.) containing the email
- Each paste has: source, title, date, email count
- Rate limit: 10 req/min (shared with breach endpoint)

**Ahmia.fi Search:**
- `GET https://ahmia.fi/search/?q={email}` via httpx
- Clearnet search engine indexing Tor hidden services
- Parse HTML results for titles and .onion URLs
- Rate limit: be polite, 2-second delay between queries

Returns `DarkWebResult` dataclasses:
- `source` (hibp_paste, ahmia)
- `title`, `url`, `date`
- `severity` (critical if contains passwords, high for personal data, medium otherwise)

### 2. Social Auditor (`social_auditor.py`)

Visits public social profile URLs with Playwright and extracts visible PII.

**Input:** List of profile URLs from Maigret username search results.

**Per-profile extraction:**
- Display name, bio/description
- Location, email, phone, website
- Follower/following counts
- Profile photo (exists or not)

**PII flagging:**
- Email visible in bio → high risk
- Phone visible → high risk
- Full real name + location → medium risk
- Generic username only → low risk

**Platform-specific selectors** stored as a dict in the module:
- Twitter/X, Instagram, Facebook, LinkedIn, GitHub, Reddit, TikTok
- Fallback: extract from `<meta property="og:*">` tags for unknown platforms

**Output:** `SocialAuditResult` per profile with: platform, url, visible_fields dict, pii_flags list, privacy_score (0-100).

### 3. holehe Scanner (`holehe_scanner.py`)

Wraps holehe CLI as subprocess (same pattern as Maigret wrapper):

```bash
holehe email@example.com --only-used --csv
```

Parses output into `HoleheResult` dataclasses:
- `service_name`, `url`, `exists` (bool)
- `risk_level`: high for financial/dating, medium for social, low for entertainment

### 4. Dark Web Monitor (`dark_web_monitor.py`)

Orchestrates dark_web_scanner + holehe:
- Runs both scanners for a given email
- Deduplicates results against existing findings in DB
- Stores new findings (source="dark_web" or source="holehe")
- Returns combined report

---

## MCP Tools

Replace stubs:
- `footprint_dark_web_monitor(email)` — runs HIBP pastes + Ahmia + holehe, returns findings
- `footprint_social_audit(person_id)` — scrapes public social profiles, returns privacy audit

## Skills

- `/monitor` — interactive dark web monitoring and social audit workflow

---

## DB Changes

None. Existing `findings` table handles new source types:
- `source="dark_web"` for paste and Ahmia findings
- `source="holehe"` for email registration findings
- `source="social_audit"` for social profile PII flags

---

## Dependencies

No new pip dependencies. holehe called as subprocess (complex deps, like Maigret). httpx and Playwright already installed.

---

## Verification Criteria

Phase 4 is complete when:
1. HIBP paste scanner queries paste endpoint and returns results
2. Ahmia.fi scanner searches clearnet and parses HTML results
3. holehe scanner wraps CLI and parses CSV output
4. Social auditor scrapes public profiles and flags PII exposure
5. Dark web monitor orchestrates scanners and deduplicates
6. `footprint_dark_web_monitor` MCP tool works end-to-end
7. `footprint_social_audit` MCP tool works end-to-end
8. `/monitor` skill orchestrates the workflow
9. All new tests pass
10. Existing 111 tests still pass
