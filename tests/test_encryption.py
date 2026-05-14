"""S-09 SQLCipher encryption + key management tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aurora_launch.persistence.encryption import (
    ENV_DB_KEY_HEX,
    EncryptionKeyError,
    clear_keychain_key,
    generate_db_key,
    get_or_create_db_key,
)


class TestKeyGeneration:
    def test_generate_db_key_64_hex_chars(self) -> None:
        key = generate_db_key()
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_generate_db_key_unique(self) -> None:
        keys = {generate_db_key() for _ in range(20)}
        assert len(keys) == 20  # all unique


class TestKeyResolution:
    def test_env_var_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        custom_key = "a" * 64
        monkeypatch.setenv(ENV_DB_KEY_HEX, custom_key)
        resolved = get_or_create_db_key()
        assert resolved == custom_key

    def test_env_var_invalid_hex_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_DB_KEY_HEX, "not-a-hex")
        with pytest.raises(EncryptionKeyError, match="64 lowercase hex"):
            get_or_create_db_key()

    def test_env_var_short_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_DB_KEY_HEX, "ab")
        with pytest.raises(EncryptionKeyError, match="64 lowercase hex"):
            get_or_create_db_key()

    def test_env_var_uppercase_normalised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_DB_KEY_HEX, "AB" * 32)
        resolved = get_or_create_db_key()
        assert resolved == "ab" * 32

    def test_auto_create_false_no_env_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ENV_DB_KEY_HEX, raising=False)
        # Use unique service/account к isolate от system keychain
        with pytest.raises(EncryptionKeyError):
            get_or_create_db_key(
                keyring_service="aurora-launch-test-isolated-xyzzy",
                keyring_account="test-key-no-create",
                auto_create=False,
            )


class TestSQLCipherIntegration:
    """ProjectDB с encryption_key — verifies SQLCipher actually encrypts."""

    @pytest.fixture()
    def isolated_key(self, monkeypatch: pytest.MonkeyPatch) -> str:
        key = "c" * 64
        monkeypatch.setenv(ENV_DB_KEY_HEX, key)
        return key

    def test_encrypted_db_opens_with_correct_key(
        self, tmp_path: Path, isolated_key: str
    ) -> None:
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB

        bs = BlobStore(tmp_path / "blobs")
        db = ProjectDB(
            tmp_path / "encrypted.db",
            bs,
            encryption_key=isolated_key,
        )
        try:
            uid = db.create_project("test", aurora_app_version="0.1.0")
            assert uid is not None
        finally:
            db.close()

    def test_encrypted_db_rejects_wrong_key(
        self, tmp_path: Path, isolated_key: str
    ) -> None:
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB

        bs = BlobStore(tmp_path / "blobs")
        # Create encrypted DB with one key
        db = ProjectDB(
            tmp_path / "encrypted.db",
            bs,
            encryption_key=isolated_key,
        )
        db.create_project("test", aurora_app_version="0.1.0")
        db.close()

        # Try к open with different key — should fail at first read
        wrong_key = "d" * 64
        with pytest.raises(Exception):  # sqlcipher raises generic DB error
            db2 = ProjectDB(
                tmp_path / "encrypted.db",
                bs,
                encryption_key=wrong_key,
            )
            try:
                db2.list_projects()
            finally:
                db2.close()

    def test_encrypted_db_file_not_plaintext_readable(
        self, tmp_path: Path, isolated_key: str
    ) -> None:
        """Verify raw file bytes don't contain project name (encryption working)."""
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB

        bs = BlobStore(tmp_path / "blobs")
        db = ProjectDB(
            tmp_path / "encrypted.db",
            bs,
            encryption_key=isolated_key,
        )
        try:
            db.create_project("UNIQUE_CANARY_STRING_FOR_TEST", aurora_app_version="0.1.0")
        finally:
            db.close()

        # Read raw file — encrypted contents should not contain canary
        raw_bytes = (tmp_path / "encrypted.db").read_bytes()
        assert b"UNIQUE_CANARY_STRING_FOR_TEST" not in raw_bytes, (
            "Encrypted DB file contains plaintext project name — encryption not working"
        )

    def test_unencrypted_db_still_works(self, tmp_path: Path) -> None:
        """Backward compat: encryption_key=None uses plain sqlite3."""
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB

        bs = BlobStore(tmp_path / "blobs")
        db = ProjectDB(tmp_path / "plain.db", bs)  # no encryption_key
        try:
            uid = db.create_project("plain", aurora_app_version="0.1.0")
            assert uid is not None
        finally:
            db.close()


class TestClearKeychainKey:
    def test_clear_nonexistent_returns_false(self) -> None:
        # Use isolated service name
        result = clear_keychain_key(
            keyring_service="aurora-launch-test-clear-xyzzy",
            keyring_account="never-set",
        )
        assert result is False
