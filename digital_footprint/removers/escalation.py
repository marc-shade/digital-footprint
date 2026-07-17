"""Escalation for removals a broker has ignored.

Two rendered artifacts:
  * followup email  (followup.j2)          -- a formal second-request email
  * regulatory complaint (regulatory_complaint.j2) -- an FTC / state-AG filing

The complaint is WRITTEN to a local file, not auto-submitted anywhere: filing
with a regulator is a deliberate human act (it names you, under penalty of
perjury on some portals). The pipeline/scheduler generate the draft and record
that it was generated; the human files it. This is the honest boundary the
LinkedIn post's Prompt 4 implies ("a complaint drafted to the FTC or my state
AG").
"""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"

# A removal is escalation-eligible once it has been requested this many times
# and the person is still listed. Matches the post's "ignores 2+ requests".
ESCALATION_ATTEMPT_THRESHOLD = 2


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def _normalize_person(person: dict) -> dict:
    p = dict(person)
    p.setdefault("state", "")
    if "email" not in p and "emails" in p:
        emails = p["emails"]
        p["email"] = emails[0] if emails else ""
    return p


def render_followup(
    person: dict,
    broker: dict,
    reference_id: str,
    original_date: str,
    days_elapsed: int,
) -> tuple[str, str]:
    """Render the follow-up (second-request) email. Returns (subject, body)."""
    person = _normalize_person(person)
    template = _env().get_template("followup.j2")
    rendered = template.render(
        person=person,
        broker=broker,
        reference_id=reference_id,
        original_date=original_date,
        days_elapsed=days_elapsed,
        date=datetime.now().strftime("%Y-%m-%d"),
    )
    lines = rendered.strip().split("\n")
    subject = lines[0].replace("Subject: ", "").strip()
    body = "\n".join(lines[1:]).strip()
    return subject, body


def render_complaint(
    person: dict,
    broker: dict,
    reference_id: str,
    attempts: int,
    first_request_date: str,
    last_checked: str,
) -> str:
    """Render the regulatory (FTC / state-AG) complaint text."""
    person = _normalize_person(person)
    template = _env().get_template("regulatory_complaint.j2")
    return template.render(
        person=person,
        broker=broker,
        reference_id=reference_id,
        attempts=attempts,
        first_request_date=first_request_date,
        last_checked=last_checked,
        filed_date=datetime.now().strftime("%Y-%m-%d"),
    )


def generate_complaint_file(
    person: dict,
    broker: dict,
    reference_id: str,
    attempts: int,
    first_request_date: str,
    last_checked: str,
    complaints_dir: Path,
) -> Path:
    """Render the complaint and write it to complaints_dir. Returns the path.

    The file is a DRAFT for the human to file; nothing is submitted to any
    regulator by this code.
    """
    complaints_dir = Path(complaints_dir)
    complaints_dir.mkdir(parents=True, exist_ok=True)
    text = render_complaint(
        person=person,
        broker=broker,
        reference_id=reference_id,
        attempts=attempts,
        first_request_date=first_request_date,
        last_checked=last_checked,
    )
    slug = (broker.get("slug") or broker.get("name") or "broker").lower().replace(" ", "-")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = complaints_dir / f"complaint-{slug}-{stamp}.txt"
    path.write_text(text)
    return path
