"""Aurora Launch sidecar protocol version contract.

Defines the version negotiation contract between Python sidecar and Rust
Tauri shell. Versioning follows a two-level scheme:

  PROTOCOL_VERSION: (major, minor)
    Semantic: major bump = breaking wire format change (incompatible);
              minor bump = additive (new methods, extra fields — Rust can
              ignore unknown fields safely).
    Current: (1, 0) — initial stable protocol after Block 4 / Phase Scale.

  MIN_COMPATIBLE_RUST: (major, minor, patch)
    Minimum Rust Tauri shell semver required to communicate with this sidecar.
    Used as a floor check — older shells may lack IPC methods or auth handling
    required by this sidecar version.

Compatibility rules (S-18):
  - Protocol major mismatch → INCOMPATIBLE (both directions).
  - Protocol minor: sidecar accepts Rust with same major + any minor
    (Python sidecar is forward-minor-compatible receiver).
  - Rust shell major > MIN_COMPATIBLE_RUST major → sidecar update required
    (binary protocol may have changed under us — ask user to update sidecar).
  - Rust shell major < MIN_COMPATIBLE_RUST major → Rust too old.
  - Rust shell major == MIN_COMPATIBLE_RUST major, minor/patch flexible → compat.

Pure stdlib, no third-party imports.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ─── Protocol version constants ───────────────────────────────────────────────

PROTOCOL_VERSION: tuple[int, int] = (1, 0)
"""Wire protocol version (major, minor).

Bump major when the JSON-RPC framing, auth mechanism, or mandatory method
signatures change in a backwards-incompatible way.  Bump minor when adding
new optional methods or response fields that older Rust shells can ignore.
"""

MIN_COMPATIBLE_RUST: tuple[int, int, int] = (0, 1, 0)
"""Minimum Rust Tauri shell semver that can talk to this sidecar.

Rust shell versions below this floor lack IPC plumbing that the sidecar
relies on (e.g. sidecar stdin injection, auth token env var, event routing).
Keep in sync with Cargo.toml `version` field floor when making Rust changes.
"""

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z\-\.]+)?(?:\+[0-9A-Za-z\-\.]+)?$"
)


# ─── Public helpers ───────────────────────────────────────────────────────────


def parse_semver(version_str: str) -> tuple[int, int, int] | None:
    """Parse 'MAJOR.MINOR.PATCH[-prerelease][+build]' → (major, minor, patch).

    Returns None on invalid input instead of raising, so callers can produce
    user-friendly error messages rather than unhandled exceptions.
    """
    m = _SEMVER_RE.match(version_str.strip())
    if m is None:
        return None
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")))


def compatible(rust_semver: tuple[int, int, int]) -> bool:
    """Return True if the Rust shell version is compatible with this sidecar.

    Compatibility rules (see module docstring for rationale):
      1. rust_semver < MIN_COMPATIBLE_RUST → False (Rust too old — full tuple comparison)
      2. rust_major > MIN_COMPATIBLE_RUST.major → False (sidecar too old; breaking protocol)
      3. rust_semver >= MIN_COMPATIBLE_RUST AND same major → True

    Full-tuple floor check handles the pre-1.0 case: when major == 0 minor bumps
    CAN be breaking (e.g. MIN=(0,1,0) and Rust=(0,0,5) → incompatible).
    Once major >= 1, only major differences are breaking.

    Note: this predicate is semver-based on the *application* (Tauri shell)
    version, NOT on PROTOCOL_VERSION.  Use negotiate() for the full
    negotiation result with human-readable advice.
    """
    rust_major = rust_semver[0]
    min_major = MIN_COMPATIBLE_RUST[0]
    if rust_major > min_major:
        return False  # sidecar too old
    if rust_semver < MIN_COMPATIBLE_RUST:
        return False  # Rust too old (handles major-0 minor floor)
    return True


def negotiate(rust_version: str) -> dict[str, object]:
    """Version negotiation — called by Rust shell at startup.

    Accepts Rust Tauri shell application version string (semver), returns
    structured negotiation result.

    Args:
        rust_version: semver string, e.g. "0.1.0" or "0.2.0-beta.1".

    Returns dict with:
        compatible: bool
        reason: str | None  — None when compatible
        advice: str | None  — human-readable guidance when incompatible

    Per INV-11: only specific exceptions caught; parse errors surface as
    compatible=False with explicit reason (not silent swallow).
    """
    parsed = parse_semver(rust_version)

    if parsed is None:
        result: dict[str, object] = {
            "compatible": False,
            "reason": "invalid version format",
            "advice": (
                f"Received Rust version string {rust_version!r} which does not "
                "match semver format MAJOR.MINOR.PATCH. "
                "Ensure the Tauri shell passes its Cargo.toml version."
            ),
        }
        logger.warning(
            "negotiate: invalid Rust version string %r — incompatible",
            rust_version,
        )
        return result

    rust_major, rust_minor, rust_patch = parsed
    min_major, min_minor, min_patch = MIN_COMPATIBLE_RUST

    # Full-tuple floor: covers both explicit major-too-old AND the pre-1.0 case
    # where same-major but lower-minor is also breaking (e.g. 0.0.5 < 0.1.0).
    if rust_major < min_major or (rust_major == min_major and parsed < MIN_COMPATIBLE_RUST):
        result = {
            "compatible": False,
            "reason": (
                f"Rust shell v{rust_version} is below minimum required "
                f"v{min_major}.{min_minor}.{min_patch}"
            ),
            "advice": "Update Tauri shell",
        }
        logger.warning(
            "negotiate: Rust shell %s too old (min %d.%d.%d) — incompatible",
            rust_version,
            min_major,
            min_minor,
            min_patch,
        )
        return result

    if rust_major > min_major:
        result = {
            "compatible": False,
            "reason": (
                f"Rust shell v{rust_version} has major version {rust_major} "
                f"which is ahead of sidecar minimum {min_major}. "
                "The Rust shell may have changed the IPC protocol."
            ),
            "advice": "Python sidecar update required",
        }
        logger.warning(
            "negotiate: Rust shell %s major %d > sidecar min major %d — "
            "sidecar update required",
            rust_version,
            rust_major,
            min_major,
        )
        return result

    # Same major — minor/patch differences are forward-compatible.
    result = {
        "compatible": True,
        "reason": None,
        "advice": None,
    }
    logger.info(
        "negotiate: Rust shell %s compatible (protocol %d.%d, min_rust %d.%d.%d)",
        rust_version,
        PROTOCOL_VERSION[0],
        PROTOCOL_VERSION[1],
        min_major,
        min_minor,
        min_patch,
    )
    return result
