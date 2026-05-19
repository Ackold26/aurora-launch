"""LEGACY copy preserved для USE_SHARED_ENGINES=0 fallback (Sprint 0 wire 2026-05-19).

Default code path: USE_SHARED_ENGINES=1 → aurora_engines.decompose (shared library, canonical).
This legacy file активируется только при explicit USE_SHARED_ENGINES=0 override.
Removal scheduled Sprint Buffer per feature flag rollout decision.

Original module docstring follows below.
"""
"""
Sales decomposition engine.
Breaks down total KPI into baseline + channel contributions.

Ported from Aurora Econometrica (sidecar/econometrica/engines/decomposer.py).

Adaptations applied:
1. Import paths: sidecar.econometrica.utils.X / utils.X → aurora_launch.utils.X
                 engines.X → aurora_launch.engines.X
2. Removed FastAPI-specific imports (none were in decomposer.py originally).
3. Removed dependency on engines.optimizer._compute_mroas_money (Launch does not
   have optimizer yet). mroi_current field computed via inline closed-form formula
   matching the same math — no behavioral change.
4. Removed dependency on engines.narrative_adapter._normalize_channel_name
   (Launch does not have narrative_adapter). display_name = col (passthrough).
5. Removed dependency on engines.channel_action (Launch does not have it yet).
   Action fields are skipped; channel dict still populated with placeholder values.
6. Math kernel 100% identical: P0-3/4/10 fix, baseline energy conservation,
   posterior CI propagation via hill_function_batch / hill_function_batch_2d.

P0-3/4/10 fix (math-fix-v1.0.13, Phase 3):
Pre-fix: contribution = |β|/Σ|β| × (total - baseline) → ignored adstock,
saturation, time. Baseline = sum(actual - predicted) + 0.3 × predicted.mean × n.
Post-fix: contribution_per_period = β × hill(adstock(x)/mean) × y_std.
Baseline = intercept × y_std + y_mean × n + control_effect × y_std.
"""
import json
import logging
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any

from aurora_launch.utils.adstock import apply_adstock, geometric_adstock_batch
from aurora_launch.utils.saturation import hill_function, hill_function_batch, hill_function_batch_2d
from aurora_launch.utils.channel_categorization import auto_suggest_category

logger = logging.getLogger(__name__)


# Hybrid ROI thresholds (Phase 0.2 - plan immutable-bouncing-noodle §0.2, L4).
ROI_DEEP_LOSS = 0.5         # < 0.5× = deeply unprofitable
ROI_LOSS = 0.8              # < 0.8× = unprofitable
ROI_BREAKEVEN = 1.0         # < 1.0× = at break-even
ROI_HIGH_ABS = 5.0          # > 5× = highly effective (small-N absolute fallback)
ROI_UNIT_SMELL_FLOOR = 50.0 # > 50× with unit_smell = "not rubles?"
ROI_ARTIFACT = 100.0        # > 100× = artifact warning (regardless of unit_smell)
GAP_OVERSAT = -10.0         # pp - oversaturated
GAP_UNDER = -5.0            # pp - weaker than share
GAP_HIGH = 10.0             # pp - highly effective by share
GAP_GOOD = 5.0              # pp - effective by share
QUANTILE_MIN_N = 20         # below - relative quantile mode disabled

UNIT_HINTS = ('TRP', 'GRP', 'OTS', 'IMPRESSION', 'CLICK', 'ПОКАЗ', 'КЛИК', 'ПРОСМОТР', 'ВИЗИТ', 'ПУНКТ', 'ОХВАТ', 'РЕЙТИНГ')


