# Broker Registry Specification

## Format

Each data broker is defined as a YAML file in `brokers/` directory. Filename: `<broker-slug>.yaml`

## Schema

```yaml
# Required fields
name: string           # Human-readable broker name
url: string            # Primary website URL
category: enum         # See categories below

# Opt-out configuration
opt_out:
  method: enum         # web_form | email | api | phone | mail
  url: string          # Opt-out page URL (for web_form)
  email: string        # Privacy/opt-out email (for email method)
  api_endpoint: string # API URL (for api method)
  phone: string        # Phone number (for phone method)
  mail_address: string # Mailing address (for mail method)

  # Step-by-step instructions (human-readable)
  steps:
    - string

  # Automation flags
  captcha: boolean           # Requires CAPTCHA solving
  email_verification: boolean # Requires email confirmation click
  phone_verification: boolean # Requires phone call/SMS
  identity_verification: boolean # Requires ID upload
  time_to_removal: string    # Expected removal time

# Automation
automatable: boolean        # Can be fully automated
playwright_script: string   # Filename in removers/ directory
difficulty: enum            # easy | medium | hard | manual

# Monitoring
recheck_days: integer       # Days between re-checks (default: 30)
relisting_frequency: enum   # never | rare | occasional | frequent

# Search configuration
search:
  url_pattern: string       # URL pattern for searching (e.g., "https://spokeo.com/search?q={name}")
  selectors:                # CSS selectors for result parsing
    results: string
    name: string
    address: string
    phone: string
    profile_link: string

# Metadata
parent_company: string      # Parent company (for related brokers)
related_brokers: [string]   # Slug names of related brokers
jurisdiction: string        # Primary jurisdiction (US, EU, etc.)
ccpa_compliant: boolean     # Responds to CCPA requests
gdpr_compliant: boolean     # Responds to GDPR requests
notes: string               # Free-form notes
```

## Categories

| Category | Description | Examples |
|----------|-------------|---------|
| `people_search` | People finder / search sites | Spokeo, BeenVerified, WhitePages |
| `background_check` | Background check services | InstantCheckmate, TruthFinder |
| `public_records` | Public records aggregators | LexisNexis, Acxiom |
| `marketing` | Marketing data brokers | Oracle Data Cloud, Epsilon |
| `social_aggregator` | Social media aggregators | Social Catfish, PimEyes |
| `property` | Property/real estate data | Zillow, Redfin |
| `financial` | Financial data brokers | Equifax, Experian |
| `genealogy` | Family/genealogy sites | Ancestry, FamilyTreeNow |
| `reverse_lookup` | Phone/address lookup | AnyWho, USPhoneBook |
| `image_search` | Reverse image/facial search | PimEyes, FaceCheck.id |

## Example: Spokeo

```yaml
name: Spokeo
url: https://www.spokeo.com
category: people_search

opt_out:
  method: web_form
  url: https://www.spokeo.com/optout
  steps:
    - Search for your profile on spokeo.com
    - Copy the full URL of your profile
    - Navigate to spokeo.com/optout
    - Paste the profile URL into the form
    - Enter your email address
    - Complete the CAPTCHA
    - Click submit
    - Check email for confirmation link
    - Click the confirmation link
  captcha: true
  email_verification: true
  phone_verification: false
  identity_verification: false
  time_to_removal: "24-72 hours"

automatable: true
playwright_script: spokeo_optout.py
difficulty: easy

recheck_days: 30
relisting_frequency: occasional

search:
  url_pattern: "https://www.spokeo.com/{first_name}-{last_name}/{state}"
  selectors:
    results: ".search-results .result-card"
    name: ".result-name"
    address: ".result-location"
    phone: ".result-phone"
    profile_link: "a.result-link"

parent_company: Spokeo Inc.
related_brokers: []
jurisdiction: US
ccpa_compliant: true
gdpr_compliant: false
notes: "Data may remain visible to paid subscribers even after opt-out. Multiple profiles may exist for same person — check name variations."
```

## Sourcing Broker Data

Primary references for populating the registry:
1. **Big-Ass Data Broker Opt-Out List** — github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List
2. **CA Data Broker Registry** — privacy.ca.gov/data-brokers (500+ registered brokers)
3. **Privacy Rights Clearinghouse** — privacyrights.org/data-brokers
4. **Incogni opt-out guides** — blog.incogni.com/opt-out-guides (85+ guides)
5. **OneRep opt-out guides** — onerep.com/blog (detailed per-broker instructions)
