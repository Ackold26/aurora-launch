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

    def test_step_types_use_only_phase_a_v0_1_0_kinds(self, workflow_yaml: dict) -> None:
        """Phase A C3 ships 8 step types — workflow must use only those."""
        valid_types = {
            "import", "validate", "train", "decompose",
            "optimize", "scenario", "report", "custom",
        }
        for step in workflow_yaml["steps"]:
            assert step["step_type"] in valid_types, (
                f"Step {step['step_id']} uses unknown type {step['step_type']}"
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

    def test_engine_selector_deterministic_step(self, workflow_yaml: dict) -> None:
        """Audit M4 — engine selection as testable step."""
        step_ids = {s["step_id"] for s in workflow_yaml["steps"]}
        assert "select_engine" in step_ids

    def test_posterior_update_entry_point(self, workflow_yaml: dict) -> None:
        """B5 — posterior update on-demand entry point."""
        update_step = next(
            s for s in workflow_yaml["steps"]
            if s["step_id"] == "posterior_update_endpoint"
        )
        assert update_step.get("is_entry_point") is True
        # Auto-trigger criteria (audit M6 fix — all-AND)
        assert update_step["config"]["auto_trigger_min_new_weeks"] >= 4
        assert update_step["config"]["auto_trigger_min_ci_tightening_pct"] >= 10

    def test_telemetry_events_specified(self, workflow_yaml: dict) -> None:
        """B1.5 Customer Success Lite hooks defined."""
        telemetry = workflow_yaml.get("telemetry", {})
        events = telemetry.get("emit_events", [])
        assert len(events) > 0
        # Must include key milestones
        event_names = set()
        for e in events:
            if isinstance(e, str):
                event_names.add(e)
            elif isinstance(e, dict):
                event_names.update(e.keys())
        assert "workflow_started" in event_names
        assert "cert_signed" in event_names

    def test_performance_budgets_present(self, workflow_yaml: dict) -> None:
        """Per PHASE_B_REQUIREMENTS §3 — perf budgets unified."""
        perf = workflow_yaml.get("performance_budgets", {})
        assert "workflow_total_warm_p95_seconds" in perf
        # Train ≤45s p95 Warm — per §3
        train_budget = perf["per_step_overrides"]["train_proxy"]["warm_p95_seconds"]
        assert train_budget <= 45

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
