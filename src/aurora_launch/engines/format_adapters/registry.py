"""Adapter Registry — auto-detection + plug-in extensibility.

Per PHASE_B_REQUIREMENTS.md §4.1.5 — `AdapterRegistry`.
"""

from __future__ import annotations

from pathlib import Path

from aurora_launch.schemas.synthetic_corpus import (
    FormatAdapterContract,
    ProxyDataSource,
)


class AdapterRegistry:
    """Plug-in registry for format adapters.

    Auto-detection: `detect(file_path)` returns first matching adapter
    or None. Registration: `register(adapter)` adds custom adapter.

    Built-in adapters auto-registered at module import via __init__.py.
    """

    def __init__(self) -> None:
        self._adapters: list[ProxyDataSource] = []

    def register(self, adapter: ProxyDataSource) -> None:
        """Register a new adapter. Idempotent — duplicate adapter_id replaces."""
        contract = adapter.get_metadata()
        # Remove existing с same adapter_id
        self._adapters = [
            a for a in self._adapters if a.get_metadata().adapter_id != contract.adapter_id
        ]
        self._adapters.append(adapter)

    def detect(self, file_path: str | Path) -> ProxyDataSource | None:
        """Returns first adapter matching file. None if no match.

        Priority: order of registration (newer adapters first via reverse iteration).
        """
        path_str = str(file_path)
        # Reverse order — custom adapters (registered later) take precedence
        for adapter in reversed(self._adapters):
            if adapter.detect(path_str):
                return adapter
        return None

    def list_adapters(self) -> list[FormatAdapterContract]:
        """Returns metadata for all registered adapters."""
        return [a.get_metadata() for a in self._adapters]

    def get_by_id(self, adapter_id: str) -> ProxyDataSource | None:
        """Lookup adapter by id."""
        for a in self._adapters:
            if a.get_metadata().adapter_id == adapter_id:
                return a
        return None


def build_default_registry() -> AdapterRegistry:
    """Constructs registry with all built-in adapters registered.

    Used by application startup. Returns fresh registry instance.

    Order matters: more-specific adapters registered LAST so они take priority
    в `detect()` (which iterates reversed). DSM V2024 most common — registered
    last to win ties. V2023 / V2025 specific year-string detection avoids
    collisions.
    """
    from aurora_launch.engines.format_adapters.dsm_v2023 import DsmAdapterV2023
    from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
    from aurora_launch.engines.format_adapters.dsm_v2025 import DsmAdapterV2025
    from aurora_launch.engines.format_adapters.mediascope_adex import MediascopeAdExAdapterV1
    from aurora_launch.engines.format_adapters.mediascope_tv_index import (
        MediascopeTvIndexAdapterV1,
    )

    registry = AdapterRegistry()
    # DSM family — V2023 first (legacy), V2025 (forward-compat), V2024 last (most common)
    registry.register(DsmAdapterV2023())
    registry.register(DsmAdapterV2025())
    registry.register(DsmAdapterV2024())
    # Mediascope family — AdEx + TV Index
    registry.register(MediascopeAdExAdapterV1())
    registry.register(MediascopeTvIndexAdapterV1())
    return registry
