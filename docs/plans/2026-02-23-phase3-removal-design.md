# Phase 3: Removal Engine Design

**Date**: 2026-02-23
**Status**: Approved
**Scope**: Email-based removal (SMTP), Playwright web form automation, CAPTCHA pause, manual instructions, removal verification, `/removal` skill

---

## What Phase 3 Builds

Phase 2 gave us discovery: scanning brokers, checking breaches, searching usernames. Phase 3 acts on those findings by submitting opt-out/removal requests to data brokers and verifying they comply.

---

## Architecture: Strategy Pattern

```
digital_footprint/removers/
  __init__.py
  orchestrator.py       # Central dispatch: person + broker -> handler
  email_remover.py      # Render Jinja2 template, send via SMTP
  web_form_remover.py   # Playwright automation, CAPTCHA pause
  manual_remover.py     # Generate instructions for phone/mail methods
  verification.py       # Re-scan broker to confirm removal
  templates/            # Jinja2 templates
    ccpa_deletion.j2
    ccpa_do_not_sell.j2
    gdpr_erasure.j2
    followup.j2
    generic_removal.j2
```

The orchestrator dispatches to the correct handler based on `broker.opt_out_method`. Each handler implements a common interface: `submit(person, broker) -> RemovalResult`.

---

## Components

### 1. RemovalOrchestrator (`orchestrator.py`)

Central entry point for all removal operations.

**Functions:**
- `submit_removal(person_id, broker_slug, db) -> RemovalResult` — dispatch to handler, create DB record
- `check_removal_status(person_id, db) -> list[RemovalStatus]` — query all removals for person
- `process_pending_verifications(db) -> list[VerificationResult]` — find due verifications, re-scan

**Dispatch logic:**
| `opt_out_method` | Handler | Automation |
|------------------|---------|------------|
| `email` | EmailRemover | Full (SMTP send) |
| `web_form` | WebFormRemover | Full (Playwright + CAPTCHA pause) |
| `api` | ApiRemover (future) | Full |
| `phone` | ManualRemover | Instructions only |
| `mail` | ManualRemover | Instructions only |

### 2. EmailRemover (`email_remover.py`)

Sends opt-out emails using Jinja2 templates via SMTP.

**Template selection:**
- Broker is `ccpa_compliant` -> `ccpa_deletion.j2`
- Broker is `gdpr_compliant` -> `gdpr_erasure.j2`
- Otherwise -> `generic_removal.j2`

**Process:**
1. Generate `reference_id` (UUID)
2. Load person data + broker data into template context
3. Render template with Jinja2
4. Send via `smtplib.SMTP_SSL` using config credentials
5. Create `Removal` record: status=`submitted`, `submitted_at=now()`
6. Set `next_check_at` based on `broker.recheck_days`

### 3. WebFormRemover (`web_form_remover.py`)

Automates web-form opt-outs using Playwright.

**Process:**
1. Launch stealth browser (reuse `playwright_scanner.create_stealth_browser()`)
2. Navigate to `broker.opt_out_url`
3. Execute steps from broker YAML:
   - Form fills, clicks, navigation
   - Screenshot at each step (audit trail)
4. **CAPTCHA handling:** detect CAPTCHA presence, switch to headed mode, pause for user to solve, then continue automation
5. Create `Removal` record: status=`submitted`

**CAPTCHA detection:** Check for common CAPTCHA selectors (`iframe[src*="recaptcha"]`, `iframe[src*="hcaptcha"]`, `.g-recaptcha`, `.h-captcha`).

**Step executor maps broker YAML steps to Playwright actions.** The executor is generic; broker-specific logic lives in the YAML `opt_out.steps` field.

### 4. ManualRemover (`manual_remover.py`)

For phone and mail methods where automation is not possible.

**Process:**
1. Load broker's `opt_out.steps` from YAML
2. Format as numbered instructions with person-specific data filled in
3. Create `Removal` record: status=`instructions_generated`
4. Return formatted instructions for user to follow

### 5. RemovalVerifier (`verification.py`)

Confirms that submitted removals actually worked.

**Process:**
1. Query DB for removals where `status = "submitted"` and `next_check_at <= now()`
2. For each removal, re-scan the broker using Phase 2's `broker_scanner.scan_broker()`
3. If person **not found** -> status=`confirmed`, `confirmed_at=now()`
4. If person **still found** -> increment `attempts`, set new `next_check_at`
5. If `attempts > 3` -> status=`failed`, flag for manual review
6. Return verification summary

---

## Data Flow

```
footprint_broker_remove(broker_slug, person_id)
  -> Orchestrator loads person + broker from DB
  -> Picks handler: email/web_form/phone/mail
  -> Handler executes removal
  -> Creates Removal record
  -> Updates Finding.status to "removal_pending"
  -> Returns result

footprint_removal_status(person_id)
  -> Queries all Removal records for person
  -> Groups by status (pending, submitted, confirmed, failed)
  -> Returns dashboard JSON

footprint_verify_removals(person_id)
  -> Finds removals past next_check_at
  -> Re-scans each broker via broker_scanner
  -> Updates removal statuses
  -> Returns verification report
```

---

## DB Changes

None. The existing `removals` table has all needed columns: `status`, `submitted_at`, `confirmed_at`, `last_checked_at`, `attempts`, `next_check_at`, `notes`, `method`. The `findings` table `status` field already supports `removal_pending`.

New DB methods needed in `db.py`:
- `insert_removal(removal) -> int`
- `get_removals_by_person(person_id) -> list[Removal]`
- `get_pending_verifications() -> list[Removal]` (where next_check_at <= now)
- `update_removal(removal_id, **kwargs)`

---

## MCP Tools

Replace stubs:
- `footprint_broker_remove(broker_slug, person_id)` — submit removal request
- `footprint_removal_status(person_id)` — removal status dashboard

Add:
- `footprint_verify_removals(person_id)` — run verification on submitted removals

## Skills

- `/removal` — interactive removal workflow skill

---

## Dependencies (New)

```
jinja2>=3.1
```

SMTP is stdlib (`smtplib`, `email.mime`). Playwright already installed.

---

## Verification Criteria

Phase 3 is complete when:
1. `footprint_broker_remove` dispatches to correct handler based on opt-out method
2. Email removals render Jinja2 templates and send via SMTP
3. Web form removals automate Playwright with CAPTCHA pause for user
4. Manual removals generate formatted instructions
5. `footprint_removal_status` returns all removal statuses grouped by state
6. `footprint_verify_removals` re-scans brokers and confirms/fails removals
7. `/removal` skill orchestrates the full workflow
8. DB methods for removal CRUD work correctly
9. All new tests pass
10. Existing 78 tests still pass
