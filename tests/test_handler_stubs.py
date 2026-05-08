"""Test handler stubs (M-A2-7 closure).

Verifies all 8 handler entry-points referenced by workflow YAMLs are
importable + return realistic-shape results. Real implementations ship
in Phase B B2-B5 sprints.
"""

from __future__ import annotations

import asyncio

import pytest


class TestSimilarityCalculator:
    """B2 sprint stub."""

    def test_compute_imports(self) -> None:
        from aurora_launch.engines.similarity_calculator import compute
        assert callable(compute)

    def test_returns_verdict_shape(self) -> None:
        from aurora_launch.engines.similarity_calculator import compute
        result = asyncio.run(compute(ctx=None, multi_proxy_mode=False))
        assert result["step_type"] == "proxy_select"
        assert result["stub"] is True
        assert "similarity_score" in result
        assert "verdict" in result
        assert result["verdict"] in ("High", "Medium", "Low", "Insufficient")
        assert "block_forecast" in result


class TestEngineSelector:
    """B3 sprint — real implementation. Test workflow handler entry point."""

    def test_select_engine_handler_returns_decision(self) -> None:
        from aurora_launch.engines.engine_selector import select_engine_handler
        result = asyncio.run(select_engine_handler(ctx=None))
        assert result["step_type"] == "engine_select"
        assert result["selected_engine"] in ("single", "multi", "single_with_pooling", "blocked")
        assert result["stub"] is False  # B3 ships real implementation


class TestLaunchAdapt:
    """B3 sprint stubs."""

    def test_apply_recipient_magnitudes_returns_priors(self) -> None:
        from aurora_launch.engines.launch_adapt import apply_recipient_magnitudes
        result = asyncio.run(apply_recipient_magnitudes(ctx=None))
        assert result["step_type"] == "apply_recipient_magnitudes"
        assert "transferred_params" in result
        assert "not_transferred" in result
        # Transfer rule: shape transferred (5 params per ADR-003), magnitude calibrated
        assert "adstock_decay" in result["transferred_params"]
        assert "beta_coefficients" in result["not_transferred"]

    def test_extract_proxy_priors(self) -> None:
        from aurora_launch.engines.launch_adapt import extract_proxy_priors
        result = asyncio.run(extract_proxy_priors(ctx=None))
        assert result["step_type"] == "extract_proxy_priors"


class TestLaunchValidate:
    """B3 sprint stub."""

    def test_call_returns_prior_predictive(self) -> None:
        from aurora_launch.engines.launch_validate import validate_transfer
        result = asyncio.run(validate_transfer(ctx=None, prior_predictive_samples=50))
        assert result["step_type"] == "transfer_validate"
        assert result["prior_predictive_samples_generated"] == 50
        assert "sensitivity_results" in result
        assert "anchor_uncertainty_decomp" in result
        # Total uncertainty contributions sum = 100%
        decomp = result["anchor_uncertainty_decomp"]
        total = (
            decomp["market_size_contribution"] + decomp["distribution_contribution"]
            + decomp["pricing_contribution"] + decomp["creative_contribution"]
            + decomp["competitive_contribution"] + decomp["proxy_transfer_contribution"]
        )
        assert abs(total - 1.0) < 0.01


class TestMethodologyCert:
    """B4 sprint stub."""

    def test_build_certificate_returns_cert_metadata(self) -> None:
        """B4 real impl — composes Cert metadata. Actual signing pending C7 deployment."""
        from aurora_launch.engines.methodology_cert import build_certificate
        result = asyncio.run(build_certificate(ctx=None, dual_signature=True))
        assert result["step_type"] == "cert_sign"
        assert "cert_id" in result
        # B4 real impl — signing pending C7 service deployment
        assert "dual_signature_status" in result
        assert result["tier_independent"] is True  # BLOCKER B2
        # 3 verifier formats (HIGH H3) — schema field names
        urls = result["verifier_urls"]
        assert "web_verifier_url" in urls
        assert "standalone_html_download_url" in urls
        assert "cli_tool_download_url" in urls

    def test_pdf_renderer_default_tauri_webview(self) -> None:
        """ADR-006 — Tauri webview primary."""
        from aurora_launch.engines.methodology_cert import build_certificate
        result = asyncio.run(build_certificate(ctx=None))
        assert result["pdf_renderer_used"] == "tauri_webview"


