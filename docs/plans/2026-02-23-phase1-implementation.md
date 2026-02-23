# Phase 1: Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundation MCP server with database, broker registry, person management, and status tools.

**Architecture:** FastMCP server backed by SQLite. Broker definitions in YAML files loaded at startup. Tools expose person CRUD, broker queries, and system status. Future-phase tools registered as stubs.

**Tech Stack:** Python 3.11+, FastMCP, SQLite, PyYAML, python-dotenv, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `digital_footprint/__init__.py`
- Create: `digital_footprint/tools/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create venv and install dependencies**

Run:
```bash
cd /Volumes/FILES/code/digital-footprint
python3 -m venv .venv
```

**Step 2: Write requirements.txt**

```
fastmcp>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
click>=8.0
pytest>=8.0
pytest-asyncio>=0.23
```

**Step 3: Install dependencies**

Run:
```bash
/Volumes/FILES/code/digital-footprint/.venv/bin/pip install -r /Volumes/FILES/code/digital-footprint/requirements.txt
```
Expected: All packages install successfully.

**Step 4: Write .env.example**

```
# Breach monitoring (Phase 2+)
HIBP_API_KEY=
DEHASHED_API_KEY=
DEHASHED_EMAIL=

# CAPTCHA solving (Phase 3+)
CAPTCHA_API_KEY=

# Email for removal requests (Phase 3+)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
IMAP_HOST=
IMAP_USER=
IMAP_PASSWORD=

# Optional
DIGITAL_FOOTPRINT_DB_PATH=~/.digital-footprint/footprint.db
```

**Step 5: Write .gitignore**

```
.venv/
__pycache__/
*.pyc
.env
*.db
*.db-shm
*.db-wal
.pytest_cache/
dist/
*.egg-info/
```

**Step 6: Create package init files**

`digital_footprint/__init__.py`:
```python
"""Digital Footprint: Personal data removal and privacy protection."""
```

`digital_footprint/tools/__init__.py`:
```python
"""MCP tool implementations."""
```

`tests/__init__.py`:
```python
```

**Step 7: Initialize git repo**

Run:
```bash
cd /Volumes/FILES/code/digital-footprint && git init
```

**Step 8: Commit**

```bash
git add requirements.txt .env.example .gitignore digital_footprint/__init__.py digital_footprint/tools/__init__.py tests/__init__.py CLAUDE.md PRD.md ARCHITECTURE.md docs/
git commit -m "feat: project scaffolding with deps, docs, and package structure"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `digital_footprint/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

`tests/test_config.py`:
```python
import os
from pathlib import Path
from digital_footprint.config import get_config


def test_default_db_path():
    config = get_config()
    assert config.db_path == Path.home() / ".digital-footprint" / "footprint.db"


def test_default_brokers_dir():
    config = get_config()
    assert config.brokers_dir.name == "brokers"


def test_env_override_db_path(tmp_path, monkeypatch):
    custom_path = str(tmp_path / "custom.db")
    monkeypatch.setenv("DIGITAL_FOOTPRINT_DB_PATH", custom_path)
    config = get_config()
    assert config.db_path == Path(custom_path)
```

**Step 2: Run test to verify it fails**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.config'`

**Step 3: Write implementation**

`digital_footprint/config.py`:
```python
"""Configuration management for Digital Footprint."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    db_path: Path = field(default_factory=lambda: Path.home() / ".digital-footprint" / "footprint.db")
    brokers_dir: Path = field(default_factory=lambda: Path(__file__).parent / "brokers")
    hibp_api_key: str = ""
    dehashed_api_key: str = ""
    dehashed_email: str = ""
    captcha_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


def get_config() -> Config:
    """Load configuration from environment variables."""
    load_dotenv()

    config = Config()

    db_override = os.environ.get("DIGITAL_FOOTPRINT_DB_PATH")
    if db_override:
        config.db_path = Path(os.path.expanduser(db_override))

    config.hibp_api_key = os.environ.get("HIBP_API_KEY", "")
    config.dehashed_api_key = os.environ.get("DEHASHED_API_KEY", "")
    config.dehashed_email = os.environ.get("DEHASHED_EMAIL", "")
    config.captcha_api_key = os.environ.get("CAPTCHA_API_KEY", "")
    config.smtp_host = os.environ.get("SMTP_HOST", "")
    config.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    config.smtp_user = os.environ.get("SMTP_USER", "")
    config.smtp_password = os.environ.get("SMTP_PASSWORD", "")

    return config
```

**Step 4: Run test to verify it passes**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_config.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add digital_footprint/config.py tests/test_config.py
git commit -m "feat: configuration module with env loading"
```

---

### Task 3: Data Models

**Files:**
- Create: `digital_footprint/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

