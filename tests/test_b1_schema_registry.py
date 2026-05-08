"""Tests for B1 sprint deliverables — schema registry + migration framework."""

from __future__ import annotations

import pytest

from aurora_launch.engines.schema_registry_launch import (
    LaunchMigration,
    LaunchSchemaRegistry,
    build_default_launch_registry,
)


class TestLaunchSchemaRegistry:
    def test_default_registry_has_v1_0(self) -> None:
        reg = build_default_launch_registry()
        assert "1.0" in reg.list_versions()

    def test_self_path_empty(self) -> None:
        reg = build_default_launch_registry()
        path = reg.find_migration_path("1.0", "1.0")
        assert path == []

    def test_unknown_version_raises(self) -> None:
        reg = build_default_launch_registry()
        with pytest.raises(ValueError, match="Unknown"):
            reg.find_migration_path("1.0", "9.9")

    def test_register_migration_extends_registry(self) -> None:
        reg = LaunchSchemaRegistry()

        def _stub_migrate(b: dict) -> dict:
            return {**b, "new_field": "added"}

        reg.register_migration(LaunchMigration(
            from_version="1.0",
            to_version="1.1",
            migrate=_stub_migrate,
            description="Phase B+ stub: add new_field",
        ))

        assert "1.1" in reg.list_versions()
        path = reg.find_migration_path("1.0", "1.1")
        assert len(path) == 1
        assert path[0].from_version == "1.0"
        assert path[0].to_version == "1.1"

    def test_bfs_finds_shortest_path(self) -> None:
        """BFS picks shortest path when multiple exist."""
        reg = LaunchSchemaRegistry()

        # Direct path 1.0 → 1.2
        reg.register_migration(LaunchMigration("1.0", "1.2", lambda b: b, "direct"))
        # Indirect path 1.0 → 1.1 → 1.2
        reg.register_migration(LaunchMigration("1.0", "1.1", lambda b: b, "step1"))
        reg.register_migration(LaunchMigration("1.1", "1.2", lambda b: b, "step2"))

        path = reg.find_migration_path("1.0", "1.2")
        # BFS should pick direct (1 hop) over indirect (2 hops)
        assert len(path) == 1

    def test_no_path_raises(self) -> None:
        """If versions exist but no path connects them — raises."""
        reg = LaunchSchemaRegistry()
        reg.register_migration(LaunchMigration("2.0", "2.1", lambda b: b, ""))
        # 2.0 and 2.1 are now known. 1.0 is also known (default). But no path 1.0→2.0.
        with pytest.raises(ValueError, match="No Aurora Launch migration path"):
            reg.find_migration_path("1.0", "2.0")

    def test_migrate_applies_path_in_order(self) -> None:
        """migrate_to_latest applies migrations sequentially + tracks history."""
        reg = LaunchSchemaRegistry()
        reg.register_migration(LaunchMigration(
            from_version="1.0",
            to_version="1.1",
            migrate=lambda b: {**b, "field_v1_1": "added"},
            description="add v1.1 field",
        ))
        reg.register_migration(LaunchMigration(
            from_version="1.1",
            to_version="1.2",
            migrate=lambda b: {**b, "field_v1_2": "added"},
            description="add v1.2 field",
        ))

        original = {"aurora_launch_schema_version": "1.0", "data": "original"}
        result = reg.migrate_to_latest(original, target_version="1.2")

        # Both migrations applied
        assert result["field_v1_1"] == "added"
        assert result["field_v1_2"] == "added"
        assert result["aurora_launch_schema_version"] == "1.2"
        # History preserved
        history = result["aurora_launch_migration_history"]
        assert len(history) == 2
        assert history[0]["from"] == "1.0" and history[0]["to"] == "1.1"
        assert history[1]["from"] == "1.1" and history[1]["to"] == "1.2"

    def test_migrate_to_same_version_noop(self) -> None:
        """target_version == current_version → no-op (input returned unchanged)."""
        reg = build_default_launch_registry()
        original = {"aurora_launch_schema_version": "1.0", "data": "x"}
        result = reg.migrate_to_latest(original, target_version="1.0")
        assert result == original

    def test_round_trip_preservation(self) -> None:
        """v1.0 → v1.1 → migrate result preserves all v1.0 fields (additive)."""
        reg = LaunchSchemaRegistry()
        reg.register_migration(LaunchMigration(
            from_version="1.0",
            to_version="1.1",
            migrate=lambda b: {**b, "new_field": "added"},
            description="additive field",
        ))

        original = {
            "aurora_launch_schema_version": "1.0",
            "important_data": [1, 2, 3],
            "nested": {"key": "value"},
        }
        migrated = reg.migrate_to_latest(original, target_version="1.1")

        # All v1.0 fields preserved
        assert migrated["important_data"] == [1, 2, 3]
        assert migrated["nested"] == {"key": "value"}
        # New field added
        assert migrated["new_field"] == "added"
