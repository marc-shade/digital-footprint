# External API Integrations

## 1. Have I Been Pwned (HIBP)

**Purpose**: Email breach detection
**Documentation**: https://haveibeenpwned.com/API/v3
**Auth**: API key (hibp-api-key header)
**Cost**: $3.50/month

**Endpoints Used**:
```
GET /api/v3/breachedaccount/{email}
  → List of breaches for an email address
  → Returns: breach name, date, data types, description

GET /api/v3/pasteaccount/{email}
  → Pastes containing the email
  → Returns: paste source, title, date

GET /api/v3/breach/{name}
  → Details of a specific breach
  → Returns: full breach metadata

POST /api/v3/range/{hashPrefix}
  → k-Anonymity password check
  → Send first 5 chars of SHA-1 hash, get matching suffixes
```

**Rate Limits**: 10 requests per minute (with API key)
**Implementation**: Simple REST client with retry and caching

---

## 2. DeHashed

**Purpose**: Deep breach record search (email, phone, name, username, IP, address)
**Documentation**: https://www.dehashed.com/docs
**Auth**: API key + email (Basic auth)
**Cost**: ~$5/month

**Endpoints Used**:
```
GET /search?query={field}:{value}
  Fields: email, username, ip_address, name, address, phone, vin, password
  → Returns: matching breach records with full data

  Example: /search?query=email:marc@example.com
  → Returns records with plaintext/hashed passwords, breach source
```

**Rate Limits**: Varies by plan
**Value**: Returns actual breach records (not just breach names), including passwords

---

## 3. Breachsense (Optional)

**Purpose**: Dark web monitoring, infostealer logs, ransomware data
**Documentation**: https://www.breachsense.com/dark-web-api/
**Auth**: API key
**Cost**: Enterprise pricing (evaluate need)

**Endpoints Used**:
```
GET /api/v1/search
  → Search by email, domain, phone, username
  → Returns: dark web marketplace findings, infostealer logs, session tokens

GET /api/v1/monitor
  → Set up continuous monitoring for identifiers
  → Webhook alerts on new findings
```

**Value**: Covers dark web sources that HIBP and DeHashed miss

---

## 4. California DROP API (Available Aug 2026)

**Purpose**: Batch data broker deletion for CA residents
**Documentation**: https://cppa.ca.gov/regulations/drop.html
**Auth**: Consumer account (free)
**Cost**: Free

**Process**:
```
1. Create consumer account on DROP portal
2. Submit deletion request (hashed identifiers)
3. Request propagates to ALL registered data brokers (500+)
4. Brokers must process within 45 days
5. Check status via portal/API
```

**Note**: API integration opens Spring 2026. Single most impactful integration for CA residents — covers 500+ brokers in one request.

---

## 5. 2Captcha / Anti-Captcha

**Purpose**: Solve CAPTCHAs on broker opt-out forms
**Documentation**: https://2captcha.com/api-docs
**Auth**: API key
**Cost**: ~$3 per 1000 CAPTCHAs

**Supported Types**:
```
- reCAPTCHA v2 (most common on broker sites)
- reCAPTCHA v3
- hCaptcha
- Image CAPTCHAs
- FunCaptcha
```

**Integration**:
```python
# Submit CAPTCHA
POST /in.php
  → Returns: task ID

# Get solution
GET /res.php?id={task_id}
  → Returns: CAPTCHA solution token

# Inject into Playwright
await page.evaluate(f"document.getElementById('g-recaptcha-response').value = '{token}'")
```

---

## 6. Maigret (Local Tool)

**Purpose**: Username search across 3,000+ sites
**Installation**: `pip install maigret`
**Auth**: None (runs locally)
**Cost**: Free

**Usage**:
```bash
maigret username --json output.json
maigret username --html report.html
maigret username --pdf report.pdf
```

**Programmatic**:
```python
import maigret
# Use maigret's internal API for integration
```

---

## 7. Sherlock (Local Tool)

**Purpose**: Username search across 400+ sites
**Installation**: `pip install sherlock-project`
**Auth**: None
**Cost**: Free

**Usage**:
```bash
sherlock username --output results.txt --csv
```

---

## 8. holehe (Local Tool)

**Purpose**: Check if email is registered on various services
**Installation**: `pip install holehe`
**Auth**: None
**Cost**: Free

**Usage**:
```bash
holehe email@example.com
```

**Returns**: List of services where the email is registered (with rate limiting)

---

## 9. SpiderFoot (Local Tool)

**Purpose**: Comprehensive OSINT automation framework
**Installation**: `pip install spiderfoot`
**Auth**: None (optional API keys for premium sources)
**Cost**: Free (open source)

**Modules Used**:
- Email breach checks
- DNS/domain enumeration
- Social media discovery
- Dark web search
- Public records

---

## 10. SMTP (Email Sending)

**Purpose**: Send CCPA/GDPR deletion request emails
**Configuration**: Any SMTP provider

**Recommended Setup**:
```yaml
smtp:
  host: smtp.gmail.com  # or dedicated email service
  port: 587
  use_tls: true
  username: privacy-requests@yourdomain.com
  password: ${SMTP_PASSWORD}
  from_name: "Privacy Request"
  from_email: privacy-requests@yourdomain.com
```

**Note**: Use a dedicated email address for removal requests to:
- Track responses
- Monitor confirmation emails
- Keep personal email clean
- Enable IMAP monitoring for auto-confirmation

---

## 11. IMAP (Email Monitoring)

**Purpose**: Monitor for broker confirmation emails and click confirmation links
**Configuration**: Same account as SMTP

**Process**:
```python
# Monitor inbox for confirmation emails
# Pattern match subject lines for broker names
# Extract confirmation links
# Visit links via Playwright to confirm removal
# Mark email as processed
```

---

## API Key Management

All API keys stored in `.env` file (never committed):

```env
HIBP_API_KEY=your_key_here
DEHASHED_API_KEY=your_key_here
DEHASHED_EMAIL=your_email_here
BREACHSENSE_API_KEY=your_key_here
CAPTCHA_API_KEY=your_2captcha_key
SMTP_PASSWORD=your_smtp_password
IMAP_PASSWORD=your_imap_password
```

Loaded via `python-dotenv` and accessed through config module.
