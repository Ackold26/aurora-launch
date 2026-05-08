"""Aurora Launch schema registry integration (B1 sprint).

Aurora Launch ships sub-schemas (proxy_brand_metadata, transfer_provenance,
recipient_anchors, forecast_horizons, methodology_certificate_ref) что live
alongside Phase A C6 BundleManifest в bundle structure (composition pattern,
per H-Audit-6).

Phase A C6 SchemaRegistry handles ManifestV3 = "3.0". Aurora Launch sub-schemas
have own versioning (`aurora_launch_schema_version` field в bundle metadata).

This module:
1. Registers Aurora Launch sub-schemas с C6 registry (additive, no migration yet)
2. Maintains forward-only BFS migration graph для Aurora Launch sub-schema versions
3. Documents migration pattern для Phase B+ schema evolution (v1.0 → v1.1+)

Current registered Aurora Launch schemas:
- aurora_launch_metadata v1.0 (B0.5 ships AuroraLaunchBundleMetadata + ProxyBrandMetadata)

Phase B+ may add:
- aurora_launch_metadata v1.1 (when TransferProvenance / RecipientAnchors ship)
- aurora_launch_metadata v2.0 (breaking change, e.g., schema restructure)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from aurora_launch.schemas.bundle import AuroraLaunchBundleMetadata


# Type alias: migration takes bundle dict, returns transformed bundle dict
LaunchMigrationFn = Callable[[dict], dict]


@dataclass(frozen=True)
class LaunchMigration:
    """Forward migration for Aurora Launch sub-schema versions.

    Mirrors C6 SchemaRegistry.Migration pattern but scoped к
    `aurora_launch_metadata` sub-schema versions (independent of platform
    BundleManifest schema_version).
    """

    from_version: str
    to_version: str
    migrate: LaunchMigrationFn
    description: str = ""


@dataclass
class LaunchSchemaRegistry:
    """Aurora Launch sub-schema registry with BFS migration pathfinding.

    Forward-only DAG (per Phase A C6 H2 audit pattern). Backward migrations
    not supported — Aurora Launch evolves additive.
    """

    _migrations: dict[tuple[str, str], LaunchMigration] = field(default_factory=dict)
    _known_versions: set[str] = field(default_factory=lambda: {"1.0"})
    _current_version: str = "1.0"

    def register_migration(self, migration: LaunchMigration) -> None:
        """Register forward migration. Raises ValueError on duplicate registration."""
        key = (migration.from_version, migration.to_version)
        if key in self._migrations:
            raise ValueError(
                f"Aurora Launch migration {key[0]} -> {key[1]} already registered"
            )
        self._migrations[key] = migration
        self._known_versions.add(migration.from_version)
        self._known_versions.add(migration.to_version)

    def find_migration_path(
        self, from_version: str, to_version: str
    ) -> list[LaunchMigration]:
        """BFS shortest forward path from_version → to_version.

        Returns ordered migration list. Empty list if from == to.
        Raises ValueError if no path exists или backward attempted.
        """
        if from_version == to_version:
            return []

        if from_version not in self._known_versions:
            raise ValueError(
                f"Unknown Aurora Launch schema version: {from_version!r}. "
                f"Known: {sorted(self._known_versions)}"
            )
        if to_version not in self._known_versions:
            raise ValueError(
                f"Unknown Aurora Launch schema version: {to_version!r}. "
                f"Known: {sorted(self._known_versions)}"
            )

        # BFS forward DAG search
        visited: set[str] = {from_version}
        queue: deque[tuple[str, list[LaunchMigration]]] = deque([(from_version, [])])

        while queue:
            current, path = queue.popleft()
            if current == to_version:
                return path
            for (src, dst), migration in self._migrations.items():
                if src == current and dst not in visited:
                    visited.add(dst)
                    queue.append((dst, path + [migration]))

        raise ValueError(
            f"No Aurora Launch migration path from {from_version!r} to {to_version!r}. "
            f"Available: {sorted((m.from_version, m.to_version) for m in self._migrations.values())}"
        )

    def migrate_to_latest(
        self, metadata: dict, target_version: Optional[str] = None
    ) -> dict:
        """Apply forward migration path. Returns new dict.

        Adds `aurora_launch_migration_history` list field tracking applied
        migrations (для audit trail per Phase A C6 H8 pattern).
        """
        target = target_version or self._current_version
        current = metadata.get("aurora_launch_schema_version", "1.0")

        path = self.find_migration_path(current, target)
        if not path:
            return metadata

        result = dict(metadata)
        history = list(result.get("aurora_launch_migration_history", []))

        for migration in path:
            result = migration.migrate(result)
            history.append({
                "from": migration.from_version,
                "to": migration.to_version,
                "description": migration.description,
            })

        result["aurora_launch_schema_version"] = target
        result["aurora_launch_migration_history"] = history
        return result

    def list_versions(self) -> list[str]:
        """Returns sorted list of registered versions."""
        return sorted(self._known_versions)


def build_default_launch_registry() -> LaunchSchemaRegistry:
    """Constructs registry с all Aurora Launch migrations registered.

    Phase B v0.1.x — only v1.0 base schema, no migrations yet.
    Phase B+ will register v1.0 → v1.1 → v2.0+ paths as schemas evolve.
    """
    registry = LaunchSchemaRegistry()
    # Future: register_all_launch_migrations(registry)
    return registry


# Bridge to Phase A C6 SchemaRegistry — register Aurora Launch sub-schema indicator.
# Aurora Launch metadata lives alongside BundleManifest, not within it.
# C6 registry knows about platform manifest_v3.0; Aurora Launch metadata
# version tracked separately в bundle's `aurora_launch_metadata` field.
def get_aurora_launch_metadata_class() -> type[AuroraLaunchBundleMetadata]:
    """Returns the Pydantic model class для current Aurora Launch metadata version."""
    return AuroraLaunchBundleMetadata