class TestLaunchPosteriorUpdate:
    """B5 sprint stubs."""

    def test_detect_drift(self) -> None:
        from aurora_launch.engines.launch_posterior_update import detect_drift_handler
        result = asyncio.run(detect_drift_handler(ctx=None))
        assert result["step_type"] == "detect_drift"
        assert result["severity"] in ("normal", "mild", "moderate", "severe", "unknown")
        assert "coverage_observed" in result

    def test_detect_drift_min_weeks_8(self) -> None:
        """Audit M-fix — min 8 weeks для drift detection."""
        from aurora_launch.engines.launch_posterior_update import detect_drift_handler
        result = asyncio.run(detect_drift_handler(ctx=None, min_weeks=8))
        assert result["min_weeks_used"] >= 8

    def test_update_posterior(self) -> None:
        from aurora_launch.engines.launch_posterior_update import update_posterior
        result = asyncio.run(update_posterior(ctx=None))
        assert result["step_type"] == "posterior_update"
        assert result["update_mode"] in ("partial_pooling", "bma")
        assert result["bma_opted_in_by_customer"] in (True, False)  # explicit, never None (audit M11)
        # Pooling weights sum to 1.0
        weights = result["pooling_weights"]
        assert abs(weights["w_proxy"] + weights["w_recipient"] - 1.0) < 0.01

    def test_entry_point_composes(self) -> None:
        """Entry point composes drift detection + update."""
        from aurora_launch.engines.launch_posterior_update import entry_point
        result = asyncio.run(entry_point(ctx=None))
        assert result["step_type"] == "posterior_update_entry"
        assert "drift" in result


class TestAllHandlersReferencedByWorkflows:
    """End-to-end check: all handlers referenced by workflow YAMLs are importable."""

    HANDLER_PATHS = [
        "aurora_launch.engines.similarity_calculator.compute",
        "aurora_launch.engines.engine_selector.select_engine_handler",  # B3 real
        "aurora_launch.engines.launch_adapt.apply_recipient_magnitudes",
        "aurora_launch.engines.launch_adapt.extract_proxy_priors",
        "aurora_launch.engines.launch_validate.validate_transfer",
        "aurora_launch.engines.methodology_cert.build_certificate",
        "aurora_launch.engines.launch_posterior_update.entry_point",
        "aurora_launch.engines.launch_posterior_update.detect_drift_handler",
        "aurora_launch.engines.launch_posterior_update.update_posterior_handler",
    ]

    @pytest.mark.parametrize("dotted_path", HANDLER_PATHS)
    def test_handler_resolvable(self, dotted_path: str) -> None:
        """Each handler is importable + callable (mirrors C3 resolver expectations)."""
        parts = dotted_path.split(".")
        # Try as module first, then as attribute
        for split_idx in range(len(parts) - 1, 0, -1):
            module_path = ".".join(parts[:split_idx])
            attr_path = parts[split_idx:]
            try:
                import importlib
                mod = importlib.import_module(module_path)
                obj: object = mod
                for attr in attr_path:
                    obj = getattr(obj, attr)
                assert callable(obj), f"Handler {dotted_path} not callable"
                return
            except (ImportError, AttributeError):
                continue
        # If we exhausted all splits without finding handler — try module-level __call__
        try:
            import importlib
            mod = importlib.import_module(dotted_path)
            assert hasattr(mod, "__call__"), f"Module {dotted_path} not module-callable"
        except ImportError as e:
            pytest.fail(f"Cannot resolve handler {dotted_path}: {e}")