`tests/test_models.py`:
```python
import json
from digital_footprint.models import Person, Broker, Finding, Removal, Breach, Scan


def test_person_creation():
    p = Person(name="Marc Shade", emails=["marc@example.com"])
    assert p.name == "Marc Shade"
    assert p.emails == ["marc@example.com"]
    assert p.relation == "self"
    assert p.phones == []


def test_person_to_dict():
    p = Person(name="Marc Shade", emails=["marc@example.com"], phones=["555-0100"])
    d = p.to_dict()
    assert d["name"] == "Marc Shade"
    assert d["emails"] == ["marc@example.com"]
    assert d["phones"] == ["555-0100"]


def test_broker_creation():
    b = Broker(
        slug="spokeo",
        name="Spokeo",
        url="https://www.spokeo.com",
        category="people_search",
        opt_out_method="web_form",
    )
    assert b.slug == "spokeo"
    assert b.difficulty == "medium"
    assert b.recheck_days == 30


def test_finding_creation():
    f = Finding(
        person_id=1,
        source="broker",
        finding_type="profile",
        data_found={"name": "Marc Shade", "address": "123 Main St"},
    )
    assert f.risk_level == "medium"
    assert f.status == "active"
    assert f.data_found["name"] == "Marc Shade"


def test_broker_from_yaml_dict():
    yaml_data = {
        "name": "Spokeo",
        "url": "https://www.spokeo.com",
        "category": "people_search",
        "opt_out": {
            "method": "web_form",
            "url": "https://www.spokeo.com/optout",
            "captcha": True,
            "email_verification": True,
            "time_to_removal": "24-72 hours",
        },
        "automatable": True,
        "difficulty": "easy",
        "recheck_days": 30,
        "ccpa_compliant": True,
    }
    b = Broker.from_yaml("spokeo", yaml_data)
    assert b.name == "Spokeo"
    assert b.opt_out_method == "web_form"
    assert b.opt_out_url == "https://www.spokeo.com/optout"
    assert b.difficulty == "easy"
    assert b.automatable is True
    assert b.ccpa_compliant is True
```

**Step 2: Run test to verify it fails**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

`digital_footprint/models.py`:
```python
"""Data models for Digital Footprint."""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Person:
    name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    usernames: list[str] = field(default_factory=list)
    relation: str = "self"
    date_of_birth: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Broker:
    slug: str
    name: str
    url: str
    category: str
    opt_out_method: Optional[str] = None
    opt_out_url: Optional[str] = None
    opt_out_email: Optional[str] = None
    difficulty: str = "medium"
    automatable: bool = False
    recheck_days: int = 30
    ccpa_compliant: bool = False
    gdpr_compliant: bool = False
    notes: Optional[str] = None
    id: Optional[int] = None

    @classmethod
    def from_yaml(cls, slug: str, data: dict[str, Any]) -> "Broker":
        opt_out = data.get("opt_out", {})
        return cls(
            slug=slug,
            name=data["name"],
            url=data["url"],
            category=data["category"],
            opt_out_method=opt_out.get("method"),
            opt_out_url=opt_out.get("url"),
            opt_out_email=opt_out.get("email"),
            difficulty=data.get("difficulty", "medium"),
            automatable=data.get("automatable", False),
            recheck_days=data.get("recheck_days", 30),
            ccpa_compliant=data.get("ccpa_compliant", False),
            gdpr_compliant=data.get("gdpr_compliant", False),
            notes=data.get("notes"),
        )


@dataclass
class Finding:
    person_id: int
    source: str
    finding_type: str
    data_found: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    url: Optional[str] = None
    screenshot_path: Optional[str] = None
    status: str = "active"
    broker_id: Optional[int] = None
    id: Optional[int] = None
    discovered_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Removal:
    person_id: int
    broker_id: int
    method: str
    finding_id: Optional[int] = None
    status: str = "pending"
    submitted_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    attempts: int = 0
    next_check_at: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Breach:
    person_id: int
    breach_name: str
    source: str
    breach_date: Optional[str] = None
    data_types: list[str] = field(default_factory=list)
    severity: str = "medium"
    discovered_at: Optional[str] = None
    action_taken: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Scan:
    scan_type: str
    person_id: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    findings_count: int = 0
    new_findings: int = 0
    removed_count: int = 0
    status: str = "running"
    id: Optional[int] = None
```

**Step 4: Run test to verify it passes**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_models.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add digital_footprint/models.py tests/test_models.py
git commit -m "feat: data models for persons, brokers, findings, removals, breaches, scans"
```

---

### Task 4: Database Module

**Files:**
- Create: `digital_footprint/db.py`
- Create: `tests/test_db.py`
- Create: `tests/conftest.py`

**Step 1: Write conftest with test fixtures**

`tests/conftest.py`:
```python
import pytest
from pathlib import Path
from digital_footprint.db import Database
from digital_footprint.config import Config


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    config = Config(db_path=db_path, brokers_dir=Path(__file__).parent.parent / "digital_footprint" / "brokers")
    db = Database(config)
    db.initialize()
    yield db
    db.close()
