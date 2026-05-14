"""Database encryption key management (S-09 audit fix).

Manages encryption keys для SQLCipher-encrypted ProjectDB. Keys stored в
OS native credential store via `keyring`:
  - Windows: Credential Manager (DPAPI-protected)
  - macOS: Keychain
  - Linux: Secret Service (gnome-keyring / KWallet)

Customer never sees passphrase. Key derived once on first run + persisted
to keychain. Machine theft → DB unreadable without keychain entry.

Override mechanism:
  Env var `AURORA_DB_KEY_HEX` (64 lowercase hex chars) takes precedence over
  keychain entry. Used in tests, CI, и emergency disaster recovery.

Per master-plan v3.1 decision: SQLCipher chosen for pharma 152-ФЗ compliance
+ industry-standard "AES-256 encryption at rest" defensibility.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
from typing import Optional

_log = logging.getLogger(__name__)

# Keyring service name (per platform) and account name.
KEYRING_SERVICE = "aurora-launch"
KEYRING_ACCOUNT = "projects-db"

# Env var override (highest precedence).
ENV_DB_KEY_HEX = "AURORA_DB_KEY_HEX"

# Key length: 256 bits = 64 lowercase hex chars (AES-256).
_KEY_LENGTH_HEX = 64
_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class EncryptionKeyError(RuntimeError):
    """Raised on key management failures."""


def _validate_hex_key(key: str) -> None:
    if not _HEX_RE.match(key):
        raise EncryptionKeyError(
            f"DB key must be 64 lowercase hex chars (256-bit AES-256), "
            f"got length {len(key)}"
        )


def generate_db_key() -> str:
    """Generate cryptographically secure 256-bit hex key."""
    return secrets.token_hex(32)  # 32 bytes = 64 hex chars


def get_or_create_db_key(
    *,
    keyring_service: str = KEYRING_SERVICE,
    keyring_account: str = KEYRING_ACCOUNT,
    auto_create: bool = True,
) -> str:
    """Retrieve DB key from environment, keychain, or generate-and-store.

    Resolution order:
      1. Env var `AURORA_DB_KEY_HEX` (tests, CI, recovery)
      2. OS keychain (production)
      3. Newly generated key persisted к keychain (first run, if auto_create)

    Returns:
        64-char hex string suitable для SQLCipher PRAGMA key.

    Raises:
        EncryptionKeyError: keychain unavailable + auto_create=False + no env var
    """
    # 1. Environment variable override
    env_key = os.environ.get(ENV_DB_KEY_HEX)
    if env_key:
        env_key = env_key.lower().strip()
        _validate_hex_key(env_key)
        _log.debug("DB key sourced from environment override")
        return env_key

    # 2. Keychain lookup (optional — `keyring` may not be installed in dev)
    try:
        import keyring  # noqa: PLC0415 — optional dep, defer import

        stored = keyring.get_password(keyring_service, keyring_account)
        if stored:
            stored = stored.lower().strip()
            _validate_hex_key(stored)
            _log.debug("DB key sourced from OS keychain")
            return stored
    except ImportError:
        _log.warning(
            "keyring library not installed — fallback к env-var-only mode. "
            "Production setup requires `pip install keyring` для OS keychain."
        )
        if not auto_create:
            raise EncryptionKeyError(
                "Cannot retrieve key: keyring unavailable + no env override + auto_create=False"
            )

    # 3. Generate + persist new key (first-run case)
    if not auto_create:
        raise EncryptionKeyError(
            "No DB key found в keychain or env. Set AURORA_DB_KEY_HEX or enable auto_create."
        )

    new_key = generate_db_key()
    try:
        import keyring  # noqa: PLC0415

        keyring.set_password(keyring_service, keyring_account, new_key)
        _log.info("Generated new DB key + persisted к OS keychain")
    except ImportError:
        _log.warning(
            "Generated new DB key но keyring not installed — key NOT persisted. "
            "Will regenerate на next run unless AURORA_DB_KEY_HEX is set."
        )

    return new_key


def clear_keychain_key(
    *,
    keyring_service: str = KEYRING_SERVICE,
    keyring_account: str = KEYRING_ACCOUNT,
) -> bool:
    """Remove key from keychain. Returns True if removed, False if not present.

    Used by uninstall workflows + disaster recovery. WARNING: existing
    encrypted DBs become unreadable если key not backed up separately.
    """
    try:
        import keyring  # noqa: PLC0415

        existing = keyring.get_password(keyring_service, keyring_account)
        if existing is None:
            return False
        keyring.delete_password(keyring_service, keyring_account)
        _log.info("Removed DB key from OS keychain")
        return True
    except ImportError:
        _log.warning("keyring library not installed — nothing к clear")
        return False
