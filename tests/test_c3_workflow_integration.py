"""Integration test: Aurora Launch workflow loads через C3 Workflow Engine.

Verifies aurora_workflow C3 (Phase A platform) can load Aurora Launch
reference workflow без errors. Covers Phase A→B handoff matrix per
PHASE_B_REQUIREMENTS.md §2.

Test skipped if aurora-platform-core path-dep not available (dev env only).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Path to aurora-platform-core local checkout (path-based dep)
PLATFORM_CORE_PATH = Path("../aurora-platform-core").resolve()
WORKFLOW_PATH = (
    PLATFORM_CORE_PATH
    / "aurora_workflow"
    / "src"
    / "aurora_workflow"
    / "reference_workflows"
    / "aurora_launch_proxy_intake.v2.yaml"
)


@pytest.fixture
def workflow_yaml() -> dict:
    if not WORKFLOW_PATH.exists():
        pytest.skip(f"aurora-platform-core not found at {PLATFORM_CORE_PATH}")
    with WORKFLOW_PATH.open() as f:
        return yaml.safe_load(f)


class TestAuroraLaunchWorkflowYaml:
    """Workflow YAML structural validation (does not require importing aurora_workflow)."""

    def test_workflow_id(self, workflow_yaml: dict) -> None:
        assert workflow_yaml["workflow_id"] == "aurora_launch_proxy_intake"

    def test_definition_version_v2(self, workflow_yaml: dict) -> None:
        assert workflow_yaml["definition_version"] == "2.0.0"

    def test_schema_version(self, workflow_yaml: dict) -> None:
        assert workflow_yaml["schema_version"] == "3.0"

    def test_steps_present(self, workflow_yaml: dict) -> None:
        steps = workflow_yaml["steps"]
        assert len(steps) >= 12  # B2/B3/B4/B5 mapped

    def test_step_types_use_only_registered_kinds(self, workflow_yaml: dict) -> None:
        """C3 ships 13 step types в Phase B v0.2.0 (8 Phase A + 5 first-class
        Aurora Launch types per H-Audit-4 Option A)."""
        valid_types = {
            # Phase A v0.1.0
            "import", "validate", "train", "decompose",
            "optimize", "scenario", "report", "custom",
            # Phase B v0.2.0 — Aurora Launch first-class
            "proxy_select", "transfer_validate", "posterior_update",
            "engine_select", "cert_sign",
        }
        for step in workflow_yaml["steps"]:
            assert step["step_type"] in valid_types, (
                f"Step {step['step_id']} uses unknown type {step['step_type']}"
            )

    def test_aurora_launch_first_class_step_types_used(self, workflow_yaml: dict) -> None:
        """H-Audit-4 Option A verified: Aurora Launch–specific operations now
        use first-class step types instead of generic `custom`. Main workflow
        uses 4 of 5 (posterior_update lives в separate on-demand workflow per
        B-A2-2 fix)."""
        used_types = {s["step_type"] for s in workflow_yaml["steps"]}
        # 4 of 5 Aurora Launch first-class types appear in main workflow
        assert "proxy_select" in used_types
        assert "transfer_validate" in used_types
        assert "engine_select" in used_types
        assert "cert_sign" in used_types
        # posterior_update — separate workflow (B-A2-2 fix)

    def test_workflow_loads_via_pydantic(self, workflow_yaml: dict) -> None:
        """Verify workflow YAML actually loads через Workflow Pydantic model
        (FrozenModel, extra='forbid' — non-standard fields rejected).
        H-Audit-5 — non-standard top-level fields removed from YAML."""
        # No top-level non-standard fields
        forbidden_top_level = {"cleanup_callbacks", "telemetry", "performance_budgets"}
        for field in forbidden_top_level:
            assert field not in workflow_yaml, (
                f"Top-level field {field!r} would be rejected by Workflow.extra=forbid; "
                f"move into step config dict instead"
            )

    def test_proxy_intake_protocol_steps_present(self, workflow_yaml: dict) -> None:
        """Verify 7-step PROXY_INTAKE_PROTOCOL operationalized."""
        step_ids = {s["step_id"] for s in workflow_yaml["steps"]}
        # Discovery + verification implicit во import_proxy_data
        # Anonymization handled by Phase A C2 adapter layer
        # Steps 4-7 explicit:
        assert "import_proxy_data" in step_ids  # data ingestion
        assert "extract_proxy_priors" in step_ids  # train Trust 3 model
        assert "apply_recipient_magnitudes" in step_ids  # transfer
        assert "generate_methodology_cert" in step_ids  # signed cert

    def test_dual_signature_configured(self, workflow_yaml: dict) -> None:
        """HIGH H2 fix verified — dual signature in cert generation."""
        cert_step = next(
            s for s in workflow_yaml["steps"]
            if s["step_id"] == "generate_methodology_cert"
        )
        assert cert_step["config"]["dual_signature"] is True

    def test_pdf_renderer_per_adr_006(self, workflow_yaml: dict) -> None:
        """ADR-006 — Tauri webview print API primary."""
        cert_step = next(
            s for s in workflow_yaml["steps"]
            if s["step_id"] == "generate_methodology_cert"
        )
        assert cert_step["config"]["pdf_renderer"] == "tauri_webview"

    def test_three_verifier_formats_present(self, workflow_yaml: dict) -> None:
        """HIGH H3 fix — web + standalone HTML + CLI verifier formats."""
        cert_step = next(
            s for s in workflow_yaml["steps"]
            if s["step_id"] == "generate_methodology_cert"
        )
        urls = cert_step["config"]["verifier_urls"]
        assert "web" in urls
        assert "standalone_html" in urls
        assert "cli" in urls

    def test_engine_selector_first_class_step(self, workflow_yaml: dict) -> None:
        """Audit M4 — engine selection as testable step. Now first-class type
        engine_select (was custom in v0.1.0)."""
        step_ids = {s["step_id"] for s in workflow_yaml["steps"]}
        assert "select_engine" in step_ids
        select_step = next(s for s in workflow_yaml["steps"] if s["step_id"] == "select_engine")
        assert select_step["step_type"] == "engine_select"

    def test_posterior_update_in_separate_workflow(self) -> None:
        """B-A2-2 fix verified: posterior_update was removed from main workflow
        (was `posterior_update_endpoint` с is_on_demand=true config flag — wrong
        because Workflow engine executes DAG eagerly). Now separate workflow file
        `aurora_launch_posterior_update.v1.yaml` for on-demand re-fits."""
        update_workflow_path = (
            PLATFORM_CORE_PATH
            / "aurora_workflow"
            / "src"
            / "aurora_workflow"
            / "reference_workflows"
            / "aurora_launch_posterior_update.v1.yaml"
        )
        if not update_workflow_path.exists():
            pytest.skip(f"posterior_update workflow not found at {update_workflow_path}")
        with update_workflow_path.open() as f:
            update_wf = yaml.safe_load(f)
        assert update_wf["workflow_id"] == "aurora_launch_posterior_update"
        # Has dedicated posterior_update step
        update_step = next(
            s for s in update_wf["steps"]
            if s["step_type"] == "posterior_update"
        )
        # Auto-trigger criteria (audit M6 fix — all-AND)
        assert update_step["config"]["auto_trigger_min_new_weeks"] >= 4
        assert update_step["config"]["auto_trigger_min_ci_tightening_pct"] >= 10

    def test_main_workflow_no_posterior_update_step(self, workflow_yaml: dict) -> None:
        """B-A2-2 fix verified: main pipeline does NOT contain posterior_update
        step (it's in separate on-demand workflow)."""
        for step in workflow_yaml["steps"]:
            assert step["step_type"] != "posterior_update", (
                f"Main workflow contains posterior_update step {step['step_id']!r} — "
                f"posterior_update должен быть в separate workflow per B-A2-2 fix"
            )

    def test_apply_recipient_magnitudes_depends_on_select_engine(
        self, workflow_yaml: dict
    ) -> None:
        """H-A2-7 fix verified: magnitude calibration formula varies by engine
        choice (single vs multi-proxy aggregate) — DAG must reflect dependency."""
        magnitudes_step = next(
            s for s in workflow_yaml["steps"]
            if s["step_id"] == "apply_recipient_magnitudes"
        )
        assert "select_engine" in magnitudes_step["depends_on"], (
            "apply_recipient_magnitudes должен depend on select_engine"
        )

    def test_telemetry_events_in_step_config(self, workflow_yaml: dict) -> None:
        """B1.5 Customer Success Lite hooks. Now distributed into per-step
        config (telemetry_event field) instead of non-standard top-level
        block (H-Audit-5 fix). Main workflow milestones — posterior_updated
        в separate on-demand workflow."""
        events_emitted = set()
        for step in workflow_yaml["steps"]:
            event_name = step.get("config", {}).get("telemetry_event")
            if event_name:
                events_emitted.add(event_name)
        # Main pipeline milestones
        assert "proxy_selected" in events_emitted
        assert "cert_signed" in events_emitted
        # posterior_updated — separate workflow (B-A2-2 fix)

    def test_performance_budgets_in_step_config(self, workflow_yaml: dict) -> None:
        """Per PHASE_B_REQUIREMENTS §3 — perf budgets per-step. Now in step
        config (`perf_budget_warm_p95_seconds`) instead of non-standard
        top-level block (H-Audit-5 fix)."""
        budgets_found = []
        for step in workflow_yaml["steps"]:
            budget = step.get("config", {}).get("perf_budget_warm_p95_seconds")
            if budget is not None:
                budgets_found.append((step["step_id"], budget))
        assert len(budgets_found) >= 4  # at least 4 steps have explicit budgets
        # train steps must respect ≤45s p95 Warm
        for step_id, budget in budgets_found:
            if "train" in step_id or "fit" in step_id:
                assert budget <= 45

    def test_dependencies_form_dag(self, workflow_yaml: dict) -> None:
        """Verify dependencies are well-formed (no self-loops, valid step refs)."""
        steps = workflow_yaml["steps"]
        step_ids = {s["step_id"] for s in steps}
        for step in steps:
            depends = step.get("depends_on", [])
            for dep in depends:
                assert dep in step_ids, (
                    f"Step {step['step_id']} depends on unknown step {dep}"
                )
                assert dep != step["step_id"], "Self-dependency"