```

**Step 2: Write the failing tests**

`tests/test_db.py`:
```python
from digital_footprint.db import Database


def test_database_creates_tables(tmp_db):
    cursor = tmp_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "persons" in tables
    assert "brokers" in tables
    assert "findings" in tables
    assert "removals" in tables
    assert "breaches" in tables
    assert "scans" in tables


def test_insert_person(tmp_db):
    person_id = tmp_db.insert_person(
        name="Marc Shade",
        emails=["marc@example.com"],
        phones=["555-0100"],
    )
    assert person_id == 1


def test_get_person(tmp_db):
    tmp_db.insert_person(name="Marc Shade", emails=["marc@example.com"])
    person = tmp_db.get_person(1)
    assert person is not None
    assert person.name == "Marc Shade"
    assert person.emails == ["marc@example.com"]


def test_list_persons(tmp_db):
    tmp_db.insert_person(name="Alice", emails=["alice@example.com"])
    tmp_db.insert_person(name="Bob", emails=["bob@example.com"])
    persons = tmp_db.list_persons()
    assert len(persons) == 2


def test_update_person(tmp_db):
    tmp_db.insert_person(name="Marc Shade", emails=["marc@example.com"])
    tmp_db.update_person(1, phones=["555-0100"])
    person = tmp_db.get_person(1)
    assert person.phones == ["555-0100"]


def test_insert_broker(tmp_db):
    from digital_footprint.models import Broker
    broker = Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search")
    broker_id = tmp_db.insert_broker(broker)
    assert broker_id == 1


def test_get_broker_by_slug(tmp_db):
    from digital_footprint.models import Broker
    broker = Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search")
    tmp_db.insert_broker(broker)
    result = tmp_db.get_broker_by_slug("spokeo")
    assert result is not None
    assert result.name == "Spokeo"


def test_list_brokers_by_category(tmp_db):
    from digital_footprint.models import Broker
    tmp_db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search"))
    tmp_db.insert_broker(Broker(slug="acxiom", name="Acxiom", url="https://acxiom.com", category="marketing"))
    results = tmp_db.list_brokers(category="people_search")
    assert len(results) == 1
    assert results[0].slug == "spokeo"


def test_broker_stats(tmp_db):
    from digital_footprint.models import Broker
    tmp_db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search", difficulty="easy", automatable=True))
    tmp_db.insert_broker(Broker(slug="acxiom", name="Acxiom", url="https://acxiom.com", category="marketing", difficulty="hard"))
    stats = tmp_db.broker_stats()
    assert stats["total"] == 2
    assert stats["by_category"]["people_search"] == 1
    assert stats["by_difficulty"]["easy"] == 1
    assert stats["automatable"] == 1


def test_get_status(tmp_db):
    tmp_db.insert_person(name="Marc", emails=["marc@example.com"])
    status = tmp_db.get_status()
    assert status["persons_count"] == 1
    assert status["brokers_count"] == 0
    assert status["findings"]["active"] == 0
```

**Step 3: Run tests to verify they fail**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'digital_footprint.db'`

**Step 4: Write implementation**

`digital_footprint/db.py`:
```python
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
```

**Step 5: Run tests to verify they pass**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_db.py -v`
Expected: All 10 tests passed

**Step 6: Commit**

```bash
git add digital_footprint/db.py tests/conftest.py tests/test_db.py
git commit -m "feat: database module with schema, person/broker CRUD, and status queries"
```

---

### Task 5: Broker Registry Loader

**Files:**
- Create: `digital_footprint/broker_registry.py`
- Create: `digital_footprint/brokers/_schema.yaml`
- Create: `digital_footprint/brokers/spokeo.yaml` (first broker as template)
- Create: `tests/test_broker_registry.py`

**Step 1: Write the failing test**

`tests/test_broker_registry.py`:
```python
import yaml
from pathlib import Path
from digital_footprint.broker_registry import load_broker_yaml, load_all_brokers, validate_broker_yaml


def test_load_single_broker_yaml(tmp_path):
    broker_file = tmp_path / "testbroker.yaml"
    broker_file.write_text(yaml.dump({
        "name": "TestBroker",
        "url": "https://test.com",
        "category": "people_search",
        "opt_out": {"method": "email", "email": "privacy@test.com"},
        "difficulty": "easy",
        "recheck_days": 14,
    }))
    broker = load_broker_yaml(broker_file)
    assert broker.slug == "testbroker"
    assert broker.name == "TestBroker"
    assert broker.opt_out_method == "email"
    assert broker.opt_out_email == "privacy@test.com"


