# Legal Templates Specification

## Template Engine
Jinja2 templates with person-specific variables injected at send time.

## Variables Available in All Templates

```
{{ person.name }}           - Full legal name
{{ person.email }}          - Primary email address
{{ person.phone }}          - Phone number (if provided)
{{ person.address }}        - Physical address (if provided)
{{ person.state }}          - State of residence
{{ broker.name }}           - Data broker name
{{ broker.url }}            - Broker website
{{ broker.opt_out_email }}  - Broker's privacy contact
{{ date }}                  - Current date
{{ reference_id }}          - Unique request tracking ID
```

## Template 1: CCPA Deletion Request

**File**: `templates/ccpa_deletion.j2`
**Use**: California residents requesting deletion under CCPA/CPRA

```
Subject: CCPA Data Deletion Request - {{ person.name }} [Ref: {{ reference_id }}]

To the Privacy Team at {{ broker.name }},

I am a California resident and I am exercising my right to deletion of my personal
information under the California Consumer Privacy Act (CCPA), Cal. Civ. Code
Section 1798.105.

I request that {{ broker.name }} delete all personal information you have collected
about me. My identifying information is as follows:

Full Name: {{ person.name }}
Email Address: {{ person.email }}
{% if person.phone %}Phone Number: {{ person.phone }}{% endif %}
{% if person.address %}Address: {{ person.address }}{% endif %}

Under the CCPA, you are required to:
1. Delete my personal information from your records
2. Direct any service providers to delete my personal information
3. Confirm completion of this deletion within 45 days

If you cannot verify my identity through the information provided above, please
contact me at {{ person.email }} to discuss additional verification steps.

Please confirm deletion to this email address. I am tracking this request under
reference ID {{ reference_id }}.

If this request is not fulfilled within 45 calendar days, I will file a complaint
with the California Attorney General's office.

Sincerely,
{{ person.name }}
{{ person.email }}
{{ date }}
```

## Template 2: CCPA Do-Not-Sell Request

**File**: `templates/ccpa_do_not_sell.j2`
**Use**: Opt-out of data sale under CCPA

```
Subject: CCPA Do Not Sell My Personal Information - {{ person.name }} [Ref: {{ reference_id }}]

To the Privacy Team at {{ broker.name }},

I am exercising my right under the California Consumer Privacy Act (CCPA),
Cal. Civ. Code Section 1798.120, to opt out of the sale or sharing of my
personal information.

I direct {{ broker.name }} to:
1. Stop selling my personal information to third parties immediately
2. Stop sharing my personal information for cross-context behavioral advertising
3. Remove my existing listings and profiles from your platform

My identifying information:

Full Name: {{ person.name }}
Email Address: {{ person.email }}
{% if person.phone %}Phone Number: {{ person.phone }}{% endif %}
{% if person.address %}Address: {{ person.address }}{% endif %}

Please confirm this opt-out within 15 business days per CCPA requirements.

Reference ID: {{ reference_id }}

Sincerely,
{{ person.name }}
{{ date }}
```

## Template 3: GDPR Erasure Request (Article 17)

**File**: `templates/gdpr_erasure.j2`
**Use**: EU/UK residents or any broker with GDPR compliance

```
Subject: GDPR Right to Erasure Request - {{ person.name }} [Ref: {{ reference_id }}]

To the Data Protection Officer at {{ broker.name }},

I am writing to exercise my right to erasure (right to be forgotten) under
Article 17 of the General Data Protection Regulation (GDPR).

I request that you erase all personal data you hold about me without undue delay.
This includes but is not limited to: name, address, phone number, email, employment
information, family relationships, and any derived or aggregated data.

My identifying information:

Full Name: {{ person.name }}
Email Address: {{ person.email }}
{% if person.phone %}Phone Number: {{ person.phone }}{% endif %}

Under GDPR Article 17, you must respond within one month (30 days). If you require
additional information to verify my identity, please contact me promptly.

Reference ID: {{ reference_id }}

Regards,
{{ person.name }}
{{ date }}
```

## Template 4: Follow-Up / Escalation

**File**: `templates/followup.j2`
**Use**: When initial request has not been answered within the legal timeframe

```
Subject: FOLLOW-UP: Data Deletion Request - {{ person.name }} [Ref: {{ reference_id }}]

To the Privacy Team at {{ broker.name }},

On {{ original_date }}, I submitted a data deletion request (Reference:
{{ reference_id }}). More than {{ days_elapsed }} days have passed and I have
not received confirmation that my data has been deleted.

Under applicable privacy law{% if person.state == 'California' %} (CCPA, Cal. Civ.
Code Section 1798.105){% endif %}, you are required to respond to deletion requests
within 45 calendar days.

This is a formal follow-up. If I do not receive confirmation of deletion within
10 business days of this message, I will:

1. File a complaint with the {% if person.state == 'California' %}California Attorney
General{% else %}relevant state attorney general{% endif %}
2. File a complaint with the FTC
3. Document this non-compliance for potential legal action

Original request details:
- Date submitted: {{ original_date }}
- Reference ID: {{ reference_id }}
- Requested action: Deletion of all personal information

Full Name: {{ person.name }}
Email: {{ person.email }}

Sincerely,
{{ person.name }}
{{ date }}
```

## Template 5: Generic Privacy Removal

**File**: `templates/generic_removal.j2`
**Use**: Brokers without specific CCPA/GDPR obligations

```
Subject: Personal Information Removal Request - {{ person.name }}

To Whom It May Concern at {{ broker.name }},

I am writing to request the removal of my personal information from your website
and databases.

I have found that {{ broker.name }} ({{ broker.url }}) displays my personal
information without my consent. I request that you:

1. Remove all listings and profiles containing my personal information
2. Remove my data from your databases
3. Ensure my information is not re-added in the future

My information to be removed:

Full Name: {{ person.name }}
Email: {{ person.email }}
{% if person.phone %}Phone: {{ person.phone }}{% endif %}
{% if person.address %}Address: {{ person.address }}{% endif %}

Please confirm removal within 30 days.

Thank you,
{{ person.name }}
{{ date }}
```
