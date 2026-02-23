---
name: breach
description: Check if an email has been exposed in data breaches
---

# /breach - Data Breach Check

Check if an email address has been exposed in known data breaches.

## Usage

`/breach` - Check the default person's primary email
`/breach <email>` - Check a specific email address

## What it does

1. Queries Have I Been Pwned API for breach history
2. Queries DeHashed API for exposed credentials
3. Reports severity and recommended actions

## Steps

1. Call `footprint_breach_check` with the email
2. Present results grouped by severity
3. For critical breaches (passwords exposed): recommend immediate password change + 2FA
4. For high breaches (personal data): recommend monitoring
5. For medium breaches (email only): note for awareness

## API Keys Required

- `HIBP_API_KEY` - Get from https://haveibeenpwned.com/API/Key ($3.50/month)
- `DEHASHED_API_KEY` - Get from https://dehashed.com (optional, $5/month)