def test_load_all_brokers(tmp_path):
    for name in ["alpha", "beta", "gamma"]:
        (tmp_path / f"{name}.yaml").write_text(yaml.dump({
            "name": name.title(),
            "url": f"https://{name}.com",
            "category": "people_search",
        }))
    # Should skip non-yaml and underscore-prefixed files
    (tmp_path / "_schema.yaml").write_text("schema: true")
    (tmp_path / "readme.txt").write_text("not a broker")

    brokers = load_all_brokers(tmp_path)
    assert len(brokers) == 3
    slugs = {b.slug for b in brokers}
    assert slugs == {"alpha", "beta", "gamma"}


def test_validate_broker_yaml_valid():
    data = {
        "name": "Test",
        "url": "https://test.com",
        "category": "people_search",
    }
    errors = validate_broker_yaml(data)
    assert errors == []


def test_validate_broker_yaml_missing_required():
    data = {"name": "Test"}
    errors = validate_broker_yaml(data)
    assert len(errors) > 0
    assert any("url" in e for e in errors)


def test_real_brokers_dir_has_files():
    """Verify the actual brokers directory has at least one YAML file."""
    brokers_dir = Path(__file__).parent.parent / "digital_footprint" / "brokers"
    if brokers_dir.exists():
        yamls = list(brokers_dir.glob("*.yaml"))
        # Filter out schema
        yamls = [y for y in yamls if not y.name.startswith("_")]
        assert len(yamls) >= 1, "Should have at least one broker YAML"
```

**Step 2: Run tests to verify they fail**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_broker_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

`digital_footprint/broker_registry.py`:
```python
"""Load and validate broker YAML definitions."""

from pathlib import Path
from typing import Optional

import yaml

from digital_footprint.models import Broker

REQUIRED_FIELDS = {"name", "url", "category"}
VALID_CATEGORIES = {
    "people_search", "background_check", "public_records", "marketing",
    "social_aggregator", "property", "financial", "genealogy",
    "reverse_lookup", "image_search",
}
VALID_METHODS = {"web_form", "email", "api", "phone", "mail"}
VALID_DIFFICULTIES = {"easy", "medium", "hard", "manual"}


