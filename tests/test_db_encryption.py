"""Encryption-at-rest tests (P0-2).

Acceptance criteria from the roadmap:
- encrypted DB shows no PII to `strings`
- decrypt round-trip works
- wrong key fails loudly (no silent garbage)
- legacy plaintext DBs still read
- key file is chmod 600
- migration encrypts an existing plaintext DB
"""

import json
import os
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from digital_footprint.config import Config
from digital_footprint.db import Database
from digital_footprint.crypto import Cipher


PII = {
    "name": "Robert Johnson",
    "emails": ["robert.johnson@example.com"],
    "phones": ["+15551234567"],
    "addresses": ["221B Baker Street, Seattle WA"],
}


def _enc_db(tmp_path, key=None) -> Database:
    key = key or Fernet.generate_key().decode()
    cfg = Config(db_path=tmp_path / "enc.db")
    cfg.key_path = tmp_path / "db.key"
    os.environ["DIGITAL_FOOTPRINT_DB_KEY"] = key
    try:
        db = Database(cfg)
        db.initialize()
    finally:
        os.environ.pop("DIGITAL_FOOTPRINT_DB_KEY", None)
    return db


def test_cipher_round_trip():
    c = Cipher(Fernet.generate_key())
    assert c.decrypt(c.encrypt("secret")) == "secret"
    assert c.encrypt(None) is None
    assert c.encrypt("") == ""
    assert c.is_encrypted(c.encrypt("x"))
    assert not c.is_encrypted("plaintext")


def test_cipher_legacy_plaintext_passthrough():
    c = Cipher(Fernet.generate_key())
    # a value that was never encrypted must read back unchanged
    assert c.decrypt("legacy-plaintext-value") == "legacy-plaintext-value"


def test_cipher_wrong_key_raises():
    c1 = Cipher(Fernet.generate_key())
    c2 = Cipher(Fernet.generate_key())
    token = c1.encrypt("secret")
    with pytest.raises(ValueError):
        c2.decrypt(token)


def test_person_round_trips_through_encrypted_db(tmp_path):
    db = _enc_db(tmp_path)
    assert db.cipher is not None
    pid = db.insert_person(**PII)
    p = db.get_person(pid)
    assert p.name == PII["name"]
    assert p.emails == PII["emails"]
    assert p.phones == PII["phones"]
    assert p.addresses == PII["addresses"]


def test_no_pii_in_encrypted_db_file(tmp_path):
    db = _enc_db(tmp_path)
    db.insert_person(**PII)
    db.insert_finding(db.list_persons()[0].id, source="broker", finding_type="listing",
                      data_found={"broker_name": "Radaris"},
                      url="https://radaris.com/p/Robert/Johnson")
    db.close()  # flush WAL
    # scan the DB file (+WAL) for any PII substring
    blob = b""
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(tmp_path / "enc.db") + suffix)
        if p.exists():
            blob += p.read_bytes()
    text = blob.decode("latin-1")
    for needle in ("Robert", "Johnson", "robert.johnson@example.com",
                   "5551234567", "Baker Street", "radaris.com/p/Robert"):
        assert needle not in text, f"PII leaked to disk: {needle!r}"


def test_wrong_key_on_existing_db_fails_loudly(tmp_path):
    db = _enc_db(tmp_path, key=Fernet.generate_key().decode())
    pid = db.insert_person(**PII)
    db.close()
    # reopen with a DIFFERENT key
    cfg = Config(db_path=tmp_path / "enc.db")
    os.environ["DIGITAL_FOOTPRINT_DB_KEY"] = Fernet.generate_key().decode()
    try:
        db2 = Database(cfg)
        db2.initialize()
        with pytest.raises(ValueError):
            db2.get_person(pid)
    finally:
        os.environ.pop("DIGITAL_FOOTPRINT_DB_KEY", None)


def test_key_file_is_600(tmp_path):
    cfg = Config(db_path=tmp_path / "enc.db", encrypt=True)
    cfg.key_path = tmp_path / "db.key"
    db = Database(cfg)
    db.initialize()
    assert db.cipher is not None
    mode = stat.S_IMODE(os.stat(cfg.key_path).st_mode)
    assert mode == 0o600, f"key file mode is {oct(mode)}, want 0o600"


def test_plaintext_db_still_works_without_key(tmp_path):
    # No key configured -> plaintext mode, PII readable in file, but functional.
    cfg = Config(db_path=tmp_path / "plain.db")
    db = Database(cfg)
    db.initialize()
    assert db.cipher is None
    pid = db.insert_person(**PII)
    assert db.get_person(pid).name == "Robert Johnson"


def test_migration_encrypts_existing_plaintext_db(tmp_path):
    # 1. write plaintext
    cfg = Config(db_path=tmp_path / "m.db")
    db = Database(cfg)
    db.initialize()
    pid = db.insert_person(**PII)
    db.insert_finding(pid, source="broker", finding_type="listing",
                      data_found={"broker_name": "Radaris"},
                      url="https://radaris.com/p/Robert/Johnson")
    db.close()

    # 2. reopen with a key and migrate
    key = Fernet.generate_key().decode()
    cfg2 = Config(db_path=tmp_path / "m.db")
    os.environ["DIGITAL_FOOTPRINT_DB_KEY"] = key
    try:
        db2 = Database(cfg2)
        db2.initialize()
        result = db2.migrate_to_encrypted()
        assert result["persons"] == 1
        assert result["findings"] == 1
        # data still reads correctly post-migration
        assert db2.get_person(pid).emails == PII["emails"]
        findings = db2.get_findings_by_person(pid)
        assert findings[0]["url"] == "https://radaris.com/p/Robert/Johnson"
        db2.close()
    finally:
        os.environ.pop("DIGITAL_FOOTPRINT_DB_KEY", None)

    # 3. file no longer contains plaintext PII
    blob = Path(tmp_path / "m.db").read_bytes().decode("latin-1")
    assert "robert.johnson@example.com" not in blob
    assert "Baker Street" not in blob


def test_finding_dedup_survives_encryption(tmp_path):
    db = _enc_db(tmp_path)
    pid = db.insert_person(**PII)
    a = db.insert_finding(pid, source="broker", finding_type="listing",
                          url="https://radaris.com/p/Robert/Johnson", broker_id=None)
    b = db.insert_finding(pid, source="broker", finding_type="listing",
                          url="https://radaris.com/p/Robert/Johnson", broker_id=None)
    assert a == b  # de-dup by content_hash, not by (encrypted) url
    assert len(db.get_findings_by_person(pid)) == 1
