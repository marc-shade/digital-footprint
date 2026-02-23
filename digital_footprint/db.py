"""SQLite database manager for Digital Footprint."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from digital_footprint.config import Config
from digital_footprint.models import Person, Broker


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
"""


class Database:
    def __init__(self, config: Config):
        self.config = config
        self.conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.config.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

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
                name,
                relation,
                json.dumps(emails or []),
                json.dumps(phones or []),
                json.dumps(addresses or []),
                json.dumps(usernames or []),
                date_of_birth,
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
        json_fields = {"emails", "phones", "addresses", "usernames"}
        sets = []
        values = []
        for key, value in kwargs.items():
            if key in json_fields:
                sets.append(f"{key} = ?")
                values.append(json.dumps(value))
            else:
                sets.append(f"{key} = ?")
                values.append(value)
        sets.append("updated_at = datetime('now')")
        values.append(person_id)
        self.conn.execute(f"UPDATE persons SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()

    def _row_to_person(self, row: sqlite3.Row) -> Person:
        return Person(
            id=row["id"],
            name=row["name"],
            relation=row["relation"],
            emails=json.loads(row["emails"]),
            phones=json.loads(row["phones"]),
            addresses=json.loads(row["addresses"]),
            usernames=json.loads(row["usernames"]),
            date_of_birth=row["date_of_birth"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- Broker operations ---

    def insert_broker(self, broker: Broker) -> int:
        cursor = self.conn.execute(
            """INSERT OR REPLACE INTO brokers
            (slug, name, url, category, opt_out_method, opt_out_url, opt_out_email,
             difficulty, automatable, recheck_days, ccpa_compliant, gdpr_compliant, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                broker.slug, broker.name, broker.url, broker.category,
                broker.opt_out_method, broker.opt_out_url, broker.opt_out_email,
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
        rows = self.conn.execute(
            "SELECT * FROM removals WHERE status = 'submitted' AND next_check_at <= datetime('now') ORDER BY next_check_at",
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
