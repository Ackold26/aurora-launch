"""Format adapters for proxy data ingestion (B0.5 §4.1).

Implements `ProxyDataSource` Protocol-based plug-in architecture.
Phase B ships built-in DSM (V2023/V2024/V2025) + Mediascope AdEx + TV Index adapters.

Custom client adapters добавляются через `AdapterRegistry.register(MyAdapter())`.

Audit (post-1D extended) — file-size cap: every built-in adapter validates
incoming file size against `MAX_INPUT_FILE_BYTES` before reading. Realistic
DSM/Mediascope exports are <50 MB; any larger is either malicious or a
caller bug.
"""

from aurora_launch.engines.format_adapters.dsm_v2023 import DsmAdapterV2023
from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
from aurora_launch.engines.format_adapters.dsm_v2025 import DsmAdapterV2025
from aurora_launch.engines.format_adapters.mediascope_adex import MediascopeAdExAdapterV1
from aurora_launch.engines.format_adapters.mediascope_tv_index import MediascopeTvIndexAdapterV1
from aurora_launch.engines.format_adapters.registry import AdapterRegistry


# Shared input-size guard. 256 MB is far above any legitimate DSM/Mediascope
# panel export (annual TV index ≈ 10 MB; full pharma DSM annual ≈ 30 MB).
MAX_INPUT_FILE_BYTES = 256 * 1024 * 1024


class FormatAdapterFileTooLarge(ValueError):
    """Raised when an adapter is asked to parse a file exceeding the cap."""


def assert_file_size_ok(path, *, cap: int = MAX_INPUT_FILE_BYTES) -> None:
    """Helper: raise `FormatAdapterFileTooLarge` if file > cap. Adapters call
    this before opening for consistent enforcement."""
    from pathlib import Path as _Path

    p = _Path(path)
    if not p.exists():
        return  # let downstream FileNotFoundError fire
    size = p.stat().st_size
    if size > cap:
        raise FormatAdapterFileTooLarge(
            f"Input file {p} too large: {size} bytes > cap {cap} bytes "
            f"({size / 1e6:.1f} MB > {cap / 1e6:.0f} MB). Refusing to parse."
        )


__all__ = [
    "AdapterRegistry",
    "DsmAdapterV2023",
    "DsmAdapterV2024",
    "DsmAdapterV2025",
    "FormatAdapterFileTooLarge",
    "MAX_INPUT_FILE_BYTES",
    "MediascopeAdExAdapterV1",
    "MediascopeTvIndexAdapterV1",
    "assert_file_size_ok",
]