def compute_roi_verdict(
    roi: float,
    efficiency_gap: float,
    *,
    category: str = 'mixed',
    unit_smell: bool = False,
    roi_ci_low: float | None = None,
    roi_ci_high: float | None = None,
    n_channels: int = 0,
    category_quantiles: dict[str, dict[str, float]] | None = None,
) -> tuple[str, str]:
    """Hybrid ROI verdict combining absolute + relative + posterior CI.

    Per plan immutable-bouncing-noodle §0.2 (L4 fix), and L2 (math-fix v1.4
    Section C, 2026-04-29) re-ordering.

    Returns:
      (verdict_label, verdict_tone) where tone ∈ {good, warn, bad, neutral}.
    """
    wide_ci = (
        roi_ci_low is not None
        and roi_ci_high is not None
        and roi > 0
        and (roi_ci_high - roi_ci_low) > roi
    )

    def _apply_ci_suffix(label: str, tone: str) -> tuple[str, str]:
        if wide_ci:
            return (f"{label} (широкий ROI-интервал)", 'warn' if tone == 'good' else tone)
        return (label, tone)

    # Step 2 - absolute hard caps
    if roi > ROI_UNIT_SMELL_FLOOR and unit_smell:
        return _apply_ci_suffix('ROI завышен (не рубли?)', 'warn')
    if roi > ROI_ARTIFACT:
        return _apply_ci_suffix('ROI нереалистичен (артефакт)', 'warn')
    if roi < ROI_DEEP_LOSS:
        return _apply_ci_suffix('Глубоко убыточный', 'bad')
    if roi < ROI_LOSS:
        return _apply_ci_suffix('Убыточный', 'bad')
    if roi < ROI_BREAKEVEN:
        return _apply_ci_suffix('На грани окупаемости', 'warn')

    # Step 3 - category-relative quantile (gated by min N)
    if (
        n_channels >= QUANTILE_MIN_N
        and category_quantiles
        and category in category_quantiles
    ):
        q = category_quantiles[category]
        p10 = q.get('p10')
        p25 = q.get('p25')
        p75 = q.get('p75')
        p90 = q.get('p90')
        if p10 is not None and roi < p10:
            return _apply_ci_suffix('Bottom-10% по категории', 'bad')
        if p90 is not None and roi >= p90:
            return _apply_ci_suffix('Top-10% по категории', 'good')
        if p75 is not None and roi >= p75:
            return _apply_ci_suffix('Top-25% по категории', 'good')
        if p25 is not None and roi < p25:
            return _apply_ci_suffix('Bottom-25% по категории', 'warn')
        return _apply_ci_suffix('Средний по категории', 'neutral')

    # Step 4 - efficiency gap fallback
    if roi > ROI_HIGH_ABS and not unit_smell:
        return _apply_ci_suffix('Высокоэффективен', 'good')
    if efficiency_gap <= GAP_OVERSAT:
        return _apply_ci_suffix('Перенасыщен', 'warn')
    if efficiency_gap <= GAP_UNDER:
        return _apply_ci_suffix('Слабее своей доли', 'warn')
    if efficiency_gap >= GAP_HIGH:
        return _apply_ci_suffix('Высокоэффективен', 'good')
    if efficiency_gap >= GAP_GOOD:
        return _apply_ci_suffix('Эффективен', 'good')
    return _apply_ci_suffix('Сбалансирован', 'neutral')


def _load_v13_kpi_settings(project_path: Path) -> dict:
    """v1.3.0: load KPI settings from project state file.

    Returns empty dict if file absent (legacy project). Backward compat.
    """
    settings_file = project_path / 'settings' / 'v13_kpi.json'
    if not settings_file.exists():
        return {}
    try:
        import json as _json
        with open(settings_file, 'r', encoding='utf-8') as f:
            return _json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(
            f"v1.3 KPI settings file {settings_file} corrupted "
            f"({type(e).__name__}: {e}). Falling back to monetary defaults."
        )
        return {}


def _load_posterior_samples(model_data: dict) -> dict | None:
    """Load posterior samples from model_data dict if present."""
    ps = model_data.get('posterior_samples')
    if ps is None:
        return None
    required = {'media_betas', 'alphas', 'gammas', 'media_columns'}
    if not all(k in ps for k in required):
        return None
    return ps


