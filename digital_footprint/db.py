"""SQLite database manager for Digital Footprint."""

import hashlib
import json
import logging
import os
import stat
import sqlite3
from pathlib import Path
from typing import Optional

from digital_footprint.config import Config
from digital_footprint.crypto import Cipher, resolve_key
from digital_footprint.models import Person, Broker

logger = logging.getLogger("digital_footprint.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'self',
    emails TEXT DEFAULT '[]',
    phones TEXT DEFAULT '[]',
    addresses TEXT DEFAULT '[]',
    usernames TEXT DEFAULT '[]',
    date_of_birth TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS brokers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    opt_out_method TEXT,
    opt_out_url TEXT,
    opt_out_email TEXT,
    search_url_pattern TEXT,
    difficulty TEXT DEFAULT 'medium',
    automatable INTEGER DEFAULT 0,
    recheck_days INTEGER DEFAULT 30,
    ccpa_compliant INTEGER DEFAULT 0,
    gdpr_compliant INTEGER DEFAULT 0,
    notes TEXT,
    yaml_hash TEXT,
    loaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    broker_id INTEGER REFERENCES brokers(id),
    source TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    data_found TEXT DEFAULT '{}',
    risk_level TEXT DEFAULT 'medium',
    url TEXT,
    -- Deterministic hash of (source, broker_id, url) used for de-dup. url is
    -- PII (broker search URLs embed the person's name) and is encrypted, so a
    -- direct url comparison can't de-dup; this non-reversible hash can.
    content_hash TEXT,
    screenshot_path TEXT,
    status TEXT DEFAULT 'active',
    discovered_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS removals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id),
    person_id INTEGER NOT NULL REFERENCES persons(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    method TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    submitted_at TEXT,
    confirmed_at TEXT,
    last_checked_at TEXT,
    attempts INTEGER DEFAULT 0,
    next_check_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS breaches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    breach_name TEXT NOT NULL,
    breach_date TEXT,
    data_types TEXT DEFAULT '[]',
    source TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    discovered_at TEXT DEFAULT (datetime('now')),
    action_taken TEXT
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES persons(id),
    scan_type TEXT NOT NULL,
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    findings_count INTEGER DEFAULT 0,
    new_findings INTEGER DEFAULT 0,
    removed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_findings_person ON findings(person_id);
CREATE INDEX IF NOT EXISTS idx_findings_broker ON findings(broker_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_removals_status ON removals(status);
CREATE INDEX IF NOT EXISTS idx_removals_person ON removals(person_id);
CREATE INDEX IF NOT EXISTS idx_breaches_person ON breaches(person_id);
CREATE INDEX IF NOT EXISTS idx_brokers_slug ON brokers(slug);

CREATE TABLE IF NOT EXISTS scheduled_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    details TEXT DEFAULT '{}',
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_scheduled_runs_job ON scheduled_runs(job_name);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    breaches_found INTEGER DEFAULT 0,
    dark_web_findings INTEGER DEFAULT 0,
    accounts_found INTEGER DEFAULT 0,
    removals_submitted INTEGER DEFAULT 0,
    risk_score INTEGER DEFAULT 0,
    report_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_person ON pipeline_runs(person_id);
"""


class Database:
    def __init__(self, config: Config):
        self.config = config
        self.conn: Optional[sqlite3.Connection] = None
        self.cipher: Optional[Cipher] = None

    def initialize(self) -> None:
        is_file_db = str(self.config.db_path) not in (":memory:", "")
        if is_file_db:
            self.config.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Resolve the PII encryption key (env key > key file when enabled).
        key = resolve_key(self.config.encrypt, self.config.resolved_key_path() if is_file_db else self.config.key_path)
        self.cipher = Cipher(key) if key else None
        if self.cipher is None:
            # Fail loud: a privacy tool storing PII in plaintext should say so.
            logger.warning(
                "PII encryption at rest is OFF — %s stores personal data in "
                "plaintext. Enable with DIGITAL_FOOTPRINT_ENCRYPT=1 (or set "
                "DIGITAL_FOOTPRINT_DB_KEY).", self.config.db_path,
            )

        self.conn = sqlite3.connect(str(self.config.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate_schema()
        self.conn.commit()

        # Restrict the DB file (and WAL/SHM siblings) to owner-only.
        if is_file_db:
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(self.config.db_path) + suffix)
                if p.exists():
                    try:
                        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
                    except OSError as e:
                        # Best-effort hardening (some filesystems reject chmod);
                        # surface it rather than swallow it silently.
                        logger.warning("could not chmod 600 %s: %s", p, e)

    def _migrate_schema(self) -> None:
        """Additive migrations for DBs created before a column existed.

        CREATE TABLE IF NOT EXISTS never alters an existing table, so columns
        added to the schema over time must be back-filled here or an older DB
        raises 'no such column' at runtime.
        """
        finding_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(findings)")}
        if "content_hash" not in finding_cols:
            self.conn.execute("ALTER TABLE findings ADD COLUMN content_hash TEXT")
        broker_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(brokers)")}
        if "search_url_pattern" not in broker_cols:
            self.conn.execute("ALTER TABLE brokers ADD COLUMN search_url_pattern TEXT")

    # --- PII field encryption helpers ---

    def _enc(self, value: Optional[str]) -> Optional[str]:
        return self.cipher.encrypt(value) if self.cipher else value

    def _dec(self, value: Optional[str]) -> Optional[str]:
        return self.cipher.decrypt(value) if self.cipher else value

    @staticmethod
    def _content_hash(source: str, broker_id, url: Optional[str]) -> str:
        raw = f"{source}|{broker_id if broker_id is not None else ''}|{url or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    # --- Person operations ---

    def insert_person(
        self,
        name: str,
        emails: Optional[list[str]] = None,
        phones: Optional[list[str]] = None,
        addresses: Optional[list[str]] = None,
        usernames: Optional[list[str]] = None,
        relation: str = "self",
        date_of_birth: Optional[str] = None,
    ) -> int:
        cursor = self.conn.execute(
            "INSERT INTO persons (name, relation, emails, phones, addresses, usernames, date_of_birth) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self._enc(name),
                relation,
                self._enc(json.dumps(emails or [])),
                self._enc(json.dumps(phones or [])),
                self._enc(json.dumps(addresses or [])),
                self._enc(json.dumps(usernames or [])),
                self._enc(date_of_birth),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_person(self, person_id: int) -> Optional[Person]:
        row = self.conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        if not row:
            return None
        return self._row_to_person(row)

    def list_persons(self) -> list[Person]:
        rows = self.conn.execute("SELECT * FROM persons ORDER BY id").fetchall()
        return [self._row_to_person(r) for r in rows]

    def update_person(self, person_id: int, **kwargs) -> None:
        json_pii_fields = {"emails", "phones", "addresses", "usernames"}
        scalar_pii_fields = {"name", "date_of_birth"}
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            if key in json_pii_fields:
                values.append(self._enc(json.dumps(value)))
            elif key in scalar_pii_fields:
                values.append(self._enc(value))
            else:
                values.append(value)
        sets.append("updated_at = datetime('now')")
        values.append(person_id)
        self.conn.execute(f"UPDATE persons SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def _row_to_person(self, row: sqlite3.Row) -> Person:
        return Person(
            id=row["id"],
            name=self._dec(row["name"]),
            relation=row["relation"],
            emails=json.loads(self._dec(row["emails"]) or "[]"),
            phones=json.loads(self._dec(row["phones"]) or "[]"),
            addresses=json.loads(self._dec(row["addresses"]) or "[]"),
            usernames=json.loads(self._dec(row["usernames"]) or "[]"),
            date_of_birth=self._dec(row["date_of_birth"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- Broker operations ---

    def insert_broker(self, broker: Broker) -> int:
        cursor = self.conn.execute(
            """INSERT OR REPLACE INTO brokers
            (slug, name, url, category, opt_out_method, opt_out_url, opt_out_email,
             search_url_pattern, difficulty, automatable, recheck_days,
             ccpa_compliant, gdpr_compliant, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                broker.slug, broker.name, broker.url, broker.category,
                broker.opt_out_method, broker.opt_out_url, broker.opt_out_email,
                broker.search_url_pattern,
                broker.difficulty, int(broker.automatable), broker.recheck_days,
                int(broker.ccpa_compliant), int(broker.gdpr_compliant), broker.notes,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_broker_by_slug(self, slug: str) -> Optional[Broker]:
        row = self.conn.execute("SELECT * FROM brokers WHERE slug = ?", (slug,)).fetchone()
        if not row:
            return None
        return self._row_to_broker(row)

    def list_brokers(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        automatable: Optional[bool] = None,
    ) -> list[Broker]:
        query = "SELECT * FROM brokers WHERE 1=1"
        params: list = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        if automatable is not None:
            query += " AND automatable = ?"
            params.append(int(automatable))
        query += " ORDER BY name"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_broker(r) for r in rows]

    def broker_stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM brokers").fetchone()[0]
        by_category = {}
        for row in self.conn.execute("SELECT category, COUNT(*) FROM brokers GROUP BY category"):
            by_category[row[0]] = row[1]
        by_difficulty = {}
        for row in self.conn.execute("SELECT difficulty, COUNT(*) FROM brokers GROUP BY difficulty"):
            by_difficulty[row[0]] = row[1]
        automatable = self.conn.execute("SELECT COUNT(*) FROM brokers WHERE automatable = 1").fetchone()[0]
        by_method = {}
        for row in self.conn.execute("SELECT opt_out_method, COUNT(*) FROM brokers WHERE opt_out_method IS NOT NULL GROUP BY opt_out_method"):
            by_method[row[0]] = row[1]
        return {
            "total": total,
            "by_category": by_category,
            "by_difficulty": by_difficulty,
            "by_method": by_method,
            "automatable": automatable,
        }

    def _row_to_broker(self, row: sqlite3.Row) -> Broker:
        return Broker(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            url=row["url"],
            category=row["category"],
            opt_out_method=row["opt_out_method"],
            opt_out_url=row["opt_out_url"],
            opt_out_email=row["opt_out_email"],
            search_url_pattern=row["search_url_pattern"] if "search_url_pattern" in row.keys() else None,
            difficulty=row["difficulty"],
            automatable=bool(row["automatable"]),
            recheck_days=row["recheck_days"],
            ccpa_compliant=bool(row["ccpa_compliant"]),
            gdpr_compliant=bool(row["gdpr_compliant"]),
            notes=row["notes"],
        )

    # --- Removal operations ---

    def insert_removal(
        self,
        person_id: int,
        broker_id: int,
        method: str,
        finding_id: Optional[int] = None,
        status: str = "pending",
        reference_id: Optional[str] = None,
        next_check_at: Optional[str] = None,
        submitted_at: Optional[str] = None,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO removals
            (person_id, broker_id, method, finding_id, status, notes, next_check_at, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (person_id, broker_id, method, finding_id, status, reference_id, next_check_at, submitted_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_removal(self, removal_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM removals WHERE id = ?", (removal_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def get_removals_by_person(self, person_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM removals WHERE person_id = ? ORDER BY id",
            (person_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_removal(self, removal_id: int, **kwargs) -> None:
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(removal_id)
        self.conn.execute(f"UPDATE removals SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def get_pending_verifications(self) -> list[dict]:
        """Removals due for re-verification, enriched with the broker and
        person fields RemovalVerifier.verify_single needs (broker slug/name,
        search_url_pattern, person first/last name). The verifier cannot
        re-scan without these, so the join lives here rather than being
        re-fetched per row by the caller.
        """
        rows = self.conn.execute(
            """
            SELECT r.*,
                   b.slug AS broker_slug,
                   b.name AS broker_name,
                   b.search_url_pattern AS search_url_pattern,
                   p.name AS person_name
            FROM removals r
            JOIN brokers b ON r.broker_id = b.id
            JOIN persons p ON r.person_id = p.id
            WHERE r.status = 'submitted' AND r.next_check_at <= datetime('now')
            ORDER BY r.next_check_at
            """,
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            name = (self._dec(d.get("person_name")) or "").strip()
            d["person_name"] = name
            parts = name.split()
            d["person_first_name"] = parts[0] if parts else ""
            d["person_last_name"] = parts[-1] if len(parts) > 1 else ""
            result.append(d)
        return result

    def get_confirmed_removals_due_recheck(self) -> list[dict]:
        """Confirmed removals whose last check is older than the broker's
        recheck window — candidates to re-scan for a re-listing. Enriched with
        the broker slug/name/search_url_pattern and the person's first/last
        name so the scanner can run."""
        rows = self.conn.execute(
            """
            SELECT r.*,
                   b.slug AS broker_slug,
                   b.name AS broker_name,
                   b.search_url_pattern AS search_url_pattern,
                   p.name AS person_name
            FROM removals r
            JOIN brokers b ON r.broker_id = b.id
            JOIN persons p ON r.person_id = p.id
            WHERE r.status = 'confirmed'
              AND datetime(IFNULL(r.last_checked_at, r.confirmed_at),
                           '+' || b.recheck_days || ' days') <= datetime('now')
            ORDER BY r.id
            """,
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            name = (self._dec(d.get("person_name")) or "").strip()
            d["person_name"] = name
            parts = name.split()
            d["person_first_name"] = parts[0] if parts else ""
            d["person_last_name"] = parts[-1] if len(parts) > 1 else ""
            result.append(d)
        return result

    def get_removals_for_confirmation(self) -> list[dict]:
        """Submitted removals awaiting an email confirmation, enriched with the
        broker domain and the person's emails so the IMAP monitor can match
        incoming confirmation messages to the right removal."""
        rows = self.conn.execute(
            """
            SELECT r.*,
                   b.slug AS broker_slug,
                   b.name AS broker_name,
                   b.url  AS broker_url,
                   p.emails AS person_emails_enc
            FROM removals r
            JOIN brokers b ON r.broker_id = b.id
            JOIN persons p ON r.person_id = p.id
            WHERE r.status = 'submitted'
            ORDER BY r.id
            """,
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["reference_id"] = d.get("notes")
            d["broker_domain"] = d.get("broker_url")
            try:
                d["person_emails"] = json.loads(self._dec(d.pop("person_emails_enc")) or "[]")
            except (json.JSONDecodeError, TypeError):
                d["person_emails"] = []
            result.append(d)
        return result

    # --- Finding operations ---

    def insert_finding(
        self,
        person_id: int,
        source: str,
        finding_type: str,
        data_found: Optional[dict] = None,
        risk_level: str = "medium",
        url: Optional[str] = None,
        broker_id: Optional[int] = None,
        screenshot_path: Optional[str] = None,
        status: str = "active",
    ) -> int:
        """Insert a finding, de-duplicating on (person, source, url, broker).

        Re-scans re-surface the same listing; without the de-dup the findings
        table would grow unbounded and reports would double-count. An existing
        row is refreshed (updated_at, risk, status) instead of duplicated.

        url is PII (broker search URLs embed the person's name), so it is
        encrypted and cannot be compared directly; de-dup uses a deterministic
        content_hash instead.
        """
        content_hash = self._content_hash(source, broker_id, url)
        existing = self.conn.execute(
            "SELECT id FROM findings WHERE person_id = ? AND content_hash = ?",
            (person_id, content_hash),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE findings SET risk_level = ?, status = ?, data_found = ?, updated_at = datetime('now') WHERE id = ?",
                (risk_level, status, self._enc(json.dumps(data_found or {})), existing["id"]),
            )
            self.conn.commit()
            return existing["id"]
        cursor = self.conn.execute(
            """INSERT INTO findings
            (person_id, broker_id, source, finding_type, data_found, risk_level, url, content_hash, screenshot_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id, broker_id, source, finding_type,
                self._enc(json.dumps(data_found or {})), risk_level,
                self._enc(url), content_hash, screenshot_path, status,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_findings_by_person(self, person_id: int, status: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM findings WHERE person_id = ?"
        params: list = [person_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY discovered_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["url"] = self._dec(d.get("url"))
            try:
                d["data_found"] = json.loads(self._dec(d.get("data_found")) or "{}")
            except (json.JSONDecodeError, TypeError):
                d["data_found"] = {}
            out.append(d)
        return out

    def update_finding_status(self, finding_id: int, status: str) -> None:
        self.conn.execute(
            "UPDATE findings SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, finding_id),
        )
        self.conn.commit()

    # --- Encryption migration ---

    def migrate_to_encrypted(self) -> dict:
        """Encrypt any plaintext PII already in the DB (persons + findings),
        in place. Requires encryption to be enabled. Idempotent: values that
        are already encrypted are skipped, so re-running is safe.
        """
        if not self.cipher:
            raise RuntimeError(
                "Encryption is not enabled; cannot migrate. Set "
                "DIGITAL_FOOTPRINT_ENCRYPT=1 or DIGITAL_FOOTPRINT_DB_KEY."
            )
        migrated = {"persons": 0, "findings": 0}

        for row in self.conn.execute(
            "SELECT id, name, emails, phones, addresses, usernames, date_of_birth FROM persons"
        ).fetchall():
            updates = {}
            for col in ("name", "emails", "phones", "addresses", "usernames", "date_of_birth"):
                v = row[col]
                if v not in (None, "") and not self.cipher.is_encrypted(v):
                    updates[col] = self.cipher.encrypt(v)
            if updates:
                sets = ", ".join(f"{k} = ?" for k in updates)
                self.conn.execute(
                    f"UPDATE persons SET {sets} WHERE id = ?", [*updates.values(), row["id"]]
                )
                migrated["persons"] += 1

        for row in self.conn.execute(
            "SELECT id, source, broker_id, data_found, url, content_hash FROM findings"
        ).fetchall():
            updates = {}
            if row["content_hash"] is None:
                # content_hash is computed from the PLAINTEXT url.
                plain_url = row["url"]
                if self.cipher.is_encrypted(plain_url):
                    plain_url = self.cipher.decrypt(plain_url)
                updates["content_hash"] = self._content_hash(row["source"], row["broker_id"], plain_url)
            for col in ("data_found", "url"):
                v = row[col]
                if v not in (None, "") and not self.cipher.is_encrypted(v):
                    updates[col] = self.cipher.encrypt(v)
            if updates:
                sets = ", ".join(f"{k} = ?" for k in updates)
                self.conn.execute(
                    f"UPDATE findings SET {sets} WHERE id = ?", [*updates.values(), row["id"]]
                )
                migrated["findings"] += 1

        self.conn.commit()
        return migrated

    # --- Breach check status ---

    def record_breach_check(self, person_id: int, ok: bool) -> None:
        """Record whether the most recent breach check for a person succeeded,
        so a report built later can tell 'checked & clean' from 'never verified'."""
        self.conn.execute(
            "INSERT INTO scans (person_id, scan_type, completed_at, status) "
            "VALUES (?, 'breach', datetime('now'), ?)",
            (person_id, "success" if ok else "failed"),
        )
        self.conn.commit()

    def breach_check_ok(self, person_id: int) -> Optional[bool]:
        """True/False for the latest breach check; None if one never ran."""
        row = self.conn.execute(
            "SELECT status FROM scans WHERE person_id = ? AND scan_type = 'breach' "
            "ORDER BY id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        if not row:
            return None
        return row["status"] == "success"

    # --- Breach operations ---

    def insert_breach(
        self,
        person_id: int,
        breach_name: str,
        source: str,
        breach_date: Optional[str] = None,
        data_types: Optional[list[str]] = None,
        severity: str = "medium",
    ) -> int:
        """Insert a breach, de-duplicating on (person, breach_name, source)."""
        existing = self.conn.execute(
            "SELECT id FROM breaches WHERE person_id = ? AND breach_name = ? AND source = ?",
            (person_id, breach_name, source),
        ).fetchone()
        if existing:
            return existing["id"]
        cursor = self.conn.execute(
            """INSERT INTO breaches
            (person_id, breach_name, breach_date, data_types, source, severity)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (person_id, breach_name, breach_date, json.dumps(data_types or []), source, severity),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_breaches_by_person(self, person_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM breaches WHERE person_id = ? ORDER BY discovered_at DESC",
            (person_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["data_types"] = json.loads(d.get("data_types") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["data_types"] = []
            out.append(d)
        return out

    # --- Scheduled run operations ---

    def insert_scheduled_run(self, job_name: str, started_at: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO scheduled_runs (job_name, started_at) VALUES (?, ?)",
            (job_name, started_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_scheduled_run(self, run_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM scheduled_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def update_scheduled_run(self, run_id: int, **kwargs) -> None:
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(run_id)
        self.conn.execute(f"UPDATE scheduled_runs SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def get_last_run(self, job_name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM scheduled_runs WHERE job_name = ? ORDER BY started_at DESC LIMIT 1",
            (job_name,),
        ).fetchone()
        return dict(row) if row else None

    def get_run_history(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM scheduled_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Pipeline run operations ---

    def insert_pipeline_run(self, person_id: int, started_at: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO pipeline_runs (person_id, started_at) VALUES (?, ?)",
            (person_id, started_at),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_pipeline_run(self, run_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def update_pipeline_run(self, run_id: int, **kwargs) -> None:
        sets = []
        values = []
        for key, value in kwargs.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(run_id)
        self.conn.execute(f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def get_pipeline_runs(self, person_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM pipeline_runs WHERE person_id = ? ORDER BY started_at DESC",
            (person_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Status ---

    def get_status(self) -> dict:
        persons_count = self.conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        brokers_count = self.conn.execute("SELECT COUNT(*) FROM brokers").fetchone()[0]

        findings_active = self.conn.execute("SELECT COUNT(*) FROM findings WHERE status = 'active'").fetchone()[0]
        findings_removed = self.conn.execute("SELECT COUNT(*) FROM findings WHERE status = 'removed'").fetchone()[0]
        findings_pending = self.conn.execute("SELECT COUNT(*) FROM findings WHERE status = 'removal_pending'").fetchone()[0]

        removals_pending = self.conn.execute("SELECT COUNT(*) FROM removals WHERE status = 'pending'").fetchone()[0]
        removals_submitted = self.conn.execute("SELECT COUNT(*) FROM removals WHERE status = 'submitted'").fetchone()[0]
        removals_confirmed = self.conn.execute("SELECT COUNT(*) FROM removals WHERE status = 'confirmed'").fetchone()[0]

        breaches_count = self.conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]

        last_scan = self.conn.execute("SELECT MAX(started_at) FROM scans").fetchone()[0]

        return {
            "persons_count": persons_count,
            "brokers_count": brokers_count,
            "findings": {
                "active": findings_active,
                "removal_pending": findings_pending,
                "removed": findings_removed,
            },
            "removals": {
                "pending": removals_pending,
                "submitted": removals_submitted,
                "confirmed": removals_confirmed,
            },
            "breaches_count": breaches_count,
            "last_scan": last_scan,
        }
