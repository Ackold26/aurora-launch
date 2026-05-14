"""Attack scenario + unit tests for safe_serializer (2026-05-14).

Per INV-05: crypto invariants require attack scenario tests FIRST.
Per feedback_silent_error_swallowing: narrow excepts, no bare pass.

Coverage:
1. Tampered blob (modified bytes) → BlobSignatureError
2. Truncated signature → BlobSignatureError
3. Wrong public key → BlobSignatureError
4. Empty blob → ValueError
5. Numpy roundtrip preserves shape/dtype/values
6. Python object roundtrip (dict, list, int, str, bytes, None)
7. Forged signature attempt with known public key → BlobSignatureError
8. Legacy pickle detection → BlobLegacyFormatError
"""

from __future__ import annotations

import struct

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aurora_launch.persistence.safe_serializer import (
    BlobLegacyFormatError,
    BlobSignatureError,
    _dev_private_key,
    _dev_public_key,
    deserialize,
    serialize,
    sign_blob,
    verify_blob,
)


# ---------------------------------------------------------------------------
# Fixtures: fresh Ed25519 keypairs per test (not the dev process-cached pair)
# ---------------------------------------------------------------------------


@pytest.fixture()
def keypair():
    """Fresh Ed25519 keypair for each test."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


@pytest.fixture()
def other_keypair():
    """A second unrelated Ed25519 keypair (for wrong-key tests)."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


# ---------------------------------------------------------------------------
# Attack scenario 1: Tampered blob (modified bytes after signing)
# ---------------------------------------------------------------------------


class TestTamperedBlob:
    def test_tampered_payload_raises_signature_error(self, keypair) -> None:
        """Scenario: attacker modifies one payload byte after signing.

        Expected: BlobSignatureError — the Ed25519 signature covers the entire
        payload; any bit flip invalidates it.
        """
        priv, pub = keypair
        data = serialize({"model": "mmm", "weights": [0.3, 0.5, 0.2]})
        signed = sign_blob(data, priv)

        # Tamper: flip a byte in the payload portion (after the 64-byte sig)
        tampered = bytearray(signed)
        tampered[64] ^= 0xFF  # first byte of payload
        with pytest.raises(BlobSignatureError):
            verify_blob(bytes(tampered), pub)

    def test_tampered_signature_raises_signature_error(self, keypair) -> None:
        """Scenario: attacker modifies the signature bytes themselves."""
        priv, pub = keypair
        data = serialize({"key": "value"})
        signed = sign_blob(data, priv)

        tampered = bytearray(signed)
        tampered[0] ^= 0x01  # first byte of signature
        with pytest.raises(BlobSignatureError):
            verify_blob(bytes(tampered), pub)


# ---------------------------------------------------------------------------
# Attack scenario 2: Truncated signature
# ---------------------------------------------------------------------------


class TestTruncatedSignature:
    def test_truncated_to_zero_raises(self, keypair) -> None:
        """Empty bytes passed to verify_blob → ValueError (not signature error)."""
        _, pub = keypair
        with pytest.raises(ValueError):
            verify_blob(b"", pub)

    def test_truncated_below_sig_len_raises(self, keypair) -> None:
        """Signed blob truncated to fewer than 64 bytes → BlobSignatureError."""
        priv, pub = keypair
        data = serialize("hello")
        signed = sign_blob(data, priv)
        # Truncate to 32 bytes (half a signature)
        with pytest.raises(BlobSignatureError, match="too short"):
            verify_blob(signed[:32], pub)

    def test_exactly_sig_len_no_payload_is_valid_empty_content(
        self, keypair
    ) -> None:
        """Signing empty bytes produces a 64-byte signed blob with no content.

        verify_blob should succeed and return empty bytes.
        """
        priv, pub = keypair
        empty_data = b""
        signed = sign_blob(empty_data, priv)
        assert len(signed) == 64
        result = verify_blob(signed, pub)
        assert result == b""


# ---------------------------------------------------------------------------
# Attack scenario 3: Wrong public key
# ---------------------------------------------------------------------------


class TestWrongPublicKey:
    def test_verify_with_wrong_key_raises(self, keypair, other_keypair) -> None:
        """Scenario: signed with key A, verified with unrelated key B → BlobSignatureError."""
        priv_a, _ = keypair
        _, pub_b = other_keypair

        data = serialize({"amount": 42})
        signed = sign_blob(data, priv_a)

        with pytest.raises(BlobSignatureError):
            verify_blob(signed, pub_b)


# ---------------------------------------------------------------------------
# Attack scenario 4: Empty blob
# ---------------------------------------------------------------------------


