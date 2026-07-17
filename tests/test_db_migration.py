"""Schema back-fill migrations for DBs created before a column existed.

Regression: an older DB whose brokers table predates search_url_pattern (or
whose findings table predates content_hash) must be migrated on initialize,
not raise 'no such column' at runtime. Fresh-DB tests never caught this.
"""

import sqlite3

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.models import Broker


def _make_old_db(path):
    """A minimal pre-migration DB: brokers without search_url_pattern,
    findings without content_hash."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE persons (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE brokers (
            id INTEGER PRIMARY KEY, slug TEXT UNIQUE, name TEXT, url TEXT,
            category TEXT, opt_out_method TEXT, opt_out_url TEXT, opt_out_email TEXT,
            difficulty TEXT, automatable INTEGER, recheck_days INTEGER,
            ccpa_compliant INTEGER, gdpr_compliant INTEGER, notes TEXT
        );
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY, person_id INTEGER, broker_id INTEGER,
            source TEXT, finding_type TEXT, data_found TEXT, risk_level TEXT,
            url TEXT, screenshot_path TEXT, status TEXT,
            discovered_at TEXT, updated_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def test_initialize_backfills_missing_columns(tmp_path):
    db_path = tmp_path / "old.db"
    _make_old_db(db_path)

    db = Database(Config(db_path=db_path))
    db.initialize()  # must ALTER-add the missing columns, not crash

    broker_cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(brokers)")}
    finding_cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(findings)")}
    assert "search_url_pattern" in broker_cols
    assert "content_hash" in finding_cols

    # and the operations that use those columns now work
    db.insert_broker(Broker(slug="radaris", name="Radaris", url="https://radaris.com",
                            category="people_search", search_url_pattern="https://radaris.com/p/{first}/{last}"))
    assert db.get_broker_by_slug("radaris").search_url_pattern == "https://radaris.com/p/{first}/{last}"


def test_initialize_is_idempotent_on_current_schema(tmp_path):
    # running initialize twice on an already-migrated DB is a no-op
    db = Database(Config(db_path=tmp_path / "cur.db"))
    db.initialize()
    db.close()
    db2 = Database(Config(db_path=tmp_path / "cur.db"))
    db2.initialize()  # should not raise
    cols = {r["name"] for r in db2.conn.execute("PRAGMA table_info(brokers)")}
    assert "search_url_pattern" in cols
