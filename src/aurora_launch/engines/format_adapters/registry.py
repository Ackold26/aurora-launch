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
    """Plug-in registry для format adapters.

    Auto-detection: `detect(file_path)` returns first matching adapter
    или None. Registration: `register(adapter)` adds custom adapter.

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
    """
    from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
    from aurora_launch.engines.format_adapters.mediascope_adex import MediascopeAdExAdapterV1

    registry = AdapterRegistry()
    registry.register(DsmAdapterV2024())
    registry.register(MediascopeAdExAdapterV1())
    return registry
