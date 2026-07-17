"""Email confirmation loop for broker opt-outs (P0-3).

Many brokers email a "click to confirm your removal" link; without clicking it
the opt-out never completes. This module polls the confirmation inbox over
IMAP, matches each message to a pending removal, extracts the confirmation
link, and (when enabled) visits it to complete the removal.

Design: the pure logic (parse / extract / match) is separated from I/O (IMAP
fetch, link visit) so it is fully unit-testable and the I/O is injectable.

Security (non-negotiable): a link is only visited if it is on the BROKER'S OWN
registered domain. The monitor never clicks arbitrary URLs from email, so a
spam/phishing message sitting in the inbox cannot turn it into a click bot.
"""

import email
import imaplib
import logging
import re
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from html import unescape
from typing import Callable, Optional
from urllib.parse import urlparse

logger = logging.getLogger("digital_footprint.confirmation")

CONFIRM_KEYWORDS = (
    "confirm", "verify", "verification", "optout", "opt-out", "opt_out",
    "removal", "remove", "suppress", "activate", "validate", "unsubscribe",
)

_HREF_RE = re.compile(r'href=["\']?(https?://[^"\'>\s]+)', re.IGNORECASE)
_URL_RE = re.compile(r'https?://[^\s"\'<>)\]]+', re.IGNORECASE)


def registrable_domain(host_or_url: str) -> str:
    """Best-effort registrable domain (last two labels) from either a bare
    host or a full URL. Good enough to keep link-clicking on the broker's own
    site without a public-suffix-list dependency."""
    s = (host_or_url or "").strip().lower()
    if "://" in s:
        s = urlparse(s).netloc
    s = s.split("/")[0].split(":")[0]  # strip any path / port
    if s.startswith("www."):
        s = s[4:]
    parts = [p for p in s.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    return ".".join(parts[-2:])


def domain_of_url(url: str) -> str:
    try:
        return registrable_domain(urlparse(url).netloc)
    except Exception:
        return ""


def same_site(url: str, broker_domain: str) -> bool:
    d = domain_of_url(url)
    bd = registrable_domain(broker_domain)
    return bool(d) and bool(bd) and d == bd


def parse_email(raw: bytes) -> dict:
    """Parse a raw RFC822 message into {from, from_domain, subject, body}."""
    msg = email.message_from_bytes(raw)
    from_hdr = str(make_header(decode_header(msg.get("From", ""))))
    subject = str(make_header(decode_header(msg.get("Subject", ""))))
    m = re.search(r"[\w.+-]+@([\w.-]+)", from_hdr)
    from_domain = registrable_domain(m.group(1)) if m else ""

    body = ""
    if msg.is_multipart():
        # prefer html (links live there), fall back to plain text
        html_part = text_part = None
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and html_part is None:
                html_part = part
            elif ctype == "text/plain" and text_part is None:
                text_part = part
        # prefer html, but fall back to text if the html part is empty
        body = _decode_part(html_part) if html_part is not None else ""
        if not body.strip() and text_part is not None:
            body = _decode_part(text_part)
    else:
        body = _decode_part(msg)

    return {"from": from_hdr, "from_domain": from_domain, "subject": subject, "body": body}


def _decode_part(part) -> str:
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except Exception:
        return ""


def extract_confirmation_links(body: str, broker_domain: str) -> list[str]:
    """Return broker-domain links from an email body, confirm-looking ones
    first. Only same-site links are ever returned (security)."""
    if not body:
        return []
    candidates = []
    seen = set()
    for match in list(_HREF_RE.finditer(body)) + list(_URL_RE.finditer(body)):
        url = unescape(match.group(1) if match.re is _HREF_RE else match.group(0)).rstrip(".,;)")
        if url in seen:
            continue
        seen.add(url)
        if same_site(url, broker_domain):
            candidates.append(url)

    def looks_confirmy(u: str) -> bool:
        low = u.lower()
        return any(k in low for k in CONFIRM_KEYWORDS)

    keyworded = [u for u in candidates if looks_confirmy(u)]
    others = [u for u in candidates if not looks_confirmy(u)]
    return keyworded + others


def match_email_to_removal(msg: dict, removals: list[dict]) -> Optional[dict]:
    """Match a parsed email to a pending removal.

    Strongest signal first: a reference id in the body, then the broker's own
    sending domain, then the person's email appearing in the body.
    """
    body_low = (msg.get("body") or "").lower()
    subj_low = (msg.get("subject") or "").lower()
    from_domain = msg.get("from_domain") or ""

    # 1. reference id (e.g. REF-ABC123) present in body/subject
    for r in removals:
        ref = (r.get("reference_id") or r.get("notes") or "").strip().lower()
        if ref and (ref in body_low or ref in subj_low):
            return r

    # 2. sender domain matches the broker's registrable domain
    for r in removals:
        bd = registrable_domain(r.get("broker_domain") or r.get("broker_url") or "")
        if bd and from_domain == bd:
            return r

    # 3. one of the person's emails appears in the body
    for r in removals:
        for addr in (r.get("person_emails") or []):
            if addr and addr.lower() in body_low:
                return r
    return None


# --- I/O layer (injectable) ---

class ImapFetcher:
    """Thin IMAP4-SSL fetch of recent messages. Kept minimal on purpose; the
    parsing/matching logic that needs testing lives in the pure functions."""

    def __init__(self, host: str, user: str, password: str, port: int = 993, mailbox: str = "INBOX"):
        self.host, self.user, self.password, self.port, self.mailbox = host, user, password, port, mailbox

    def fetch_recent(self, limit: int = 50, unseen_only: bool = True) -> list[bytes]:
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            conn.login(self.user, self.password)
            conn.select(self.mailbox)
            criterion = "UNSEEN" if unseen_only else "ALL"
            typ, data = conn.search(None, criterion)
            if typ != "OK" or not data or not data[0]:
                return []
            ids = data[0].split()[-limit:]
            out = []
            for msg_id in ids:
                typ, msg_data = conn.fetch(msg_id, "(RFC822)")
                if typ == "OK" and msg_data and msg_data[0]:
                    out.append(msg_data[0][1])
            return out
        finally:
            try:
                conn.logout()
            except Exception as e:
                logger.debug("IMAP logout failed: %s", e)


def httpx_link_visitor(url: str) -> bool:
    """Visit a confirmation link with a plain GET. Returns True on 2xx.

    A simple GET completes one-click confirm links without executing JS. The
    caller has already restricted the URL to the broker's own domain.
    """
    import httpx
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30)
        return 200 <= resp.status_code < 300
    except Exception as e:
        logger.warning("confirmation link visit failed for %s: %s", url, e)
        return False


