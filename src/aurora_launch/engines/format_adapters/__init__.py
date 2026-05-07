"""Format adapters для proxy data ingestion (B0.5 §4.1).

Implements `ProxyDataSource` Protocol-based plug-in architecture.
Phase B ships built-in DSM (V2023/V2024/V2025) + Mediascope AdEx + TV Index adapters.

Custom client adapters добавляются через `AdapterRegistry.register(MyAdapter())`.
"""

from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
from aurora_launch.engines.format_adapters.mediascope_adex import MediascopeAdExAdapterV1
from aurora_launch.engines.format_adapters.registry import AdapterRegistry

__all__ = [
    "AdapterRegistry",
    "DsmAdapterV2024",
    "MediascopeAdExAdapterV1",
]