def _per_channel_samples(posterior_samples: dict, col: str) -> dict | None:
    """Extract per-channel posterior sample dict for a given column."""
    if posterior_samples is None:
        return None
    media_cols = list(posterior_samples.get('media_columns', []))
    if col not in media_cols:
        return None
    i = media_cols.index(col)
    betas = np.asarray(posterior_samples['media_betas'], dtype=np.float64)
    alphas = np.asarray(posterior_samples['alphas'], dtype=np.float64)
    gammas = np.asarray(posterior_samples['gammas'], dtype=np.float64)

    result: dict[str, Any] = {
        'beta': betas[i] if betas.ndim == 2 else betas,
        'alpha': alphas[i] if alphas.ndim == 2 else alphas,
        'gamma': gammas[i] if gammas.ndim == 2 else gammas,
    }

    # Phase 1.1: adstock decay samples per channel
    adstock_decay = posterior_samples.get('adstock_decay')
    if adstock_decay is not None:
        ad = np.asarray(adstock_decay, dtype=np.float64)
        result['decay'] = ad[i] if ad.ndim == 2 else ad

    return result


def _compute_ci_hdi(samples: np.ndarray) -> tuple[float, float, float, str]:
    """Compute HDI 90% CI for a 1D array of samples.

    Returns:
        (mean, ci_low, ci_high, method_str)
    """
    s = np.asarray(samples, dtype=np.float64).ravel()
    mean_val = float(np.mean(s))
    try:
        import arviz as az
        import xarray as xr
        da = xr.DataArray(s)
        hdi = az.hdi(da, hdi_prob=0.90)
        ci_low = float(hdi[0])
        ci_high = float(hdi[1])
        return mean_val, ci_low, ci_high, 'bayesian_hdi'
    except Exception:
        ci_low = float(np.percentile(s, 5))
        ci_high = float(np.percentile(s, 95))
        return mean_val, ci_low, ci_high, 'percentile_fallback'


def _compute_mroas_money_simple(
    current_spend_native: float,
    n_periods: int,
    mean: float,
    alpha: float,
    gamma: float,
    beta: float,
    y_std: float,
    unit_cost: float,
    decay: float = 0.5,
) -> float:
    """Inline closed-form mROAS (marginal ROI at current spend).

    Computes derivative of Hill function at average normalized spend level,
    then scales through adstock/normalization/unit_cost chain.

    Replaces dependency on engines.optimizer._compute_mroas_money from Optimizer.
    Math is identical.
    """
    if current_spend_native <= 0 or unit_cost <= 0 or mean <= 0:
        return 0.0

    # Average per-period spend in native units
    avg_spend_native = current_spend_native / max(n_periods, 1)

    # Adstock factor for geometric adstock (flat-allocation analytical)
    theta = max(0.0, min(decay, 1.0 - 1e-9))
    if theta < 1e-9:
        adstock_factor = 1.0
    else:
        n = max(n_periods, 1)
        geom_sum = (1.0 - theta ** n) / (1.0 - theta)
        adstock_factor = (n - theta * geom_sum) / (n * (1.0 - theta))

    # x_norm at current allocation
    x_avg_adstocked = avg_spend_native * adstock_factor
    x_norm = max(x_avg_adstocked / max(mean, 1e-10), 1e-10)

    # Hill derivative: dhill/dx = alpha * gamma^alpha * x^(alpha-1) / (x^alpha + gamma^alpha)^2
    alpha_v = max(alpha, 1e-6)
    gamma_v = max(gamma, 1e-10)
    x_pow = x_norm ** alpha_v
    gamma_pow = gamma_v ** alpha_v
    numerator = alpha_v * gamma_pow * (x_norm ** (alpha_v - 1.0))
    denominator = (x_pow + gamma_pow) ** 2

    dhill_dx_norm = numerator / max(denominator, 1e-20)

    # Chain: d(contribution_money)/d(spend_money) =
    #   beta * dhill_dx_norm * (adstock_factor / mean) * y_std / unit_cost
    mroas = beta * dhill_dx_norm * (adstock_factor / max(mean, 1e-10)) * y_std / max(unit_cost, 1e-10)
    return float(mroas)