def validate_broker_yaml(data: dict) -> list[str]:
    """Validate a broker YAML dictionary. Returns list of error strings."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    if "category" in data and data["category"] not in VALID_CATEGORIES:
        errors.append(f"Invalid category: {data['category']}. Valid: {VALID_CATEGORIES}")
    if "difficulty" in data and data["difficulty"] not in VALID_DIFFICULTIES:
        errors.append(f"Invalid difficulty: {data['difficulty']}. Valid: {VALID_DIFFICULTIES}")
    opt_out = data.get("opt_out", {})
    if "method" in opt_out and opt_out["method"] not in VALID_METHODS:
        errors.append(f"Invalid opt_out method: {opt_out['method']}. Valid: {VALID_METHODS}")
    return errors


def load_broker_yaml(path: Path) -> Broker:
    """Load a single broker YAML file and return a Broker model."""
    with open(path) as f:
        data = yaml.safe_load(f)
    slug = path.stem
    return Broker.from_yaml(slug, data)


def load_all_brokers(brokers_dir: Path) -> list[Broker]:
    """Load all broker YAML files from a directory."""
    brokers = []
    for path in sorted(brokers_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        brokers.append(load_broker_yaml(path))
    return brokers
```

**Step 4: Write the schema reference and first broker YAML**

`digital_footprint/brokers/_schema.yaml`:
```yaml
# Broker YAML Schema Reference
# See docs/BROKER_REGISTRY.md for full documentation

required:
  - name        # string: Human-readable name
  - url         # string: Primary website URL
  - category    # enum: people_search|background_check|public_records|marketing|social_aggregator|property|financial|genealogy|reverse_lookup|image_search

optional:
  opt_out:
    method: enum    # web_form|email|api|phone|mail
    url: string
    email: string
    steps: list[string]
    captcha: boolean
    email_verification: boolean
    phone_verification: boolean
    time_to_removal: string
  difficulty: enum  # easy|medium|hard|manual
  automatable: boolean
  recheck_days: integer
  ccpa_compliant: boolean
  gdpr_compliant: boolean
  notes: string
```

`digital_footprint/brokers/spokeo.yaml`:
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
  time_to_removal: "24-72 hours"

automatable: true
difficulty: easy
recheck_days: 30

ccpa_compliant: true
gdpr_compliant: false
notes: "Data may remain visible to paid subscribers even after opt-out. Check name variations."
```

**Step 5: Run tests to verify they pass**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/test_broker_registry.py -v`
Expected: 5 passed

**Step 6: Commit**

```bash
git add digital_footprint/broker_registry.py digital_footprint/brokers/ tests/test_broker_registry.py
git commit -m "feat: broker registry loader with YAML validation and spokeo template"
```

---

### Task 6: Populate Initial Broker Registry (50 brokers)

**Files:**
- Create: 49 more YAML files in `digital_footprint/brokers/`

**Step 1: Create all 50 broker YAML files**

Use a subagent to research and write YAML files for each broker, following the spokeo.yaml template. Each file needs:
- Correct opt-out URL (researched from Incogni guides and Big-Ass Data Broker Opt-Out List)
- Correct opt-out method
- Correct category and difficulty
- CCPA compliance flag

The 50 brokers are listed in the design doc under "Broker Registry - Initial 50". This step is a batch creation operation — create all 49 remaining YAML files.

**Step 2: Run validation**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/python -c "from digital_footprint.broker_registry import load_all_brokers; from pathlib import Path; bs = load_all_brokers(Path('digital_footprint/brokers')); print(f'{len(bs)} brokers loaded'); [print(f'  {b.slug}: {b.name} ({b.category})') for b in bs]"`

Expected: "50 brokers loaded" followed by broker list.

**Step 3: Commit**

```bash
git add digital_footprint/brokers/
git commit -m "feat: populate broker registry with 50 data broker definitions"
```

---

### Task 7: MCP Server with Person and Broker Tools

**Files:**
- Create: `server.py`
- Create: `digital_footprint/tools/person_tools.py`
- Create: `digital_footprint/tools/broker_tools.py`
- Create: `digital_footprint/tools/status_tools.py`

**Step 1: Write person_tools.py**

`digital_footprint/tools/person_tools.py`:
```python
"""Person management MCP tools."""

import json
from typing import Optional

from digital_footprint.db import Database


def register_person_tools(mcp, db: Database):
    """Register all person-related tools with the MCP server."""

    @mcp.tool()
    def footprint_add_person(
        name: str,
        emails: list[str],
        phones: list[str] = None,
        addresses: list[str] = None,
        usernames: list[str] = None,
        date_of_birth: str = None,
        relation: str = "self",
    ) -> str:
        """Register a person for digital footprint protection.

        Args:
            name: Full legal name
            emails: Email addresses to monitor
            phones: Phone numbers (optional)
            addresses: Physical addresses (optional)
            usernames: Known usernames across platforms (optional)
            date_of_birth: Date of birth YYYY-MM-DD (optional)
            relation: Relationship - self, spouse, child, parent, other (default: self)
        """
        person_id = db.insert_person(
            name=name,
            emails=emails,
            phones=phones or [],
            addresses=addresses or [],
            usernames=usernames or [],
            relation=relation,
            date_of_birth=date_of_birth,
        )
        person = db.get_person(person_id)
        return json.dumps(person.to_dict(), indent=2)

    @mcp.tool()
    def footprint_list_persons() -> str:
        """List all persons currently under digital footprint protection."""
        persons = db.list_persons()
        if not persons:
            return "No persons registered. Use footprint_add_person to add someone."
        result = []
        for p in persons:
            result.append(f"[{p.id}] {p.name} ({p.relation}) - {len(p.emails)} emails, {len(p.phones)} phones")
        return "\n".join(result)

    @mcp.tool()
    def footprint_get_person(person_id: int = None, name: str = None) -> str:
        """Get full details for a protected person.

        Args:
            person_id: Person ID (preferred)
            name: Person name (fuzzy match)
        """
        if person_id:
            person = db.get_person(person_id)
        elif name:
            persons = db.list_persons()
            person = next((p for p in persons if name.lower() in p.name.lower()), None)
        else:
            return "Provide either person_id or name."
        if not person:
            return "Person not found."
        return json.dumps(person.to_dict(), indent=2)

    @mcp.tool()
    def footprint_update_person(
        person_id: int,
        name: str = None,
        emails: list[str] = None,
        phones: list[str] = None,
        addresses: list[str] = None,
        usernames: list[str] = None,
        date_of_birth: str = None,
        relation: str = None,
    ) -> str:
        """Update a protected person's information.

        Args:
            person_id: ID of the person to update
            name: New name (optional)
            emails: New email list (optional)
            phones: New phone list (optional)
            addresses: New address list (optional)
            usernames: New username list (optional)
            date_of_birth: New DOB (optional)
            relation: New relation (optional)
        """
        kwargs = {}
        for field, value in [
            ("name", name), ("emails", emails), ("phones", phones),
            ("addresses", addresses), ("usernames", usernames),
            ("date_of_birth", date_of_birth), ("relation", relation),
        ]:
            if value is not None:
                kwargs[field] = value
        if not kwargs:
            return "No fields to update."
        db.update_person(person_id, **kwargs)
        person = db.get_person(person_id)
        return json.dumps(person.to_dict(), indent=2)
```

**Step 2: Write broker_tools.py**

`digital_footprint/tools/broker_tools.py`:
```python
"""Broker registry MCP tools."""

import json
from typing import Optional

from digital_footprint.db import Database


def register_broker_tools(mcp, db: Database):
    """Register all broker-related tools with the MCP server."""

    @mcp.tool()
    def footprint_list_brokers(
        category: str = None,
        difficulty: str = None,
        automatable: bool = None,
    ) -> str:
        """List data brokers in the registry.

        Args:
            category: Filter by category (people_search, background_check, marketing, etc.)
            difficulty: Filter by difficulty (easy, medium, hard, manual)
            automatable: Filter by automation support (true/false)
        """
        brokers = db.list_brokers(category=category, difficulty=difficulty, automatable=automatable)
        if not brokers:
            return "No brokers match the filters."
        lines = []
        for b in brokers:
            auto = "auto" if b.automatable else "manual"
            lines.append(f"  {b.slug}: {b.name} [{b.category}] {b.difficulty}/{auto}")
        return f"{len(brokers)} brokers:\n" + "\n".join(lines)

    @mcp.tool()
    def footprint_get_broker(slug: str = None, name: str = None) -> str:
        """Get full details for a data broker including opt-out instructions.

        Args:
            slug: Broker slug (filename without .yaml)
            name: Broker name (fuzzy match)
        """
        if slug:
            broker = db.get_broker_by_slug(slug)
        elif name:
            all_brokers = db.list_brokers()
            broker = next((b for b in all_brokers if name.lower() in b.name.lower()), None)
        else:
            return "Provide either slug or name."
        if not broker:
            return "Broker not found."
        info = {
            "slug": broker.slug,
            "name": broker.name,
            "url": broker.url,
            "category": broker.category,
            "opt_out_method": broker.opt_out_method,
            "opt_out_url": broker.opt_out_url,
            "opt_out_email": broker.opt_out_email,
            "difficulty": broker.difficulty,
            "automatable": broker.automatable,
            "recheck_days": broker.recheck_days,
            "ccpa_compliant": broker.ccpa_compliant,
            "gdpr_compliant": broker.gdpr_compliant,
            "notes": broker.notes,
        }
        return json.dumps(info, indent=2)

    @mcp.tool()
    def footprint_broker_stats() -> str:
        """Get statistics about the broker registry."""
        stats = db.broker_stats()
        lines = [
            f"Total brokers: {stats['total']}",
            "",
            "By category:",
        ]
        for cat, count in sorted(stats["by_category"].items()):
            lines.append(f"  {cat}: {count}")
        lines.append("")
        lines.append("By difficulty:")
        for diff, count in sorted(stats["by_difficulty"].items()):
            lines.append(f"  {diff}: {count}")
        lines.append("")
        lines.append("By opt-out method:")
        for method, count in sorted(stats["by_method"].items()):
            lines.append(f"  {method}: {count}")
        lines.append("")
        lines.append(f"Automatable: {stats['automatable']}")
        return "\n".join(lines)
```

**Step 3: Write status_tools.py**

`digital_footprint/tools/status_tools.py`:
```python
"""System status MCP tools."""

from digital_footprint.db import Database


def register_status_tools(mcp, db: Database):
    """Register status dashboard tool."""

    @mcp.tool()
    def footprint_status() -> str:
        """Get Digital Footprint system status dashboard.

        Shows protection overview: persons, brokers, findings, removals, breaches, and last scan.
        """
        s = db.get_status()
        lines = [
            "=== Digital Footprint Status ===",
            "",
            f"Protected persons: {s['persons_count']}",
            f"Broker registry:   {s['brokers_count']} brokers",
            "",
            "Findings:",
            f"  Active:           {s['findings']['active']}",
            f"  Removal pending:  {s['findings']['removal_pending']}",
            f"  Removed:          {s['findings']['removed']}",
            "",
            "Removals:",
            f"  Pending:          {s['removals']['pending']}",
            f"  Submitted:        {s['removals']['submitted']}",
            f"  Confirmed:        {s['removals']['confirmed']}",
            "",
            f"Breaches detected:  {s['breaches_count']}",
            f"Last scan:          {s['last_scan'] or 'never'}",
        ]
        return "\n".join(lines)
```

**Step 4: Write server.py**

`server.py`:
```python
#!/usr/bin/env python3
"""
Digital Footprint MCP Server
Personal data removal and privacy protection.
"""

from fastmcp import FastMCP

from digital_footprint.config import get_config
from digital_footprint.db import Database
from digital_footprint.broker_registry import load_all_brokers
from digital_footprint.tools.person_tools import register_person_tools
from digital_footprint.tools.broker_tools import register_broker_tools
from digital_footprint.tools.status_tools import register_status_tools

# Initialize
config = get_config()
db = Database(config)
db.initialize()

# Load broker registry into database
brokers = load_all_brokers(config.brokers_dir)
for broker in brokers:
    db.insert_broker(broker)

# Create MCP server
mcp = FastMCP("digital-footprint")

# Register implemented tools
register_person_tools(mcp, db)
register_broker_tools(mcp, db)
register_status_tools(mcp, db)


# --- Stub tools for future phases ---

@mcp.tool()
def footprint_scan(person_id: int = None, email: str = None) -> str:
    """Run a full exposure scan for a person. [Phase 2 - Not yet implemented]"""
    return "Scanning not yet implemented. Coming in Phase 2. Use footprint_add_person first to register for protection."

@mcp.tool()
def footprint_broker_check(broker_slug: str, person_id: int = 1) -> str:
    """Check a specific data broker for a person's data. [Phase 2 - Not yet implemented]"""
    return "Broker checking not yet implemented. Coming in Phase 2."

