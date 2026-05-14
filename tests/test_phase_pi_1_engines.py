"""
Smoke tests for Phase π.1 math engine port from Aurora Econometrica.

Per INV-02: tests call public functions with trivial args to ensure:
1. All 4 engine modules import without errors.
2. recommend_engine returns correct routing decisions.
3. apply_adstock returns correct length array.
4. hill_function is monotonically increasing.
5. train_model / train_ols are importable (no end-to-end run — slow PyMC compile).
"""
import importlib
import numpy as np
import pytest


# ─── INV-02: import checks ────────────────────────────────────────────────────

def test_import_bayesian_engine():
    """bayesian_engine.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.engines.bayesian_engine')
    assert hasattr(mod, 'train_model')
    assert hasattr(mod, 'recommend_engine') is False  # recommend_engine is in ols_engine


def test_import_ols_engine():
    """ols_engine.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.engines.ols_engine')
    assert hasattr(mod, 'train_ols')
    assert hasattr(mod, 'recommend_engine')


def test_import_decompose():
    """decompose.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.engines.decompose')
    assert hasattr(mod, 'decompose')
    assert hasattr(mod, 'compute_roi_verdict')


def test_import_loader():
    """loader.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.engines.loader')
    assert hasattr(mod, 'load_model_with_compat')
    assert hasattr(mod, 'get_channel_categories')


def test_import_utils_adstock():
    """utils/adstock.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.utils.adstock')
    assert hasattr(mod, 'apply_adstock')
    assert hasattr(mod, 'geometric_adstock')
    assert hasattr(mod, 'geometric_adstock_batch')


def test_import_utils_saturation():
    """utils/saturation.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.utils.saturation')
    assert hasattr(mod, 'hill_function')
    assert hasattr(mod, 'hill_function_batch')


def test_import_utils_channel_categorization():
    """utils/channel_categorization.py imports without errors (INV-02)."""
    mod = importlib.import_module('aurora_launch.utils.channel_categorization')
    assert hasattr(mod, 'auto_suggest_category')
    assert hasattr(mod, 'recommend_engine') is False


# ─── recommend_engine routing ─────────────────────────────────────────────────

def test_recommend_engine_small_data_returns_ols():
    """n_obs=10 → recommended='ols' (Bayesian unreliable below 20 obs)."""
    from aurora_launch.engines.ols_engine import recommend_engine
    result = recommend_engine(n_obs=10)
    assert result['recommended'] == 'ols', (
        f"Expected 'ols' for n=10, got '{result['recommended']}'. "
        f"Reason: {result.get('reason', '')}"
    )
    assert result['banner_tone'] == 'bad'
    assert 'ols' in result['allowed']
    assert 'bayesian' not in result['allowed']


def test_recommend_engine_large_data_returns_bayesian():
    """n_obs=50 → recommended='bayesian' (sufficient for reliable posterior CI)."""
    from aurora_launch.engines.ols_engine import recommend_engine
    result = recommend_engine(n_obs=50)
    assert result['recommended'] == 'bayesian', (
        f"Expected 'bayesian' for n=50, got '{result['recommended']}'. "
        f"Reason: {result.get('reason', '')}"
    )
    assert result['banner_tone'] == 'good'
    assert 'bayesian' in result['allowed']
    assert 'ols' in result['allowed']


def test_recommend_engine_borderline():
    """n_obs=25 → recommended='ols' (borderline, warn tone), both allowed."""
    from aurora_launch.engines.ols_engine import recommend_engine
    result = recommend_engine(n_obs=25)
    assert result['recommended'] == 'ols'
    assert result['banner_tone'] == 'warn'
    assert 'ols' in result['allowed']
    assert 'bayesian' in result['allowed']


def test_recommend_engine_user_override():
    """override='bayesian' on n=5 → respects user choice regardless of n."""
    from aurora_launch.engines.ols_engine import recommend_engine
    result = recommend_engine(n_obs=5, override='bayesian')
    assert result['recommended'] == 'bayesian'
    assert result.get('override_active') is True
    assert result['banner_tone'] == 'good'


def test_recommend_engine_ols_override():
    """override='ols' on n=100 → respects user choice for large dataset."""
    from aurora_launch.engines.ols_engine import recommend_engine
    result = recommend_engine(n_obs=100, override='ols')
    assert result['recommended'] == 'ols'
    assert result.get('override_active') is True