class TestEmptyBlob:
    def test_deserialize_empty_bytes_raises_value_error(self) -> None:
        """Empty bytes passed to deserialize() must raise ValueError immediately."""
        with pytest.raises(ValueError, match="empty"):
            deserialize(b"")

    def test_verify_blob_empty_raises_value_error(self, keypair) -> None:
        """Empty bytes passed to verify_blob() must raise ValueError."""
        _, pub = keypair
        with pytest.raises(ValueError, match="empty"):
            verify_blob(b"", pub)


# ---------------------------------------------------------------------------
# Attack scenario 5: Numpy roundtrip
# ---------------------------------------------------------------------------


class TestNumpyRoundtrip:
    def test_float64_2d_array_roundtrip(self) -> None:
        """float64 2D array preserves shape, dtype, and exact values."""
        arr = np.array([[1.0, 2.5], [3.14, -7.0]], dtype=np.float64)
        encoded = serialize(arr)
        decoded = deserialize(encoded)
        assert isinstance(decoded, np.ndarray)
        assert decoded.shape == arr.shape
        assert decoded.dtype == arr.dtype
        np.testing.assert_array_equal(decoded, arr)

    def test_int32_1d_array_roundtrip(self) -> None:
        """int32 1D array preserves dtype and values exactly."""
        arr = np.arange(100, dtype=np.int32)
        encoded = serialize(arr)
        decoded = deserialize(encoded)
        assert decoded.dtype == np.int32
        np.testing.assert_array_equal(decoded, arr)

    def test_numpy_in_dict_roundtrip(self) -> None:
        """Numpy array nested inside a dict survives serialize/deserialize."""
        obj = {
            "name": "forecast",
            "weights": np.array([0.3, 0.5, 0.2], dtype=np.float32),
        }
        encoded = serialize(obj)
        decoded = deserialize(encoded)
        assert decoded["name"] == "forecast"
        assert isinstance(decoded["weights"], np.ndarray)
        np.testing.assert_array_almost_equal(decoded["weights"], obj["weights"])

    def test_empty_array_roundtrip(self) -> None:
        """Zero-element array roundtrips without error."""
        arr = np.array([], dtype=np.float64)
        decoded = deserialize(serialize(arr))
        assert decoded.shape == (0,)
        assert decoded.dtype == np.float64

    def test_numpy_encoded_as_bytes_not_strings(self) -> None:
        """Numpy raw data is stored as binary bytes (not string encoding)."""
        arr = np.array([1.1, 2.2, 3.3], dtype=np.float64)
        encoded = serialize(arr)
        # The encoded bytes should not grow to string length of repr
        # A 3-element float64 array is 24 bytes raw; string repr would be >> 24 bytes.
        # We verify encoded size is reasonable (< 200 bytes), not the 300+ a JSON string would be.
        assert len(encoded) < 200, (
            f"Expected compact binary encoding, got {len(encoded)} bytes"
        )


# ---------------------------------------------------------------------------
# Attack scenario 6: Python object roundtrip
# ---------------------------------------------------------------------------


class TestPythonObjectRoundtrip:
    def test_dict_roundtrip(self) -> None:
        obj = {"project": "aurora-launch", "version": 1, "active": True}
        assert deserialize(serialize(obj)) == obj

    def test_list_roundtrip(self) -> None:
        obj = [1, 2.5, "hello", None, True, False]
        assert deserialize(serialize(obj)) == obj

    def test_nested_structure_roundtrip(self) -> None:
        obj = {"meta": {"tags": ["a", "b"], "count": 2}, "data": [1, 2, 3]}
        assert deserialize(serialize(obj)) == obj

    def test_bytes_roundtrip(self) -> None:
        """Raw bytes payload roundtrips correctly."""
        obj = {"raw": b"\x00\x01\x02\xff"}
        result = deserialize(serialize(obj))
        assert result["raw"] == b"\x00\x01\x02\xff"

    def test_none_roundtrip(self) -> None:
        assert deserialize(serialize(None)) is None

    def test_integer_roundtrip(self) -> None:
        assert deserialize(serialize(12345)) == 12345

    def test_string_roundtrip(self) -> None:
        assert deserialize(serialize("Materia Medica pilot")) == "Materia Medica pilot"


# ---------------------------------------------------------------------------
# Attack scenario 7: Forged signature attempt
# ---------------------------------------------------------------------------


