"""Tests for B1 KPI registry extension."""

from __future__ import annotations

import pytest

from aurora_launch.engines.kpi_registry import (
    LAUNCH_KPI_REGISTRY,
    LaunchKPI,
    get_kpi,
    kpi_field_for_category,
    list_kpis,
)


class TestKpiRegistry:
    def test_registry_contains_b0_5_kpis(self) -> None:
        assert "sales_revenue_rub" in LAUNCH_KPI_REGISTRY
        assert "units_sold" in LAUNCH_KPI_REGISTRY
        assert "sales_volume" in LAUNCH_KPI_REGISTRY

    def test_awareness_kpi_marked_phase_b_plus(self) -> None:
        kpi = LAUNCH_KPI_REGISTRY["awareness_pct"]
        assert kpi.available_in_phase == "B+"

    def test_sales_kpis_available_b0_5(self) -> None:
        for kpi_id in ("sales_revenue_rub", "units_sold", "sales_volume"):
            kpi = LAUNCH_KPI_REGISTRY[kpi_id]
            assert kpi.available_in_phase == "B0.5"
            assert kpi.kpi_type == "sales"


class TestGetKpi:
    def test_known_kpi(self) -> None:
        kpi = get_kpi("sales_revenue_rub")
        assert isinstance(kpi, LaunchKPI)
        assert kpi.unit_label == "₽"

    def test_unknown_kpi_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown Aurora Launch KPI"):
            get_kpi("nonexistent_kpi")


class TestListKpis:
    def test_default_excludes_phase_b_plus(self) -> None:
        kpis = list_kpis()  # available_only=True default
        kpi_ids = {k.kpi_id for k in kpis}
        assert "awareness_pct" not in kpi_ids  # B+ excluded
        assert "sales_revenue_rub" in kpi_ids  # B0.5 included

    def test_full_registry_includes_phase_b_plus(self) -> None:
        kpis = list_kpis(available_only=False)
        kpi_ids = {k.kpi_id for k in kpis}
        assert "awareness_pct" in kpi_ids
        assert len(kpis) == len(LAUNCH_KPI_REGISTRY)


class TestKpiFieldForCategory:
    def test_awareness_category_uses_awareness_pct(self) -> None:
        assert kpi_field_for_category("awareness.brand_awareness_only") == "awareness_pct"

    def test_sales_category_uses_sales_volume(self) -> None:
        assert kpi_field_for_category("FMCG_food.snacks_savoury") == "sales_volume"
        assert kpi_field_for_category("OTC_pharma.OTC_cold_flu") == "sales_volume"
        assert kpi_field_for_category("Cosmetics.skincare_premium") == "sales_volume"

    def test_telecom_category_uses_sales_volume(self) -> None:
        # Even non-FMCG, non-awareness categories default к sales_volume
        assert kpi_field_for_category("Telecom.telecom_b2c_mobile") == "sales_volume"