# ─── apply_adstock correctness ────────────────────────────────────────────────

def test_apply_adstock_returns_correct_length():
    """apply_adstock output length must equal input length."""
    from aurora_launch.utils.adstock import apply_adstock
    x = np.array([100.0, 200.0, 50.0, 75.0, 120.0, 90.0, 60.0, 110.0], dtype=float)
    for adstock_type in ('geometric', 'weibull', 'noop'):
        out = apply_adstock(x, adstock_type)
        assert len(out) == len(x), (
            f"apply_adstock(type={adstock_type}): expected len={len(x)}, got len={len(out)}"
        )


def test_apply_adstock_geometric_carryover():
    """Geometric adstock result[t] > x[t] when prior period had positive spend."""
    from aurora_launch.utils.adstock import apply_adstock
    x = np.array([100.0, 0.0, 0.0, 0.0], dtype=float)
    out = apply_adstock(x, 'geometric', {'alpha': 0.5})
    assert out[0] == pytest.approx(100.0)
    # At t=1, x[1]=0 but decay*prev = 0.5*100 = 50
    assert out[1] == pytest.approx(50.0)
    assert out[2] == pytest.approx(25.0)


def test_apply_adstock_noop_passthrough():
    """'noop' adstock should return identical array to input."""
    from aurora_launch.utils.adstock import apply_adstock
    x = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
    out = apply_adstock(x, 'noop')
    np.testing.assert_array_almost_equal(out, x)


def test_geometric_adstock_batch_shape():
    """geometric_adstock_batch output shape = (n_samples, n_periods)."""
    from aurora_launch.utils.adstock import geometric_adstock_batch
    raw_x = np.array([100.0, 50.0, 75.0, 30.0, 90.0], dtype=float)
    decays = np.array([0.3, 0.5, 0.7], dtype=float)
    out = geometric_adstock_batch(raw_x, decays)
    assert out.shape == (3, 5), f"Expected shape (3, 5), got {out.shape}"


# ─── hill_function monotonicity ───────────────────────────────────────────────

def test_hill_function_monotonically_increasing():
    """Hill saturation function must be monotonically increasing in x."""
    from aurora_launch.utils.saturation import hill_function
    x = np.linspace(0.0, 10.0, 200)
    alpha = 1.5
    gamma = 0.5
    y = hill_function(x, alpha=alpha, gamma=gamma)
    diffs = np.diff(y)
    assert np.all(diffs >= -1e-12), (
        f"hill_function not monotonically increasing: min diff={diffs.min():.6f}"
    )


def test_hill_function_bounded_zero_to_one():
    """Hill saturation output must be in [0, 1]."""
    from aurora_launch.utils.saturation import hill_function
    x = np.linspace(0.0, 100.0, 500)
    y = hill_function(x, alpha=2.0, gamma=1.0)
    assert np.all(y >= 0.0), "hill_function output below 0"
    assert np.all(y <= 1.0 + 1e-12), "hill_function output above 1"


def test_hill_function_zero_at_zero():
    """hill_function(0, alpha, gamma) = 0 for any valid alpha, gamma."""
    from aurora_launch.utils.saturation import hill_function
    y = hill_function(np.array([0.0]), alpha=2.0, gamma=0.5)
    assert y[0] == pytest.approx(0.0)


def test_hill_function_half_saturation_at_gamma():
    """hill_function(gamma, alpha=1, gamma=gamma) = 0.5 (Michaelis-Menten property)."""
    from aurora_launch.utils.saturation import hill_function
    gamma_val = 3.0
    y = hill_function(np.array([gamma_val]), alpha=1.0, gamma=gamma_val)
    assert y[0] == pytest.approx(0.5, abs=1e-9)


def test_hill_function_batch_shape():
    """hill_function_batch output shape = (n_samples, n_periods)."""
    from aurora_launch.utils.saturation import hill_function_batch
    x_norm = np.linspace(0, 2, 36)
    alpha_samples = np.array([1.0, 1.5, 2.0])
    gamma_samples = np.array([0.4, 0.5, 0.6])
    out = hill_function_batch(x_norm, alpha_samples, gamma_samples)
    assert out.shape == (3, 36), f"Expected shape (3, 36), got {out.shape}"


