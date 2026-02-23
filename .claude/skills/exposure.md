---
name: exposure
description: Run a comprehensive exposure scan and generate a privacy report
---

# /exposure - Digital Footprint Exposure Scan

Run a full exposure scan for a person and generate a comprehensive report.

## Usage

`/exposure` - Scan the default person (id=1)
`/exposure <name>` - Scan a specific person by name

## What it does

1. Looks up the person in the database
2. Checks data breaches via HIBP and DeHashed (if API keys configured)
3. Searches for usernames across 3,000+ sites via Maigret
4. Builds Google dork queries for manual investigation
5. Generates a risk-scored exposure report

## Steps

1. Call `footprint_list_persons` to find the person
2. Call `footprint_breach_check` with their primary email
3. Call `footprint_username_search` with their usernames
4. Call `footprint_google_dork` with their name
5. Call `footprint_exposure_report` to generate the final report
6. Present the report to the user with actionable next steps