@mcp.tool()
def footprint_broker_remove(broker_slug: str, person_id: int = 1) -> str:
    """Submit a removal request to a specific data broker. [Phase 3 - Not yet implemented]"""
    return "Removal engine not yet implemented. Coming in Phase 3."

@mcp.tool()
def footprint_breach_check(email: str = None, username: str = None) -> str:
    """Check for credential exposure in data breaches. [Phase 2 - Not yet implemented]"""
    return "Breach checking not yet implemented. Coming in Phase 2."

@mcp.tool()
def footprint_username_search(username: str) -> str:
    """Search for a username across 3,000+ sites. [Phase 2 - Not yet implemented]"""
    return "Username search not yet implemented. Coming in Phase 2."

@mcp.tool()
def footprint_exposure_report(person_id: int = 1) -> str:
    """Generate a comprehensive exposure report. [Phase 2 - Not yet implemented]"""
    return "Exposure reports not yet implemented. Coming in Phase 2."

@mcp.tool()
def footprint_removal_status(person_id: int = None) -> str:
    """Get status of all pending removal requests. [Phase 3 - Not yet implemented]"""
    return "Removal tracking not yet implemented. Coming in Phase 3."

@mcp.tool()
def footprint_dark_web_monitor(email: str = None) -> str:
    """Monitor dark web sources for exposed personal data. [Phase 4 - Not yet implemented]"""
    return "Dark web monitoring not yet implemented. Coming in Phase 4."

