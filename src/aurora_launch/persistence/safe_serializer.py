"""Blob serialization: msgpack + Ed25519 signing (2026-05-14).

Replaces pickle as the wire format for all blob store content. Hard-cut policy:
legacy pickle blobs are detected and rejected — no fallback deserialization.

Public API:
    serialize(obj)        -> bytes           # msgpack-encoded
    deserialize(data)     -> object          # msgpack-decoded
    sign_blob(data, key)  -> bytes           # 64-byte Ed25519 sig || data
    verify_blob(signed, key) -> bytes        # verifies sig; returns raw data

Detection:
    is_pickle_magic(data) -> bool            # True if data looks like pickle

Numpy support:
    Custom msgpack ext hooks encode ndarray as (shape, dtype_str, raw bytes).
    Roundtrip preserves dtype and values exactly; no string encoding of floats.

Dev keypair:
    DEV_PRIVATE_KEY / DEV_PUBLIC_KEY — Ed25519 keypair generated at first import,
    cached for the process lifetime. Production code replaces with keypair from
    Veracrypt container.

Per INV-05: crypto invariant — attack scenario tests written first.
Per feedback_silent_error_swallowing: explicit narrow excepts, no bare pass.
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache
from typing import Any

import msgpack
import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class SafeSerializerError(RuntimeError):
    """Base for all safe_serializer failures."""


class BlobSignatureError(SafeSerializerError):
    """Raised when Ed25519 signature verification fails (tampered or wrong key)."""


class BlobLegacyFormatError(SafeSerializerError):
    """Raised when legacy pickle content is detected.

    Hard-cut policy: no read-pickle fallback.
    Message instructs user how to recover.
    """


# ---------------------------------------------------------------------------
# Magic-byte detection
# ---------------------------------------------------------------------------

# Pickle protocol magic bytes:
#   \x80\x02 .. \x80\x05  (protocols 2-5, most common)
#   \x80\x00 \x80\x01      (protocols 0-1 encoded with protocol byte)
# The common prefix for pickle protocol ≥ 2 is b'\x80' followed by
# protocol number 0x00..0x05.
_PICKLE_PROTO_MAGIC = b"\x80"

# msgpack fixmap (0x80..0x8f), fixarray (0x90..0x9f), or uint8 (0xcc..),
# or positive fixint (0x00..0x7f), nil (0xc0), etc.
# The key insight: pickle always starts with 0x80 followed by a byte 0x00..0x05
# (the protocol number). msgpack dict starts 0x81..0x8f (fixmap) or 0xde/0xdf
# (map16/map32). msgpack array: 0x90..0x9f / 0xdc/0xdd.
# We detect pickle by checking: first byte == 0x80 AND second byte in 0x00..0x05.
_PICKLE_PROTO_RANGE = frozenset(range(6))  # protocols 0–5


def is_pickle_magic(data: bytes) -> bool:
    """Return True if data starts with a pickle protocol magic sequence."""
    if len(data) < 2:
        return False
    return data[0] == 0x80 and data[1] in _PICKLE_PROTO_RANGE


# Signature length: Ed25519 produces 64-byte signatures.
_SIG_LEN = 64

# ---------------------------------------------------------------------------
# Numpy msgpack extension type
# ---------------------------------------------------------------------------

_NUMPY_EXT_TYPE = 1  # custom ext type code


def _pack_ndarray(arr: np.ndarray) -> bytes:
    """Encode numpy array as msgpack bytes: shape + dtype_str + raw data."""
    dtype_str = arr.dtype.str.encode("ascii")  # e.g. b'<f8'
    shape_packed = msgpack.packb(list(arr.shape), use_bin_type=True)
    raw = arr.tobytes(order="C")
    # Frame: 4-byte shape_len | shape_packed | 1-byte dtype_len | dtype_str | raw
    buf = io.BytesIO()
    sl = len(shape_packed)
    buf.write(sl.to_bytes(4, "big"))
    buf.write(shape_packed)
    dl = len(dtype_str)
    buf.write(dl.to_bytes(1, "big"))
    buf.write(dtype_str)
    buf.write(raw)
    return buf.getvalue()


def _unpack_ndarray(data: bytes) -> np.ndarray:
    """Decode ndarray from bytes produced by _pack_ndarray."""
    view = memoryview(data)
    pos = 0
    sl = int.from_bytes(view[pos : pos + 4], "big")
    pos += 4
    shape = msgpack.unpackb(bytes(view[pos : pos + sl]), raw=False)
    pos += sl
    dl = int.from_bytes(view[pos : pos + 1], "big")
    pos += 1
    dtype_str = bytes(view[pos : pos + dl]).decode("ascii")
    pos += dl
    dtype = np.dtype(dtype_str)
    raw = bytes(view[pos:])
    arr = np.frombuffer(raw, dtype=dtype).reshape(shape)
    return arr.copy()  # copy so result owns its memory (frombuffer is read-only)


def _default_encoder(obj: Any) -> msgpack.ExtType:
    """msgpack default hook: encode numpy arrays as ExtType."""
    if isinstance(obj, np.ndarray):
        return msgpack.ExtType(_NUMPY_EXT_TYPE, _pack_ndarray(obj))
    raise TypeError(f"Unknown type: {type(obj)!r}")


def _ext_hook(code: int, data: bytes) -> Any:
    """msgpack ext_hook: decode numpy arrays."""
    if code == _NUMPY_EXT_TYPE:
        return _unpack_ndarray(data)
    return msgpack.ExtType(code, data)  # passthrough unknown ext types


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize(obj: Any) -> bytes:
    """Encode obj to msgpack bytes. Supports numpy arrays via ext hooks.

    Raises TypeError if obj contains un-encodable types.
    """
    return msgpack.packb(obj, default=_default_encoder, use_bin_type=True)


def deserialize(data: bytes) -> Any:
    """Decode msgpack bytes back to Python object.

    Raises:
        BlobLegacyFormatError: if data looks like pickle.
        ValueError: if data is empty.
        msgpack.UnpackValueError / msgpack.ExtraData: on corrupt msgpack.
    """
    if not data:
        raise ValueError("Cannot deserialize empty bytes")
    if is_pickle_magic(data):
        raise BlobLegacyFormatError(
            "Legacy pickle blobs unsupported в v0.1.0+. "
            "Re-import project from .aurora bundle."
        )
    return msgpack.unpackb(data, ext_hook=_ext_hook, raw=False)


# ---------------------------------------------------------------------------
# Ed25519 signing
# ---------------------------------------------------------------------------


def sign_blob(data: bytes, private_key: Ed25519PrivateKey) -> bytes:
    """Sign data with Ed25519; return 64-byte signature || data.

    Raises TypeError if private_key is not an Ed25519PrivateKey.
    """
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError(
            f"sign_blob expects Ed25519PrivateKey, got {type(private_key).__name__}"
        )
    sig = private_key.sign(data)  # 64 bytes
    assert len(sig) == _SIG_LEN  # invariant: Ed25519 always 64 bytes
    return sig + data


def verify_blob(signed_data: bytes, public_key: Ed25519PublicKey) -> bytes:
    """Verify Ed25519 signature; return raw (unsigned) data.

    Layout: first 64 bytes = signature, rest = data.

    Raises:
        BlobSignatureError: if signature is invalid, truncated, or wrong key.
        ValueError: if signed_data is empty.
    """
    if not signed_data:
        raise ValueError("Cannot verify empty signed blob")
    if len(signed_data) < _SIG_LEN:
        raise BlobSignatureError(
            f"Signed blob too short: {len(signed_data)} bytes "
            f"(minimum {_SIG_LEN} for signature header)"
        )
    sig = signed_data[:_SIG_LEN]
    data = signed_data[_SIG_LEN:]
    try:
        public_key.verify(sig, data)
    except InvalidSignature as exc:
        raise BlobSignatureError("Ed25519 signature verification failed") from exc
    return data


# ---------------------------------------------------------------------------
# Dev keypair (process-cached; production replaces with Veracrypt keypair)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_dev_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate (or return cached) dev Ed25519 keypair.

    Called at first use; cached for process lifetime via lru_cache.
    Production code replaces DEV_PRIVATE_KEY / DEV_PUBLIC_KEY references
    with keypair loaded from Veracrypt container.
    """
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    _log.debug(
        "Generated dev Ed25519 keypair (ephemeral — process scope only). "
        "Replace with persistent keypair for production."
    )
    return private, public


def _dev_private_key() -> Ed25519PrivateKey:
    return _get_dev_keypair()[0]


def _dev_public_key() -> Ed25519PublicKey:
    return _get_dev_keypair()[1]
