"""Application-layer encryption for PII at rest.

Full-file SQLCipher was the first choice, but it needs a native
``libsqlcipher`` that does not pip-install cleanly on this platform (the
``sqlcipher3-binary`` wheel has no matching distribution), which would make
the project fragile to install for everyone. Instead we encrypt the PII
*values* with Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from the
``cryptography`` package, which is pure-pip and already a dependency.

Scope, stated honestly: this encrypts personal data (names, emails, phones,
addresses, dates of birth, finding URLs/blobs). The schema, column names,
row counts, timestamps and status enums remain visible in the file. No
personal data does.

Key handling:
- ``DIGITAL_FOOTPRINT_DB_KEY`` env var, if set, must be a valid Fernet key
  (generate with ``python -c "from cryptography.fernet import Fernet;
  print(Fernet.generate_key().decode())"``). Highest precedence.
- Otherwise, when encryption is enabled, a key file is loaded (or created on
  first use) next to the database, ``chmod 600``. The key is never written to
  the database and never logged.
"""

import os
import stat
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

ENV_KEY = "DIGITAL_FOOTPRINT_DB_KEY"
ENV_ENABLE = "DIGITAL_FOOTPRINT_ENCRYPT"


def _valid_fernet_key(raw: bytes) -> bool:
    try:
        Fernet(raw)
        return True
    except Exception:
        return False


def key_from_env() -> Optional[bytes]:
    """Return a Fernet key from the environment, or None. Raises if the env
    var is set but malformed (fail loud rather than silently skip encryption)."""
    val = os.environ.get(ENV_KEY)
    if not val:
        return None
    raw = val.strip().encode()
    if not _valid_fernet_key(raw):
        raise ValueError(
            f"{ENV_KEY} is set but is not a valid Fernet key. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return raw


def load_or_create_key_file(key_path: Path) -> bytes:
    """Load a Fernet key from key_path, creating it (chmod 600) if absent."""
    key_path = Path(key_path)
    if key_path.exists():
        raw = key_path.read_bytes().strip()
        if not _valid_fernet_key(raw):
            raise ValueError(f"Key file {key_path} does not contain a valid Fernet key")
        return raw
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    # Write with owner-only perms from the start (open with 0600, not chmod
    # after, to avoid a readable window).
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    # Belt-and-suspenders in case umask widened it.
    os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    return key


def resolve_key(enabled: bool, key_path: Optional[Path]) -> Optional[bytes]:
    """Resolve the encryption key, or None if encryption is off.

    Precedence: env key > key file (when enabled). Encryption is considered
    ON if the env key is present OR ``enabled`` is True.
    """
    env_key = key_from_env()
    if env_key is not None:
        return env_key
    if enabled and key_path is not None:
        return load_or_create_key_file(key_path)
    return None


def encryption_requested() -> bool:
    """True if the operator asked for encryption via env (key or flag)."""
    if os.environ.get(ENV_KEY):
        return True
    return os.environ.get(ENV_ENABLE, "").strip().lower() in ("1", "true", "yes", "on")


class Cipher:
    """Encrypt/decrypt PII strings. Backward compatible on read: a value that
    is not a valid token (legacy plaintext) is returned unchanged, so an
    existing plaintext DB keeps working until migrated."""

    _PREFIX = "enc:"  # marks our ciphertext so plaintext is unambiguous

    def __init__(self, key: bytes):
        self._f = Fernet(key)

    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value == "":
            return ""  # keep empties empty; nothing to hide
        token = self._f.encrypt(value.encode()).decode()
        return self._PREFIX + token

    def decrypt(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value == "":
            return ""
        if not value.startswith(self._PREFIX):
            return value  # legacy plaintext (or non-PII) — pass through
        token = value[len(self._PREFIX):].encode()
        try:
            return self._f.decrypt(token).decode()
        except InvalidToken:
            # Wrong key: do NOT silently return ciphertext as if it were data.
            raise ValueError(
                "Failed to decrypt a PII field — the encryption key does not "
                "match this database. Check DIGITAL_FOOTPRINT_DB_KEY / the key file."
            )

    def is_encrypted(self, value: Optional[str]) -> bool:
        return isinstance(value, str) and value.startswith(self._PREFIX)
