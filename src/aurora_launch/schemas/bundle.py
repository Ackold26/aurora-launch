"""Aurora Launch bundle metadata composition (B1 schema integration).

H-Audit-6 fix: spec/code alignment. PHASE_B_REQUIREMENTS.md §4.2.4 originally
declared `ManifestV3Launch extends ManifestV3` (inheritance). Aurora Platform
Core C6 `BundleManifest` is FrozenModel (extra="forbid") — direct field
extension via subclass conflicts с platform constraints.

Pattern (composition over inheritance):
- Phase A C6 BundleManifest stays as platform base (manifest.json)
- Aurora Launch–specific metadata lives в `aurora_launch_metadata.json`
  alongside в bundle directory
- Both files referenced via bundle_layout_id «aurora_launch_proxy_intake_v1»
- Schema registry handles загрузку обоих consistently

Public API: `AuroraLaunchBundleMetadata` aggregates все Aurora Launch–
specific fields. В Phase B+ when real .aurora ZIP container ships (replacing
v0.1.0-b05 .aurora.json intermediate), this metadata file becomes
`aurora_launch_metadata.json` entry в ZIP.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from aurora_launch.schemas.proxy import ProxyBrandMetadata


class AuroraLaunchBundleMetadata(BaseModel):
    """Aggregates Aurora Launch–specific bundle metadata.

    Composed alongside Phase A C6 `BundleManifest` (not inherited).
    Future Phase B+ extensions (TransferProvenance / RecipientAnchors /
    ForecastHorizons / MethodologyCertificateRef) added here as they ship
    в B3-B5 sprints.

    H-A2-5 fix: `aurora_launch_version` is Optional с default — allows reading
    legacy bundles where field may be absent. Strict version check happens
    via aurora-launch-reproduce CLI which has explicit version skew warning.

    M-A2-4 fix: model_config matches Phase A C6 FrozenModel pattern (frozen,
    extra=forbid, validate_assignment). Bundle metadata = persisted artifact,
    immutability post-construction prevents accidental mutation в runtime.
    `extra=forbid` catches typos в field names при Phase B+ extensions.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    schema_version: str = "3.0"
    aurora_launch_version: Optional[str] = None  # H-A2-5: Optional для legacy bundle reads

    # B1 — primary fields (B0.5 ships ProxyBrandMetadata; others Phase B+ sprints)
    proxy_brand_metadata: Optional[ProxyBrandMetadata] = None

    # Phase B+ extension hooks — populated по мере shipping sprints
    # transfer_provenance: Optional[TransferProvenance] = None  # B3
    # recipient_anchors: Optional[RecipientAnchors] = None      # B3
    # forecast_horizons: Optional[ForecastHorizons] = None      # B4
    # methodology_certificate_ref: Optional[MethodologyCertificateRef] = None  # B4
