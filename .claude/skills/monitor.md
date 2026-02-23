---
name: monitor
description: Run dark web monitoring and social media privacy audit
---

# /monitor - Dark Web Monitoring & Social Audit

Check for dark web exposure and audit social media privacy.

## Usage

`/monitor` - Full monitoring scan for default person
`/monitor dark` - Dark web scan only (paste sites, Ahmia, holehe)
`/monitor social` - Social media audit only
`/monitor <email>` - Dark web scan for specific email

## Steps

### Full monitoring scan:
1. Call `footprint_list_persons` to find the person
2. Call `footprint_dark_web_monitor` with their primary email
3. Call `footprint_social_audit` with their person ID
4. Present combined results with risk assessment

### Dark web only:
1. Call `footprint_dark_web_monitor` with the email
2. Present paste site findings, dark web references, and registered services
3. Highlight high-risk findings (dating sites, financial services, dark web mentions)

### Social audit only:
1. Call `footprint_social_audit` with person ID
2. Show which platforms have public profiles
3. Flag PII exposure (email, phone, real name, location visible)
4. Give per-platform privacy score

## Recommendations
- For paste site exposure: change passwords immediately, enable 2FA
- For holehe high-risk services: review and delete unused accounts
- For social PII exposure: update privacy settings on flagged platforms