@mcp.tool()
def footprint_social_audit(person_id: int = 1) -> str:
    """Audit social media privacy settings and exposure. [Phase 4 - Not yet implemented]"""
    return "Social media audit not yet implemented. Coming in Phase 4."

@mcp.tool()
def footprint_google_dork(name: str, additional_terms: str = None) -> str:
    """Run targeted Google searches to find data exposure. [Phase 2 - Not yet implemented]"""
    return "Google dorking not yet implemented. Coming in Phase 2."


if __name__ == "__main__":
    mcp.run()
```

**Step 5: Test server starts**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/python -c "from server import mcp; print(f'Server created: {mcp.name}'); print(f'Tools: {len(mcp._tool_manager._tools)}')"` (from project dir)

Expected: Server created, tool count = ~18

**Step 6: Commit**

```bash
git add server.py digital_footprint/tools/person_tools.py digital_footprint/tools/broker_tools.py digital_footprint/tools/status_tools.py
git commit -m "feat: MCP server with person, broker, and status tools plus future-phase stubs"
```

---

### Task 8: Integration Tests

**Files:**
- Create: `tests/test_person_tools.py`
- Create: `tests/test_broker_tools.py`
- Create: `tests/test_status_tools.py`

**Step 1: Write test_person_tools.py**

`tests/test_person_tools.py`:
```python
"""Test person management tools end-to-end."""

import json
from digital_footprint.tools.person_tools import register_person_tools


class FakeMCP:
    """Minimal MCP mock that captures registered tools."""
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def test_add_and_get_person(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)

    result = mcp.tools["footprint_add_person"](
        name="Marc Shade",
        emails=["marc@example.com"],
        phones=["555-0100"],
    )
    data = json.loads(result)
    assert data["name"] == "Marc Shade"
    assert data["emails"] == ["marc@example.com"]
    assert "id" in data

    result2 = mcp.tools["footprint_get_person"](person_id=data["id"])
    data2 = json.loads(result2)
    assert data2["name"] == "Marc Shade"


def test_list_persons(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)
    mcp.tools["footprint_add_person"](name="Alice", emails=["a@b.com"])
    mcp.tools["footprint_add_person"](name="Bob", emails=["b@b.com"])
    result = mcp.tools["footprint_list_persons"]()
    assert "Alice" in result
    assert "Bob" in result


def test_update_person(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)
    mcp.tools["footprint_add_person"](name="Marc Shade", emails=["marc@example.com"])
    result = mcp.tools["footprint_update_person"](person_id=1, phones=["555-9999"])
    data = json.loads(result)
    assert data["phones"] == ["555-9999"]


def test_get_person_by_name(tmp_db):
    mcp = FakeMCP()
    register_person_tools(mcp, tmp_db)
    mcp.tools["footprint_add_person"](name="Marc Shade", emails=["marc@example.com"])
    result = mcp.tools["footprint_get_person"](name="marc")
    data = json.loads(result)
    assert data["name"] == "Marc Shade"
```

**Step 2: Write test_broker_tools.py**