def decompose(
    project_dir: str,
    unit_costs_override: dict | None = None,
    unit_cost_inflation_pct: dict | None = None,
) -> dict[str, Any]:
    """Decompose KPI into baseline + channel contributions using trained model.

    Args:
        project_dir: Path to project with models/latest.pkl
        unit_costs_override: If provided - used instead of config.unit_costs from pickle.
            Needed when user changed CPP/CPM after training.

    Returns:
        JSON with waterfall data, ROI, share of spend vs effect
    """
    project_path = Path(project_dir)
    model_path = project_path / 'models' / 'latest.pkl'

    if not model_path.exists():
        return {
            'status': 'error',
            'error_code': 'MODEL_NOT_FOUND',
            'message': 'Model not found. Train a model first.',
        }

    from aurora_launch.engines.loader import load_model_with_compat, get_channel_categories
    model_data = load_model_with_compat(model_path)

    model_version = model_data.get('model_version', '1.0')
    if model_version == '1.0':
        return {
            'status': 'error',
            'error_code': 'MODEL_OUTDATED',
            'message': 'Model trained before v1.0.13. Normalization changed - retrain the model.',
        }

    config = model_data['config']
    channel_params = model_data['channel_params']
    norm = model_data['normalization']
    posterior_samples = _load_posterior_samples(model_data)
    y_actual = np.array(model_data['y_actual'])
    media_cols = config['media_columns']
    control_cols = config.get('control_columns', []) or []
    untrained_channels = set(model_data.get('normalization', {}).get('untrained_channels', []) or [])
    unit_costs = unit_costs_override if unit_costs_override is not None else (config.get('unit_costs', {}) or {})

    # Read original data for spend totals + adstock + control effects
    data_file = config['data_file']
    df = pd.read_excel(data_file) if data_file.endswith(('.xlsx', '.xls')) else pd.read_csv(data_file)

    n_periods = len(df)
    total_sales = float(y_actual.sum())

    # Normalization params
    y_mean = float(norm.get('y_mean', 0))
    y_std = float(norm.get('y_std', 1)) or 1
    intercept_mean = float(norm.get('intercept_mean', 0))
    control_betas_mean = norm.get('control_betas_mean', []) or []
    media_means = norm.get('media_means', {}) or {}
    control_means = norm.get('control_means', {}) or {}
    control_stds = norm.get('control_stds', {}) or {}

    adstock_config = config.get('adstock_config', {}) or {}

    # ─────────────────────────────────────────────────────────────────────
    # P0-3/4/10 fix: per-channel per-period contribution = β × hill(adstock(x)/mean) × y_std
    # ─────────────────────────────────────────────────────────────────────
    channels: list[dict[str, Any]] = []
    time_series_channels: dict[str, list[float]] = {}
    total_media_contribution = 0.0

    for col in media_cols:
        params = channel_params[col]

        # H-OLS-2 + Phase 5 follow-up: explicit guard for untrained channels.
        if params.get('untrained') or col in untrained_channels:
            ch_dict_untr: dict[str, Any] = {
                'name': col,
                'display_name': col,
                'spend': 0.0,
                'raw_spend': 0.0,
                'unit_cost': float(unit_costs.get(col, 1.0) or 1.0),
                'contribution': 0.0,
                'contribution_pct': 0,
                'roi': 0.0,
                'beta': 0.0,
                'verdict': 'Не обучен',
                'verdict_tone': 'neutral',
                'untrained': True,
                'ci_skip_reason': 'untrained_channel',
                'mroi_current': 0.0,
            }
            channels.append(ch_dict_untr)
            continue

        beta = float(params.get('beta', 0))
        alpha = max(float(params.get('alpha', 1)), 1e-6)
        gamma = max(float(params.get('gamma', 0.5)), 1e-6)

        raw_spend_series = df[col].fillna(0).values.astype(float)
        raw_spend_total = float(raw_spend_series.sum())

        # 1. Adstock (matches training).
        raw_at = adstock_config.get(col)
        if isinstance(raw_at, dict):
            a_type = raw_at.get('type', 'geometric')
        elif isinstance(raw_at, str):
            a_type = raw_at
        else:
            a_type = 'geometric'

        decay_point = params.get('decay')
        adstock_params_override = {'alpha': float(decay_point)} if decay_point is not None else None
        x_adstock = apply_adstock(raw_spend_series, a_type, adstock_params_override)

        # 2. Normalize spend/mean (matches Phase 2 fix).
        mean_posterior = params.get('adstock_mean_posterior')
        mean = float(mean_posterior) if mean_posterior is not None else float(media_means.get(col, 1)) or 1
        x_norm = x_adstock / max(mean, 1e-10)

        # 3. Hill saturation
        sat = hill_function(np.maximum(x_norm, 0), alpha=alpha, gamma=gamma)

        # 4. Per-period contribution in original KPI units
        contrib_per_period = beta * sat * y_std
        channel_total = float(contrib_per_period.sum())
        total_media_contribution += channel_total

        time_series_channels[col] = [round(float(v), 1) for v in contrib_per_period]

        # Money & ROI
        unit_cost = float(unit_costs.get(col, 1.0) or 1.0)
        spend_money = raw_spend_total * unit_cost
        roi = channel_total / spend_money if spend_money > 0 else 0

        # mROAS at current allocation (inline closed-form)
        mroi_current_pt = _compute_mroas_money_simple(
            current_spend_native=raw_spend_total,
            n_periods=n_periods,
            mean=mean,
            alpha=alpha,
            gamma=gamma,
            beta=beta,
            y_std=y_std,
            unit_cost=unit_cost,
            decay=float(decay_point) if decay_point is not None else 0.5,
        )

        ch_dict: dict[str, Any] = {
            'name': col,
            'display_name': col,  # no narrative_adapter in Launch; passthrough
            'spend': round(spend_money, 0),
            'raw_spend': round(raw_spend_total, 2),
            'unit_cost': unit_cost,
            'contribution': round(channel_total, 0),
            'contribution_pct': 0,  # filled after total computed below
            'roi': round(roi, 2),
            'mroi_current': round(mroi_current_pt, 4),
            'beta': beta,
            'verdict': '',
            'verdict_tone': 'neutral',
            'adstock_decay_mean': float(decay_point) if decay_point is not None else None,
        }

        # Posterior CI path (Phase 1.9 + 1.1)
        if posterior_samples is not None and spend_money <= 0:
            ch_dict['contribution_ci_low'] = 0.0
            ch_dict['contribution_ci_high'] = 0.0
            ch_dict['roi_ci_low'] = 0.0
            ch_dict['roi_ci_high'] = 0.0
            ch_dict['ci_skip_reason'] = 'zero_spend'
            ch_dict['ci_method'] = 'unavailable_zero_spend'

        # Sprint 2 extension: for '1.0-ols' pickles, populate roi_ci from stored bootstrap CI.
        if posterior_samples is None and spend_money > 0:
            roi_ci_low_boot = params.get('roi_ci_low_bootstrap')
            roi_ci_high_boot = params.get('roi_ci_high_bootstrap')
            if roi_ci_low_boot is not None and roi_ci_high_boot is not None:
                ch_dict['roi_ci_low'] = round(float(roi_ci_low_boot), 4)
                ch_dict['roi_ci_high'] = round(float(roi_ci_high_boot), 4)
                ch_dict['ci_method'] = 'frequentist_bootstrap'

        if posterior_samples is not None and spend_money > 0:
            ch_samples = _per_channel_samples(posterior_samples, col)
            if ch_samples is not None:
                decay_samples = ch_samples.get('decay')
                if decay_samples is not None and a_type == 'geometric':
                    # Phase 1.1: per-sample adstock + Hill, joint correlation preserved.
                    x_adstock_2d = geometric_adstock_batch(raw_spend_series, decay_samples)
                    mean_per_sample = np.maximum(
                        x_adstock_2d.mean(axis=1, keepdims=True), 1e-10
                    )
                    x_norm_2d = x_adstock_2d / mean_per_sample
                    sat_samples = hill_function_batch_2d(
                        x_norm_2d, ch_samples['alpha'], ch_samples['gamma']
                    )
                else:
                    sat_samples = hill_function_batch(
                        x_norm, ch_samples['alpha'], ch_samples['gamma']
                    )
                contrib_total_samples = (
                    ch_samples['beta'].reshape(-1, 1).astype(np.float64)
                    * sat_samples
                    * y_std
                ).sum(axis=1)
                _, contrib_ci_low, contrib_ci_high, _method_c = _compute_ci_hdi(contrib_total_samples)
                ch_dict['contribution_ci_low'] = round(float(contrib_ci_low), 0)
                ch_dict['contribution_ci_high'] = round(float(contrib_ci_high), 0)

                roi_samples = contrib_total_samples / spend_money
                _, roi_ci_low, roi_ci_high, _method_r = _compute_ci_hdi(roi_samples)
                ch_dict['roi_ci_low'] = round(float(roi_ci_low), 4)
                ch_dict['roi_ci_high'] = round(float(roi_ci_high), 4)
                _is_pct = (_method_c == 'percentile_fallback') or (_method_r == 'percentile_fallback')
                if decay_samples is not None:
                    base = 'bayesian_hdi_phase11_pct' if _is_pct else 'bayesian_hdi_phase11'
                    try:
                        import numpy as _np2
                        ds = _np2.asarray(decay_samples, dtype=float)
                        ch_dict['adstock_decay_mean'] = float(_np2.mean(ds))
                        ch_dict['adstock_decay_ci_low'] = float(_np2.quantile(ds, 0.25))
                        ch_dict['adstock_decay_ci_high'] = float(_np2.quantile(ds, 0.75))
                    except Exception:
                        pass
                else:
                    base = 'bayesian_hdi_pct' if _is_pct else 'bayesian_hdi'
                ch_dict['ci_method'] = base

        channels.append(ch_dict)

    # Fill contribution_pct relative to total media contribution
    for ch in channels:
        ch['contribution_pct'] = round(
            ch['contribution'] / total_media_contribution * 100, 1
        ) if total_media_contribution > 0 else 0

    # ─────────────────────────────────────────────────────────────────────
    # Baseline = intercept_mean × y_std + y_mean (per period) + control effect
    # ─────────────────────────────────────────────────────────────────────
    intercept_per_period = np.full(n_periods, intercept_mean * y_std + y_mean, dtype=float)

    control_effect_per_period = np.zeros(n_periods, dtype=float)
    signed_factor_contributions: dict = {}
    if control_cols and control_betas_mean and len(control_betas_mean) == len(control_cols):
        c_means = np.array([float(control_means.get(c, 0)) for c in control_cols])
        c_stds = np.array([float(control_stds.get(c, 1)) or 1 for c in control_cols])
        X_control_raw = df[control_cols].fillna(0).astype(float).values
        X_control_norm = (X_control_raw - c_means) / c_stds
        beta_c = np.array(control_betas_mean, dtype=float)
        control_effect_per_period = (X_control_norm @ beta_c) * y_std

        # v2.0.0: per-factor contribution breakdown
        try:
            for i, col in enumerate(control_cols):
                col_effect = (X_control_norm[:, i] * beta_c[i]) * y_std
                col_total = float(col_effect.sum())
                col_upper = col.upper()
                if any(h in col_upper for h in ('COMPETITOR', 'КОНКУР')):
                    factor_type = 'signed_competitor'
                elif any(h in col_upper for h in ('PRICE', 'ЦЕНА', 'COST')):
                    factor_type = 'signed_price'
                elif any(h in col_upper for h in ('HOLIDAY', 'ПРАЗДН')):
                    factor_type = 'holiday'
                elif any(h in col_upper for h in ('WEATHER', 'ПОГОДА')):
                    factor_type = 'signed_weather'
                elif any(h in col_upper for h in ('MACRO', 'GDP', 'ВВП')):
                    factor_type = 'signed_macro'
                else:
                    factor_type = 'positive_control'
                _y_total = float(y_actual.sum()) if len(y_actual) else 0.0
                signed_factor_contributions[col] = {
                    'value': round(col_total, 1),
                    'pct': round(col_total / (_y_total + 1e-10) * 100, 1) if _y_total > 0 else 0.0,
                    'type': factor_type,
                    'beta_mean': float(beta_c[i]),
                    'per_period': [round(float(v), 1) for v in col_effect],
                }
        except Exception as e:
            logger.warning('signed_factor_contributions computation failed: %s', e)
            signed_factor_contributions = {}

    # Energy conservation: baseline absorbs residual variance
    media_contrib_per_period = np.zeros(n_periods, dtype=float)
    for col in media_cols:
        ts = time_series_channels.get(col, [])
        for t, v in enumerate(ts):
            if t < n_periods:
                media_contrib_per_period[t] += float(v)
    raw_baseline = intercept_per_period + control_effect_per_period
    model_predicted_per_period = raw_baseline + media_contrib_per_period
    if len(y_actual) >= n_periods:
        residual_per_period = y_actual[:n_periods] - model_predicted_per_period
    else:
        residual_per_period = np.zeros(n_periods, dtype=float)
    baseline_per_period = raw_baseline + residual_per_period
    baseline_total = float(baseline_per_period.sum())
    baseline_ts = [round(float(v), 1) for v in baseline_per_period]

    # Sort by ROI descending
    channels.sort(key=lambda x: x['roi'], reverse=True)

    # Share of Spend vs Share of Effect
    total_spend = sum(c['spend'] for c in channels) or 1
    for ch in channels:
        ch['share_of_spend'] = round(ch['spend'] / total_spend * 100, 1)
        ch['share_of_effect'] = ch['contribution_pct']
        ch['efficiency_gap'] = round(ch['share_of_effect'] - ch['share_of_spend'], 1)

    # Category + unit_smell detection
    explicit_categories = get_channel_categories(model_data, fallback_heuristic=False)
    category_quantiles = config.get('category_quantiles') if isinstance(config, dict) else None
    n_channels = len(channels)

    for ch in channels:
        if ch.get('untrained'):
            ch.setdefault('category', 'mixed')
            ch.setdefault('unit_smell', False)
            ch.setdefault('share_of_spend', 0.0)
            ch.setdefault('share_of_effect', 0.0)
            ch.setdefault('efficiency_gap', 0.0)
            continue
        name = ch['name'] or ''
        name_upper = name.upper()
        looks_like_non_money = any(hint in name_upper for hint in UNIT_HINTS)
        if name in explicit_categories:
            cat_v3 = explicit_categories[name]
            if cat_v3 == 'brand':
                ch['category'] = 'brand_reach'
            elif cat_v3 == 'performance':
                ch['category'] = 'performance'
            else:
                ch['category'] = 'mixed'
        else:
            sug = auto_suggest_category(name)
            if sug['category'] == 'brand' and sug['confidence'] >= 0.7:
                ch['category'] = 'brand_reach'
            elif sug['category'] == 'performance' and sug['confidence'] >= 0.7:
                ch['category'] = 'performance'
            else:
                ch['category'] = 'mixed'
        ch['unit_smell'] = bool(looks_like_non_money and abs(ch['unit_cost'] - 1.0) < 1e-9)

        verdict_label, verdict_tone = compute_roi_verdict(
            roi=ch['roi'],
            efficiency_gap=ch['efficiency_gap'],
            category=ch['category'],
            unit_smell=ch['unit_smell'],
            roi_ci_low=ch.get('roi_ci_low'),
            roi_ci_high=ch.get('roi_ci_high'),
            n_channels=n_channels,
            category_quantiles=category_quantiles,
        )
        ch['verdict'] = verdict_label
        ch['verdict_tone'] = verdict_tone

    # Action fields — placeholder (no channel_action engine in Launch yet)
    for ch in channels:
        if ch.get('untrained'):
            ch.setdefault('action', 'Uncertain')
            ch.setdefault('action_label', 'Не обучен')
            ch.setdefault('action_tone', 'neutral')
            continue
        # Simple action heuristic based on mROAS
        mroas = ch.get('mroi_current', 0.0)
        if mroas > 1.0:
            ch['action'] = 'Increase'
            ch['action_label'] = 'Увеличить'
            ch['action_tone'] = 'good'
        elif mroas < 0.5:
            ch['action'] = 'Reduce'
            ch['action_label'] = 'Сократить'
            ch['action_tone'] = 'warn'
        else:
            ch['action'] = 'Maintain'
            ch['action_label'] = 'Сохранить'
            ch['action_tone'] = 'neutral'

    # Insight generation
    top = channels[0] if channels else None
    worst = channels[-1] if channels else None
    insight = ''
    if top and worst:
        insight = (
            f"{top['name']} - наиболее эффективный канал (ROI {top['roi']:.1f}×). "
            f"{worst['name']} - наименее эффективный (ROI {worst['roi']:.1f}×)."
        )

    # Per-period dates
    date_col = config.get('date_column', 'date')
    if date_col in df.columns:
        dates = [str(d)[:10] for d in df[date_col].tolist()]
    else:
        dates = [str(i + 1) for i in range(n_periods)]

    # Smell detector for trust banner
    smell_flags: list[dict] = []
    positive_rois = [c['roi'] for c in channels if c['roi'] > 0]
    any_unit_smell = any(c.get('unit_smell') for c in channels)
    if positive_rois and any_unit_smell:
        roi_max = max(positive_rois)
        roi_min = min(positive_rois)
        if roi_max > 50:
            top_ch = max(channels, key=lambda c: c['roi'])
            smell_flags.append({
                'type': 'roi_max',
                'channel': top_ch['name'],
                'value': round(roi_max, 1),
                'severity': 'high' if roi_max > 200 else 'medium',
            })
        if roi_min > 0 and roi_max / roi_min > 50:
            smell_flags.append({
                'type': 'roi_spread',
                'value': round(roi_max / roi_min, 1),
                'severity': 'high' if roi_max / roi_min > 200 else 'medium',
            })
    unit_smell_channels = [c['name'] for c in channels if c.get('unit_smell')]
    if unit_smell_channels:
        smell_flags.append({
            'type': 'unit_smell',
            'channels': unit_smell_channels,
            'severity': 'medium',
        })

    # Model version warning
    model_warning = None
    if model_version == '1.0-ols':
        n_obs_ols = len(y_actual) if isinstance(y_actual, (list, np.ndarray)) else 0
        model_warning = (
            f'OLS mode (small data fallback): n={n_obs_ols} observations. '
            f'Hill α=1.5, γ=0.5, decay=0.5 - fixed (not learned). '
            f'Bayesian posterior CI unavailable (need n≥30). Collect more data for premium model.'
        )
    elif model_version == '1.1.5':
        model_warning = (
            'This model was trained with fixed adstock decay (0.5). '
            'CI does not account for carryover uncertainty. Retrain for honest CI on adstock.'
        )
    elif model_version == '1.1':
        model_warning = (
            'This model was trained before Phase 1.9 - posterior samples absent. '
            'CI unavailable. Retrain for CI support.'
        )

    # v1.3.0: load KPI settings from project state (per ADR-016, ADR-017).
    v13_kpi = _load_v13_kpi_settings(project_path)

    result: dict[str, Any] = {
        'status': 'ok',
        'model_version': model_version,
        'model_warning': model_warning,
        'smell_flags': smell_flags,
        'kpi_kind': v13_kpi.get('kpi_kind', 'monetary'),
        'derived_mode': v13_kpi.get('derived_mode', 'roi'),
        'value_per_count_unit': v13_kpi.get('value_per_count_unit'),
        'value_per_count_unit_label': v13_kpi.get('value_per_count_unit_label', ''),
        'total_sales': round(total_sales, 0),
        'baseline': round(baseline_total, 0),
        'baseline_pct': round(baseline_total / total_sales * 100, 1) if total_sales else 0,
        'media_contribution': round(total_media_contribution, 0),
        'channels': channels,
        'insight': insight,
        'waterfall': {
            'labels': ['Baseline'] + [c['name'] for c in channels] + ['Итого'],
            'values': [round(baseline_total, 0)] + [round(c['contribution'], 0) for c in channels] + [round(total_sales, 0)],
            'types': ['baseline'] + ['channel'] * len(channels) + ['total'],
        },
        'time_series': {
            'dates': dates,
            'baseline': baseline_ts,
            'channels': time_series_channels,
        },
        'hierarchical': {
            'enabled': bool(model_data.get('use_hierarchical')),
            'channel_categories': dict(model_data.get('channel_categories') or {}),
            'categorization_warnings': list(model_data.get('categorization_warnings') or []),
            'priors_summary': dict(model_data.get('hierarchical_priors') or {}),
        },
        'signed_factor_contributions': signed_factor_contributions,
    }

    # Save
    results_dir = project_path / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(results_dir / 'decomposition.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