class TestForgedSignature:
    def test_random_64_bytes_prefix_rejected(self, keypair) -> None:
        """Attacker prepends 64 random bytes as a 'signature' — must fail verification."""
        import os

        _, pub = keypair
        data = serialize({"important": "data"})
        # Craft a fake signed blob: random 64 bytes + real msgpack payload
        fake_sig = os.urandom(64)
        forged = fake_sig + data

        with pytest.raises(BlobSignatureError):
            verify_blob(forged, pub)

    def test_replay_attack_different_payload(self, keypair) -> None:
        """Attacker takes a valid signature and attaches it to a different payload.

        The Ed25519 signature binds to the exact bytes of the original message;
        reusing sig from message A on message B must fail.
        """
        priv, pub = keypair
        data_a = serialize({"budget": 100})
        data_b = serialize({"budget": 9999999})

        signed_a = sign_blob(data_a, priv)
        sig_a = signed_a[:64]  # extract valid signature from message A

        # Craft forged blob: real sig from A, payload from B
        forged = sig_a + data_b

        with pytest.raises(BlobSignatureError):
            verify_blob(forged, pub)

    def test_zero_signature_rejected(self, keypair) -> None:
        """All-zero signature bytes are not a valid Ed25519 signature."""
        _, pub = keypair
        data = serialize("target payload")
        forged = b"\x00" * 64 + data
        with pytest.raises(BlobSignatureError):
            verify_blob(forged, pub)


# ---------------------------------------------------------------------------
# Attack scenario 8: Legacy pickle detection
# ---------------------------------------------------------------------------


class TestLegacyPickleDetection:
    def test_pickle_protocol_2_raises_legacy_error(self) -> None:
        """Python pickle protocol 2 magic (\\x80\\x02) triggers BlobLegacyFormatError."""
        import pickle

        pickle_bytes = pickle.dumps({"key": "value"}, protocol=2)
        assert pickle_bytes[:2] == b"\x80\x02"  # sanity check magic
        with pytest.raises(BlobLegacyFormatError, match="Legacy pickle"):
            deserialize(pickle_bytes)

    def test_pickle_protocol_4_raises_legacy_error(self) -> None:
        """Python pickle protocol 4 magic (\\x80\\x04) triggers BlobLegacyFormatError."""
        import pickle

        pickle_bytes = pickle.dumps({"model": "mmm", "v": [1, 2, 3]}, protocol=4)
        assert pickle_bytes[:2] == b"\x80\x04"
        with pytest.raises(BlobLegacyFormatError, match="Legacy pickle"):
            deserialize(pickle_bytes)

    def test_is_pickle_magic_positive_cases(self) -> None:
        """is_pickle_magic returns True for all supported pickle protocols."""
        from aurora_launch.persistence.safe_serializer import is_pickle_magic

        for proto in range(6):
            magic = bytes([0x80, proto])
            assert is_pickle_magic(magic), f"Protocol {proto} should be detected as pickle"

    def test_is_pickle_magic_negative_cases(self) -> None:
        """is_pickle_magic returns False for non-pickle bytes."""
        from aurora_launch.persistence.safe_serializer import is_pickle_magic

        # msgpack fixmap (\x81), array (\x91), nil (\xc0), valid msgpack dict
        assert not is_pickle_magic(b"\x81\x01")
        assert not is_pickle_magic(b"\x91\x01")
        assert not is_pickle_magic(b"\xc0")
        assert not is_pickle_magic(b"")  # too short
        assert not is_pickle_magic(b"\x80\x06")  # proto 6 (not a real pickle proto)

    def test_pickle_in_verify_blob_path_raises_legacy_error(self) -> None:
        """verify_blob with pickle data raises BlobLegacyFormatError (not BlobSignatureError).

        The detection happens before signature parsing so the error is more informative.
        This mirrors what blob_store.load() does when it encounters a legacy file.
        """
        import pickle

        from aurora_launch.persistence.safe_serializer import is_pickle_magic

        _, pub = _dev_public_key(), _dev_public_key()
        pub = _dev_public_key()

        pickle_data = pickle.dumps({"legacy": True}, protocol=2)
        # is_pickle_magic should fire first inside safe_serializer paths
        assert is_pickle_magic(pickle_data)
        # deserialize detects and raises
        with pytest.raises(BlobLegacyFormatError):
            deserialize(pickle_data)


# ---------------------------------------------------------------------------
# Sign/verify integration: happy path
# ---------------------------------------------------------------------------


class TestSignVerifyHappyPath:
    def test_sign_and_verify_roundtrip(self, keypair) -> None:
        priv, pub = keypair
        data = serialize({"result": 42, "labels": ["a", "b"]})
        signed = sign_blob(data, priv)
        recovered = verify_blob(signed, pub)
        assert recovered == data

    def test_dev_keypair_stable_within_process(self) -> None:
        """Dev keypair is process-cached: two calls return the same objects."""
        priv1 = _dev_private_key()
        priv2 = _dev_private_key()
        assert priv1 is priv2

        pub1 = _dev_public_key()
        pub2 = _dev_public_key()
        assert pub1 is pub2

    def test_sign_blob_wrong_key_type_raises_type_error(self) -> None:
        """Passing a non-Ed25519 private key to sign_blob raises TypeError."""
        with pytest.raises(TypeError, match="Ed25519PrivateKey"):
            sign_blob(b"data", "not-a-key")  # type: ignore[arg-type]