# ─── train_model / train_ols importability ────────────────────────────────────

def test_train_model_callable():
    """train_model is importable and callable (no actual PyMC compile)."""
    from aurora_launch.engines.bayesian_engine import train_model
    assert callable(train_model), "train_model must be callable"


def test_train_ols_callable():
    """train_ols is importable and callable (no actual training run)."""
    from aurora_launch.engines.ols_engine import train_ols
    assert callable(train_ols), "train_ols must be callable"


def test_decompose_callable():
    """decompose is importable and callable."""
    from aurora_launch.engines.decompose import decompose
    assert callable(decompose), "decompose must be callable"


def test_load_model_with_compat_callable():
    """load_model_with_compat is importable and callable."""
    from aurora_launch.engines.loader import load_model_with_compat
    assert callable(load_model_with_compat), "load_model_with_compat must be callable"


# ─── channel categorization ───────────────────────────────────────────────────

def test_auto_suggest_category_tv_is_brand():
    """TV channel name should be categorized as brand."""
    from aurora_launch.utils.channel_categorization import auto_suggest_category
    result = auto_suggest_category('TV National')
    assert result['category'] == 'brand', f"Expected brand for 'TV National', got {result}"
    assert result['confidence'] >= 0.7


def test_auto_suggest_category_search_is_performance():
    """Search channel should be categorized as performance."""
    from aurora_launch.utils.channel_categorization import auto_suggest_category
    result = auto_suggest_category('Yandex Search')
    assert result['category'] == 'performance', f"Expected performance for 'Yandex Search', got {result}"


def test_auto_suggest_category_unknown_is_mixed():
    """Unknown channel name should default to mixed."""
    from aurora_launch.utils.channel_categorization import auto_suggest_category
    result = auto_suggest_category('channel_xyz_unknown_1234')
    assert result['category'] == 'mixed'


# ─── ROI verdict logic ────────────────────────────────────────────────────────

def test_compute_roi_verdict_deep_loss():
    """ROI < 0.5 → Глубоко убыточный / bad."""
    from aurora_launch.engines.decompose import compute_roi_verdict
    label, tone = compute_roi_verdict(roi=0.3, efficiency_gap=0.0)
    assert tone == 'bad'
    assert 'убыточ' in label.lower()


def test_compute_roi_verdict_high_roi():
    """ROI > 5 → Высокоэффективен / good."""
    from aurora_launch.engines.decompose import compute_roi_verdict
    label, tone = compute_roi_verdict(roi=6.0, efficiency_gap=5.0)
    assert tone == 'good'


def test_compute_roi_verdict_wide_ci_suffix():
    """Wide CI adds suffix to verdict label."""
    from aurora_launch.engines.decompose import compute_roi_verdict
    label, tone = compute_roi_verdict(
        roi=5.0, efficiency_gap=3.0,
        roi_ci_low=1.0, roi_ci_high=8.0,  # width > roi → wide CI
    )
    assert 'интервал' in label or 'warn' == tone or 'ROI' in label


# ─── Weibull adstock math ─────────────────────────────────────────────────────

def test_weibull_kernel_sums_to_one():
    """weibull_kernel_survival must sum to 1.0."""
    from aurora_launch.utils.adstock import weibull_kernel_survival
    kernel = weibull_kernel_survival(max_decay=26, peak_week=3.0, tail_decay=0.5)
    assert abs(kernel.sum() - 1.0) < 1e-9, f"Kernel sum={kernel.sum()}, expected 1.0"


def test_weibull_kernel_length():
    """weibull_kernel_survival output length equals max_decay."""
    from aurora_launch.utils.adstock import weibull_kernel_survival
    kernel = weibull_kernel_survival(max_decay=13, peak_week=2.0, tail_decay=0.6)
    assert len(kernel) == 13


def test_weibull_kernel_invalid_max_decay_raises():
    """max_decay=0 should raise ValueError."""
    from aurora_launch.utils.adstock import weibull_kernel_survival
    with pytest.raises(ValueError):
        weibull_kernel_survival(max_decay=0, peak_week=3.0, tail_decay=0.5)
