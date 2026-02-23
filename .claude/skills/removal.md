---
name: removal
description: Submit data removal requests to brokers and track their status
---

# /removal - Data Broker Removal Requests

Submit opt-out and removal requests to data brokers found holding your personal data.

## Usage

`/removal` - Start removal process for all active findings
`/removal <broker_slug>` - Remove from a specific broker
`/removal status` - Check status of all removal requests
`/removal verify` - Re-scan brokers to verify removals completed

## Steps

### For new removals:
1. Call `footprint_list_persons` to identify the person
2. Call `footprint_exposure_report` to see active findings
3. For each broker with findings, call `footprint_broker_remove` with the broker slug and person ID
4. Present results to user:
   - Email removals: show that email was sent with reference ID
   - Web form removals: show result (submitted or CAPTCHA required)
   - Phone/mail removals: show step-by-step instructions
5. Call `footprint_removal_status` to show the dashboard

### For status check:
1. Call `footprint_removal_status` with person ID
2. Present grouped by status: pending, submitted, confirmed, failed

### For verification:
1. Call `footprint_verify_removals` with person ID
2. Present which removals were confirmed vs still found
