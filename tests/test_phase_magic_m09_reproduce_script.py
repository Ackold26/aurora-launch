"""Phase Magic M-09: reproduce-in-Python script generator tests."""

from __future__ import annotations

import ast

import pytest

from aurora_launch.tools.reproduce_script import (
    generate_reproduce_script,
    reproduce_script_to_filename,
)


class TestScriptGeneration:
    """Basic generation contract."""

    def _make_minimal_args(self) -> dict:
        return {
            "bundle_path": "/tmp/project.aurora",
            "anchors": {
                "market_size": 1_000_000.0,
                "market_size_cv": 0.10,
                "planned_share_trajectory": [0.05] * 12,
                "distribution_trajectory": [0.8] * 12,
                "pricing_index": 1.0,
                "elasticity": 0.0,
                "seasonality": None,
            },
            "spend_plan": {"tv": [100_000.0] * 12},
            "horizon_periods": 12,
            "granularity": "monthly",
            "coverage_target": 0.95,
            "n_recipient": 0,
            "seed": 42,
        }

    def test_generates_non_empty_string(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        assert isinstance(script, str)
        assert len(script) > 500  # non-trivial content

    def test_script_has_shebang(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        assert script.startswith("#!/usr/bin/env python3")

    def test_script_imports_aurora_launch(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        assert "from aurora_launch.engines.launch_orchestrator import" in script
        assert "make_proxy_bundle" in script
        assert "LaunchOrchestrator" in script

    def test_script_imports_open_lazy(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        assert "from aurora_launch.engines.bundle_streaming import open_lazy" in script

    def test_script_references_bundle_path(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        assert "/tmp/project.aurora" in script

    def test_script_includes_horizon_periods(self) -> None:
        args = self._make_minimal_args()
        args["horizon_periods"] = 26
        script = generate_reproduce_script(**args)
        assert "horizon_periods=26" in script

    def test_script_includes_granularity(self) -> None:
        args = self._make_minimal_args()
        args["granularity"] = "weekly"
        script = generate_reproduce_script(**args)
        assert 'granularity="weekly"' in script


class TestScriptValidity:
    """Generated script must be valid Python syntactically."""

    def _make_minimal_args(self) -> dict:
        return {
            "bundle_path": "./project.aurora",
            "anchors": {
                "market_size": 1_000_000.0,
                "market_size_cv": 0.10,
                "planned_share_trajectory": [0.05] * 6,
                "distribution_trajectory": [0.8] * 6,
                "pricing_index": 1.0,
                "elasticity": 0.0,
                "seasonality": None,
            },
            "spend_plan": {"tv": [50_000.0] * 6, "digital": [25_000.0] * 6},
            "horizon_periods": 6,
        }

    def test_script_compiles_к_valid_python(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        try:
            ast.parse(script)
        except SyntaxError as exc:
            pytest.fail(f"Generated script has SyntaxError: {exc}")

    def test_script_includes_all_anchors_fields(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        # All anchor field names appear в anchors dict literal
        for field in (
            "market_size",
            "market_size_cv",
            "planned_share_trajectory",
            "distribution_trajectory",
            "pricing_index",
            "elasticity",
        ):
            assert field in script, f"Missing anchor field {field}"

    def test_script_serializes_spend_plan_channels(self) -> None:
        script = generate_reproduce_script(**self._make_minimal_args())
        assert "tv" in script
        assert "digital" in script

    def test_script_handles_empty_spend_plan(self) -> None:
        args = self._make_minimal_args()
        args["spend_plan"] = {}
        script = generate_reproduce_script(**args)
        ast.parse(script)  # must still compile
        assert "spend_plan = {}" in script


class TestFilename:
    def test_filename_format(self) -> None:
        name = reproduce_script_to_filename("20260515_120000")
        assert name == "aurora_reproduce_20260515_120000.py"

    def test_filename_default_uses_now(self) -> None:
        name = reproduce_script_to_filename()
        assert name.startswith("aurora_reproduce_")
        assert name.endswith(".py")


class TestIpcHandler:
    """IPC handler generate_reproduce_script returns correct schema."""

    def test_handler_returns_script_and_filename(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch(
            "generate_reproduce_script",
            {
                "bundle_path": "./my.aurora",
                "anchors": {
                    "market_size": 1_000_000.0,
                    "market_size_cv": 0.1,
                    "planned_share_trajectory": [0.05] * 12,
                    "distribution_trajectory": [0.8] * 12,
                    "pricing_index": 1.0,
                    "elasticity": 0.0,
                    "seasonality": None,
                },
                "spend_plan": {"tv": [100.0] * 12},
                "horizon_periods": 12,
            },
        )
        assert "script" in result
        assert "suggested_filename" in result
        assert result["script"].startswith("#!/usr/bin/env python3")
        assert result["suggested_filename"].endswith(".py")

    def test_handler_uses_defaults_for_missing_params(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        # Minimal params — handler uses defaults для anchors / spend_plan
        result = dispatch("generate_reproduce_script", {})
        assert "script" in result
        # Default bundle_path
        assert "project.aurora" in result["script"]


class TestSecurity:
    """Script generator must NOT inject arbitrary code via params."""

    def test_malicious_bundle_path_does_not_execute(self) -> None:
        """Path с code-like chars must appear как string literal только."""
        script = generate_reproduce_script(
            bundle_path='/tmp/`rm -rf /`.aurora',
            anchors={
                "market_size": 1_000_000.0,
                "market_size_cv": 0.1,
                "planned_share_trajectory": [0.05] * 12,
                "distribution_trajectory": [0.8] * 12,
                "pricing_index": 1.0,
                "elasticity": 0.0,
                "seasonality": None,
            },
            spend_plan={"tv": [100.0] * 12},
            horizon_periods=12,
        )
        # Path appears как Path("...") string — backticks treated as chars,
        # NOT shell expansion. ast.parse compiles cleanly.
        ast.parse(script)
        assert "BUNDLE_PATH = Path(" in script

    def test_anchors_with_string_injection_attempt(self) -> None:
        """Anchors containing quote chars produce valid JSON-encoded literals."""
        # market_size as malicious string instead of number
        script = generate_reproduce_script(
            bundle_path="./x.aurora",
            anchors={
                "market_size": 'malicious"; os.system("ls")  #',
                "market_size_cv": 0.1,
                "planned_share_trajectory": [0.05] * 6,
                "distribution_trajectory": [0.8] * 6,
                "pricing_index": 1.0,
                "elasticity": 0.0,
                "seasonality": None,
            },
            spend_plan={"tv": [100.0] * 6},
            horizon_periods=6,
        )
        # Must still compile — JSON encoding escapes quotes
        ast.parse(script)
