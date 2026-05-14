"""Phase Π.2 — 4-mode dual-math router tests.

Audit P-02 fix: thoroughly cover routing decisions для both granularities
и all 4 modes including n=0 edge case.

Per INV-08: every public function exercised в tests.
Per audit P0-10: explicit attack scenarios для invalid inputs.
"""

from __future__ import annotations

import pytest

from aurora_launch.engines.router import (
    ALLOWED_GRANULARITIES,
    THRESHOLDS_MONTHLY,
    THRESHOLDS_WEEKLY,
    EngineConfig,
    EngineMode,
    describe_thresholds,
    select_engine,
    thresholds_for,
)


# ---------------------------------------------------------------------------
# Granularity matrix tests (parametrised across monthly/weekly)
# ---------------------------------------------------------------------------


class TestGranularityThresholds:
    def test_monthly_thresholds(self) -> None:
        th = thresholds_for("monthly")
        assert th.ols_low == 3
        assert th.bayesian == 7

    def test_weekly_thresholds(self) -> None:
        th = thresholds_for("weekly")
        assert th.ols_low == 8
        assert th.bayesian == 20

    def test_invalid_granularity(self) -> None:
        with pytest.raises(ValueError, match="must be"):
            thresholds_for("daily")  # type: ignore[arg-type]


class TestModeSelection:
    """Per-granularity matrix of n_recipient → expected mode."""

    @pytest.mark.parametrize(
        "granularity,n_recipient,expected_mode",
        [
            # Monthly granularity
            ("monthly", 0, EngineMode.PURE_TRANSFER),
            ("monthly", 1, EngineMode.TRANSFER_WITH_BIAS_CHECK),
            ("monthly", 2, EngineMode.TRANSFER_WITH_BIAS_CHECK),
            ("monthly", 3, EngineMode.OLS_WITH_PROXY_PRIORS),
            ("monthly", 6, EngineMode.OLS_WITH_PROXY_PRIORS),
            ("monthly", 7, EngineMode.BAYESIAN_WITH_PROXY_PRIORS),
            ("monthly", 24, EngineMode.BAYESIAN_WITH_PROXY_PRIORS),
            # Weekly granularity
            ("weekly", 0, EngineMode.PURE_TRANSFER),
            ("weekly", 1, EngineMode.TRANSFER_WITH_BIAS_CHECK),
            ("weekly", 7, EngineMode.TRANSFER_WITH_BIAS_CHECK),
            ("weekly", 8, EngineMode.OLS_WITH_PROXY_PRIORS),
            ("weekly", 19, EngineMode.OLS_WITH_PROXY_PRIORS),
            ("weekly", 20, EngineMode.BAYESIAN_WITH_PROXY_PRIORS),
            ("weekly", 104, EngineMode.BAYESIAN_WITH_PROXY_PRIORS),
        ],
    )
    def test_baseline_mode_matrix(
        self, granularity: str, n_recipient: int, expected_mode: EngineMode
    ) -> None:
        # Use proxy size sufficient для both granularities (104 > both minima)
        cfg = select_engine(
            n_recipient=n_recipient,
            n_proxy=104,
            granularity=granularity,  # type: ignore[arg-type]
        )
        assert cfg.mode == expected_mode
        assert cfg.granularity == granularity


class TestPureTransferMode:
    """Mode 1: n_recipient = 0 — основной use case Materia Medica pilot
    (pre-launch forecast)."""

    def test_pure_transfer_returns_correct_mode(self) -> None:
        cfg = select_engine(n_recipient=0, n_proxy=24, granularity="monthly")
        assert cfg.mode == EngineMode.PURE_TRANSFER
        assert cfg.banner_tone == "warn"
        assert "proxy adaptation" in cfg.banner_message.lower()

    def test_pure_transfer_no_user_override(self) -> None:
        cfg = select_engine(n_recipient=0, n_proxy=24, granularity="monthly")
        assert cfg.user_override_allowed is False
        assert cfg.user_override_modes == ()

    def test_pure_transfer_user_override_rejected(self) -> None:
        # Cannot force Bayesian with n=0 — no y data!
        with pytest.raises(ValueError, match="not allowed"):
            select_engine(
                n_recipient=0,
                n_proxy=24,
                granularity="monthly",
                user_override=EngineMode.BAYESIAN_WITH_PROXY_PRIORS,
            )