@dataclass
class ConfirmationResult:
    processed: int = 0
    matched: int = 0
    confirmed: int = 0
    links_recorded: int = 0
    unmatched: int = 0
    details: list = field(default_factory=list)


class ConfirmationProcessor:
    """Match confirmation emails to pending removals and, when auto_confirm is
    on, visit the (broker-domain-only) confirmation link and mark the removal
    confirmed. When off, the link is recorded on the removal for a human click.
    """

    def __init__(self, auto_confirm: bool = False,
                 link_visitor: Callable[[str], bool] = httpx_link_visitor):
        self.auto_confirm = auto_confirm
        self.link_visitor = link_visitor

    def process(self, db, raw_messages: list[bytes], removals: list[dict], now: str) -> ConfirmationResult:
        res = ConfirmationResult()
        for raw in raw_messages:
            res.processed += 1
            try:
                msg = parse_email(raw)
            except Exception as e:
                logger.warning("failed to parse a confirmation email: %s", e)
                continue

            removal = match_email_to_removal(msg, removals)
            if not removal:
                res.unmatched += 1
                continue
            res.matched += 1

            broker_domain = removal.get("broker_domain") or removal.get("broker_url") or ""
            links = extract_confirmation_links(msg["body"], broker_domain)
            if not links:
                res.details.append({"removal_id": removal["id"], "status": "matched_no_link"})
                continue

            link = links[0]
            if not self.auto_confirm:
                db.update_removal(removal["id"], notes=f"confirm_link: {link}", last_checked_at=now)
                res.links_recorded += 1
                res.details.append({"removal_id": removal["id"], "status": "link_recorded", "link": link})
                continue

            # security backstop: never visit a non-broker-domain link
            if not same_site(link, broker_domain):
                res.details.append({"removal_id": removal["id"], "status": "link_rejected_offsite", "link": link})
                continue

            if self.link_visitor(link):
                db.update_removal(removal["id"], status="confirmed", confirmed_at=now, last_checked_at=now)
                res.confirmed += 1
                res.details.append({"removal_id": removal["id"], "status": "confirmed", "link": link})
            else:
                db.update_removal(removal["id"], last_checked_at=now, notes=f"confirm_link_failed: {link}")
                res.details.append({"removal_id": removal["id"], "status": "visit_failed", "link": link})
        return res