`tests/test_broker_tools.py`:
```python
"""Test broker registry tools end-to-end."""

import json
from digital_footprint.models import Broker
from digital_footprint.tools.broker_tools import register_broker_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _seed_brokers(db):
    db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search", difficulty="easy", automatable=True, opt_out_method="web_form"))
    db.insert_broker(Broker(slug="acxiom", name="Acxiom", url="https://acxiom.com", category="marketing", difficulty="hard", opt_out_method="email"))
    db.insert_broker(Broker(slug="beenverified", name="BeenVerified", url="https://beenverified.com", category="people_search", difficulty="easy", automatable=True, opt_out_method="web_form"))


def test_list_brokers(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_list_brokers"]()
    assert "3 brokers" in result
    assert "spokeo" in result


def test_list_brokers_filtered(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_list_brokers"](category="marketing")
    assert "1 brokers" in result
    assert "acxiom" in result


def test_get_broker(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_get_broker"](slug="spokeo")
    data = json.loads(result)
    assert data["name"] == "Spokeo"
    assert data["opt_out_method"] == "web_form"


def test_broker_stats(tmp_db):
    _seed_brokers(tmp_db)
    mcp = FakeMCP()
    register_broker_tools(mcp, tmp_db)
    result = mcp.tools["footprint_broker_stats"]()
    assert "Total brokers: 3" in result
    assert "people_search: 2" in result
    assert "Automatable: 2" in result
```

**Step 3: Write test_status_tools.py**

`tests/test_status_tools.py`:
```python
"""Test status dashboard tool."""

from digital_footprint.tools.status_tools import register_status_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def test_status_empty(tmp_db):
    mcp = FakeMCP()
    register_status_tools(mcp, tmp_db)
    result = mcp.tools["footprint_status"]()
    assert "Protected persons: 0" in result
    assert "Last scan:          never" in result


def test_status_with_data(tmp_db):
    tmp_db.insert_person(name="Marc", emails=["marc@example.com"])
    from digital_footprint.models import Broker
    tmp_db.insert_broker(Broker(slug="spokeo", name="Spokeo", url="https://spokeo.com", category="people_search"))
    mcp = FakeMCP()
    register_status_tools(mcp, tmp_db)
    result = mcp.tools["footprint_status"]()
    assert "Protected persons: 1" in result
    assert "Broker registry:   1" in result
```

**Step 4: Run all tests**

Run: `/Volumes/FILES/code/digital-footprint/.venv/bin/pytest tests/ -v`
Expected: All tests pass (~25 tests)

**Step 5: Commit**

```bash
git add tests/test_person_tools.py tests/test_broker_tools.py tests/test_status_tools.py
git commit -m "test: integration tests for person, broker, and status tools"
```

---

### Task 9: Register MCP Server in Claude Config

**Files:**
- Modify: `~/.claude.json` (add digital-footprint-mcp entry)

**Step 1: Add MCP server registration**

Add to `~/.claude.json` under `mcpServers`:
```json
"digital-footprint-mcp": {
  "command": "/Volumes/FILES/code/digital-footprint/.venv/bin/python",
  "args": ["/Volumes/FILES/code/digital-footprint/server.py"]
}
```

**Step 2: Verify server starts via MCP**

Restart Claude Code session and verify the `footprint_status` tool is available.

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: complete Phase 1 foundation"
```

---

### Task 10: Create /footprint Skill

**Files:**
- Create: `.claude/skills/footprint.md`

**Step 1: Write skill file**

`.claude/skills/footprint.md`:
```markdown
---
name: footprint
description: Digital Footprint system status and quick actions for personal data removal
---

You are the Digital Footprint privacy protection assistant. When the user invokes /footprint:

1. Call the `footprint_status` MCP tool to get the current system status
2. Display the status in a clean format
3. If no persons are registered, prompt to add one with `footprint_add_person`
4. Offer quick actions:
   - "Run exposure scan" → call `footprint_scan` (Phase 2+)
   - "List brokers" → call `footprint_list_brokers`
   - "Check breaches" → call `footprint_breach_check` (Phase 2+)
   - "View broker details" → call `footprint_get_broker`

The MCP server is `digital-footprint-mcp`. All tools are prefixed with `footprint_`.
```

**Step 2: Commit**

```bash
git add .claude/skills/footprint.md
git commit -m "feat: /footprint skill for system status"
```

---

### Verification Checklist

After completing all tasks, verify:

1. [ ] `.venv` created with all deps installed
2. [ ] `pytest tests/` — all tests pass
3. [ ] Server starts: `.venv/bin/python server.py`
4. [ ] 50 broker YAML files load without errors
5. [ ] `footprint_add_person` creates person in DB
6. [ ] `footprint_list_brokers` shows 50 brokers
7. [ ] `footprint_status` shows correct counts
8. [ ] Stub tools return "not yet implemented" messages
9. [ ] MCP server registered in `~/.claude.json`
10. [ ] `/footprint` skill works in Claude Code