class TestBayesianModeAllowsOverride:
    def test_bayesian_baseline_allows_ols_downgrade(self) -> None:
        cfg = select_engine(
            n_recipient=12,
            n_proxy=104,
            granularity="monthly",
            user_override=EngineMode.OLS_WITH_PROXY_PRIORS,
        )
        assert cfg.mode == EngineMode.OLS_WITH_PROXY_PRIORS
        assert "Manual override" in cfg.banner_message

    def test_bayesian_baseline_allows_bayesian_explicit(self) -> None:
        cfg = select_engine(
            n_recipient=12,
            n_proxy=104,
            granularity="monthly",
            user_override=EngineMode.BAYESIAN_WITH_PROXY_PRIORS,
        )
        assert cfg.mode == EngineMode.BAYESIAN_WITH_PROXY_PRIORS

    def test_bayesian_baseline_rejects_pure_transfer_override(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            select_engine(
                n_recipient=12,
                n_proxy=104,
                granularity="monthly",
                user_override=EngineMode.PURE_TRANSFER,
            )


class TestProxyMinimum:
    def test_proxy_too_small_monthly(self) -> None:
        with pytest.raises(ValueError, match="Proxy needs"):
            select_engine(n_recipient=5, n_proxy=10, granularity="monthly")

    def test_proxy_too_small_weekly(self) -> None:
        with pytest.raises(ValueError, match="Proxy needs"):
            select_engine(n_recipient=5, n_proxy=30, granularity="weekly")

    def test_proxy_minimum_monthly_accepted(self) -> None:
        cfg = select_engine(n_recipient=0, n_proxy=24, granularity="monthly")
        assert cfg.mode == EngineMode.PURE_TRANSFER

    def test_proxy_minimum_weekly_accepted(self) -> None:
        cfg = select_engine(n_recipient=0, n_proxy=52, granularity="weekly")
        assert cfg.mode == EngineMode.PURE_TRANSFER


class TestInputValidation:
    def test_negative_n_recipient_rejected(self) -> None:
        with pytest.raises(ValueError, match="n_recipient must be ≥ 0"):
            select_engine(n_recipient=-1, n_proxy=24, granularity="monthly")

    def test_invalid_granularity_rejected(self) -> None:
        with pytest.raises(ValueError, match="granularity"):
            select_engine(
                n_recipient=5,
                n_proxy=24,
                granularity="daily",  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("bad_shrinkage", [-0.1, 1.1, 2.0, -1.0])
    def test_shrinkage_out_of_range(self, bad_shrinkage: float) -> None:
        with pytest.raises(ValueError, match="shrinkage_factor"):
            select_engine(
                n_recipient=5,
                n_proxy=24,
                granularity="monthly",
                shrinkage_factor=bad_shrinkage,
            )

    @pytest.mark.parametrize("good_shrinkage", [0.0, 0.5, 1.0, 0.25, 0.75])
    def test_shrinkage_valid_range(self, good_shrinkage: float) -> None:
        cfg = select_engine(
            n_recipient=10,
            n_proxy=24,
            granularity="monthly",
            shrinkage_factor=good_shrinkage,
        )
        assert cfg.shrinkage_factor == good_shrinkage


class TestDescribeThresholds:
    def test_describe_monthly(self) -> None:
        desc = describe_thresholds("monthly")
        assert desc["granularity"] == "monthly"
        assert desc["proxy_minimum"] == 24
        assert "n_recipient = 0" in desc["pure_transfer"]

    def test_describe_weekly(self) -> None:
        desc = describe_thresholds("weekly")
        assert desc["granularity"] == "weekly"
        assert desc["proxy_minimum"] == 52


class TestEngineConfigContract:
    def test_config_is_frozen(self) -> None:
        cfg = select_engine(n_recipient=5, n_proxy=24, granularity="monthly")
        with pytest.raises(Exception):
            cfg.mode = EngineMode.PURE_TRANSFER  # type: ignore[misc]

    def test_banner_tone_valid_values(self) -> None:
        for n in [0, 1, 3, 7, 12]:
            cfg = select_engine(n_recipient=n, n_proxy=24, granularity="monthly")
            assert cfg.banner_tone in {"good", "warn", "bad"}

    def test_banner_message_includes_n(self) -> None:
        cfg = select_engine(n_recipient=5, n_proxy=24, granularity="monthly")
        assert "5" in cfg.banner_message
        assert "monthly" in cfg.banner_message.lower()
