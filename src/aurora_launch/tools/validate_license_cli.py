"""aurora-launch-validate-license CLI — diagnostic tool for license state.

Block 1B — surfaces current LaunchLicenseValidator state без UI integration.
Used during pilot rollout to debug license issues и by Customer Success Lite
log entries.

Output is human-readable text (default) or JSON (--json flag for scripting).
"""

from __future__ import annotations

import json
import sys

import click

from aurora_launch import __version__
from aurora_launch.engines.license_validator import (
    FEATURE_LAUNCH_PROXY_MULTI,
    FEATURE_LAUNCH_PROXY_SINGLE,
    FEATURE_METHODOLOGY_CERT,
    FEATURE_WHITE_LABEL,
    HAS_PLATFORM_CORE,
    LaunchLicenseValidator,
    LicenseState,
)


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Output JSON instead of text.")
@click.version_option(version=__version__)
def main(as_json: bool) -> None:
    """Show current Aurora Launch license status from env / cache.

    Reads AURORA_PLATFORM_URL, AURORA_PUBLIC_VERIFY_KEY_PEM,
    AURORA_LICENSE_CACHE_PATH, AURORA_MACHINE_ID. Honors
    AURORA_LAUNCH_LICENSE_BYPASS=1 dev override.
    """
    validator = LaunchLicenseValidator.from_env()
    status = validator.current_status()

    features_to_probe = [
        FEATURE_LAUNCH_PROXY_SINGLE,
        FEATURE_LAUNCH_PROXY_MULTI,
        FEATURE_METHODOLOGY_CERT,
        FEATURE_WHITE_LABEL,
    ]
    feature_results = {f: status.has_feature(f) for f in features_to_probe}

    if as_json:
        out = {
            "has_platform_core": HAS_PLATFORM_CORE,
            "state": status.state.value,
            "tier": status.tier,
            "user_id": status.user_id,
            "license_id": status.license_id,
            "seat_id": status.seat_id,
            "is_offline_grace": status.is_offline_grace,
            "valid_until": status.valid_until.isoformat() if status.valid_until else None,
            "expires_at": status.expires_at.isoformat() if status.expires_at else None,
            "detail": status.detail,
            "features": feature_results,
        }
        click.echo(json.dumps(out, indent=2))
    else:
        click.echo(f"Aurora Launch v{__version__} — license diagnostic")
        click.echo(f"Platform-core available: {HAS_PLATFORM_CORE}")
        click.echo("")
        click.echo(f"State:        {status.state.value}")
        if status.tier:
            click.echo(f"Tier:         {status.tier}")
        if status.user_id:
            click.echo(f"User:         {status.user_id}")
        if status.license_id:
            click.echo(f"License ID:   {status.license_id}")
        if status.seat_id:
            click.echo(f"Seat ID:      {status.seat_id}")
        if status.is_offline_grace:
            click.echo(f"Offline grace: ACTIVE")
        if status.valid_until:
            click.echo(f"Valid until:  {status.valid_until.isoformat()}")
        if status.detail:
            click.echo(f"Detail:       {status.detail}")
        click.echo("")
        click.echo("Feature gates:")
        for name, granted in feature_results.items():
            mark = "✓" if granted else "✗"
            click.echo(f"  {mark} {name}")

    # Exit code: 0 if usable license, 1 if degraded/invalid/expired, 2 if no license
    if status.state in (LicenseState.ACTIVE, LicenseState.GRACE):
        sys.exit(0)
    if status.state == LicenseState.NO_LICENSE:
        sys.exit(2)
    sys.exit(1)


if __name__ == "__main__":
    main()
