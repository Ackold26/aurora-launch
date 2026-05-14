"""Aurora Launch KPI registry extension (B1 sprint).

Per PHASE_B_REQUIREMENTS.md §4.2 — Aurora Launch ships sales-only KPI primary.
Awareness deferred к Phase B+ (B2-B5 sprints introduce when needed).

Aurora Launch is sales forecasting product (per PRODUCT_BOUNDARIES.md P8).
Awareness = Aurora Brand product domain.

KPI registry extends Phase A C1 KPI registry:
- `sales_revenue_rub` (primary): weekly sales в rubles
- `units_sold` (alternative): weekly volume в packs/units
- `awareness_pct` (Phase B+ only): logit-scale awareness ceiling 100
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


KpiType = Literal["sales", "awareness", "category_value"]


@dataclass(frozen=True)
class LaunchKPI:
    """Aurora Launch KPI definition."""

    kpi_id: str
    kpi_type: KpiType
    field_name: str  # canonical name в bundle weekly_data records
    unit_label: str
    description: str
    available_in_phase: Literal["B0.5", "B+"]


# Registered Aurora Launch KPIs (B0.5 base set)
LAUNCH_KPI_REGISTRY: dict[str, LaunchKPI] = {
    "sales_revenue_rub": LaunchKPI(
        kpi_id="sales_revenue_rub",
        kpi_type="sales",
        field_name="sales_value_rub",
        unit_label="₽",
        description="Weekly sales revenue в Russian rubles. Primary KPI для most launches.",
        available_in_phase="B0.5",
    ),
    "units_sold": LaunchKPI(
        kpi_id="units_sold",
        kpi_type="sales",
        field_name="sales_volume_packs",
        unit_label="packs",
        description="Weekly sales volume в packs / units. Alternative KPI для FMCG где volume primary.",
        available_in_phase="B0.5",
    ),
    "sales_volume": LaunchKPI(
        kpi_id="sales_volume",
        kpi_type="sales",
        field_name="sales_volume",
        unit_label="units",
        description="Generic sales volume (synthetic corpus default field).",
        available_in_phase="B0.5",
    ),
    "awareness_pct": LaunchKPI(
        kpi_id="awareness_pct",
        kpi_type="awareness",
        field_name="awareness_pct",
        unit_label="%",
        description=(
            "Logit-scale awareness percentage (ceiling 100). "
            "Phase B+ only — Aurora Launch primary scope is sales forecasting; "
            "awareness analysis lives в Aurora Brand product domain."
        ),
        available_in_phase="B+",
    ),
}


def get_kpi(kpi_id: str) -> LaunchKPI:
    """Lookup KPI by id. Raises KeyError if unknown."""
    if kpi_id not in LAUNCH_KPI_REGISTRY:
        raise KeyError(
            f"Unknown Aurora Launch KPI: {kpi_id!r}. "
            f"Registered: {sorted(LAUNCH_KPI_REGISTRY.keys())}"
        )
    return LAUNCH_KPI_REGISTRY[kpi_id]


def list_kpis(*, available_only: bool = True) -> list[LaunchKPI]:
    """List registered KPIs.

    Args:
        available_only: if True (default), exclude `B+` phase deferred KPIs.
                        Set False for full registry inspection.
    """
    if available_only:
        return [k for k in LAUNCH_KPI_REGISTRY.values() if k.available_in_phase == "B0.5"]
    return list(LAUNCH_KPI_REGISTRY.values())


def kpi_field_for_category(category_l3: str) -> str:
    """Returns canonical field name based on category type.

    Sales-driven categories use `sales_volume` field; awareness category
    (synthetic corpus only в B0.5) uses `awareness_pct`.
    """
    if category_l3.startswith("awareness."):
        return get_kpi("awareness_pct").field_name
    return get_kpi("sales_volume").field_name
