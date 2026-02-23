# Claude Code Skills Specification

## Skill: /footprint

**Purpose**: Main entry point — system status and quick actions
**Trigger**: `/footprint`

**Behavior**:
1. Show protection status summary:
   - Number of protected persons
   - Total findings (active/removed)
   - Pending removals
   - Recent breaches
   - Last scan date per person
   - Next scheduled scan
2. Offer quick actions:
   - Run full scan
   - View pending removals
   - Check breaches
   - Generate report
   - Add person

---

## Skill: /vanish

**Purpose**: Interactive data broker removal workflow
**Trigger**: `/vanish [--broker NAME] [--all] [--person NAME]`

**Behavior**:
1. If `--all`: Submit removal requests for all active findings
2. If `--broker`: Remove from specific broker
3. If no args: Show active findings grouped by broker, let user select
4. For each removal:
   - Show broker name, data found, removal method
   - Confirm with user before submitting
   - Execute removal (automated or generate manual instructions)
   - Report status
5. Show summary: submitted, pending confirmation, failed

---

## Skill: /exposure

**Purpose**: Run OSINT exposure scan and generate report
**Trigger**: `/exposure [EMAIL|NAME] [--deep] [--person NAME]`

**Behavior**:
1. If first run: Prompt for person details (name, email, phone, address)
2. If `--deep`: Full OSINT recon (username search, Google dorks, social media)
3. Default: Broker scan + breach check
4. Show real-time progress as scanners run
5. Generate and display exposure report with:
   - Risk score (0-100)
   - Findings grouped by source
   - Critical items highlighted
   - Recommended actions
6. Offer to start removal workflow (`/vanish`)

---

## Skill: /breach

**Purpose**: Check for credential exposure in data breaches
**Trigger**: `/breach [EMAIL|PHONE|USERNAME]`

**Behavior**:
1. Query HIBP for email breaches
2. Query DeHashed for comprehensive search
3. Show results:
   - Breach name, date, data types exposed
   - Severity rating
   - Whether passwords were exposed (plaintext vs hash)
4. For each breach with password exposure:
   - Identify affected services
   - Recommend password changes
   - Check for credential reuse risk
5. Store results and compare with previous checks

---

## Skill: /privacy-audit

**Purpose**: Audit social media and online account privacy settings
**Trigger**: `/privacy-audit [--platform NAME]`

**Behavior**:
1. Review known accounts from OSINT data
2. For each platform:
   - Check profile visibility (public/private)
   - Identify exposed personal information
   - Check for location data in posts
   - Detect friend/follower list visibility
   - Identify username patterns (reuse risk)
3. Generate privacy recommendations per platform
4. Check for impersonation accounts (similar usernames)
5. Score overall social media privacy posture

---

## Skill Registration

Skills are defined in `.claude/skills/` and registered via the skill system. Each skill invokes the `digital-footprint-mcp` tools and may spawn agents for long-running operations.

```
.claude/skills/
  footprint.md
  vanish.md
  exposure.md
  breach.md
  privacy-audit.md
```
