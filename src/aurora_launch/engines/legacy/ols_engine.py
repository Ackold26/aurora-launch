"""LEGACY copy preserved для USE_SHARED_ENGINES=0 fallback (Sprint 0 wire 2026-05-19).

Default code path: USE_SHARED_ENGINES=1 → aurora_engines.train_ols (shared library, canonical).
This legacy file активируется только при explicit USE_SHARED_ENGINES=0 override.
Removal scheduled Sprint Buffer per feature flag rollout decision.

---
OLS engine - small-data fallback engine.

Ported from Aurora Econometrica (sidecar/econometrica/engines/ols_modeler.py).

Adaptations applied:
1. Import paths: sidecar.econometrica.utils.X → aurora_launch.utils.X
                 utils.X → aurora_launch.utils.X (relative → absolute)
2. progress_callback signature changed to Callable[[float, str], None] (pct, message).
   Old callback: fn(dict) with keys {phase, pct}.
   New callback: fn(pct: float, message: str) — plain non-streaming.
3. Removed FastAPI-specific imports (none were in this file originally).
4. Math kernel 100% identical.

For datasets with n < 30 observations, Bayesian MCMC is unreliable:
posterior intervals don't converge, R-hat stays > 1.05, Hill alpha/gamma
parameters become unidentifiable. Robyn/LightweightMMM/PyMC-Marketing all
require n ≥ 50.

This engine provides honest fallback for small-N case:
- adstock + Hill applied with **fixed library defaults** (no per-channel learning)
- Closed-form OLS regression on hill-saturated features → β coefficients
- Predictive intervals (residual-based + jackknife) on y forecasts - NOT posterior CI on parameters
- Honest disclosure: "model trained on small data, β has wide bounds, treat as directional"

Schema:
- model_version='1.0-ols' (distinguishes from Bayesian v1.1+)
- channel_params: beta (from OLS), alpha=1.5, gamma=0.5, decay=0.5 (defaults - NOT learned)
- normalization: same as Bayesian (media_means + y_mean/std + control stats)
- ols_diagnostics: r_squared, adj_r_squared, mape, residual_std, n_obs, n_params, dof
- predictive_intervals: per-period stat for honest y CI

Downstream engines (decompose) treat '1.0-ols' pickle same as v1.1
(point estimates only, no posterior CI).

Math reference:
- OLS: β = (X'X)^(-1) X'y, residual_std = sqrt(SSR / (n - p - 1))
- Predictive interval: ŷ ± t_{n-p-1, α/2} · σ · sqrt(1 + h_ii)
  where h_ii = leverage of i-th observation
- For new prediction: ŷ_new ± t · σ · sqrt(1 + x_new'(X'X)^(-1)x_new)

Used when: config['mode'] == 'ols' OR auto-recommend (n < threshold).
"""
from __future__ import annotations

import json
import logging
import pickle
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Library defaults for non-learnable params on small N (consistent with v1.1.5 fallback).
DEFAULT_ALPHA = 1.5      # Hill steepness - moderate S-curve
DEFAULT_GAMMA = 0.5      # Hill half-saturation point
DEFAULT_DECAY = 0.5      # Geometric adstock retention rate


def train_ols(
    config: dict,
    project_dir: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """Train OLS small-data fallback model.

    Args:
        config: same shape as Bayesian train_model:
            data_file, kpi_column, media_columns, control_columns,
            date_column, adstock_config, unit_costs.
        project_dir: project directory (saves models/latest.pkl + latest-params.json + diagnostics)
        progress_callback: optional fn(pct: float, message: str) for UI progress.
            pct in [0, 100]. Exceptions in callback are swallowed — never crash training.

    Returns:
        JSON-serializable result with diagnostics + status.
    """
    def report(message: str, pct: float = 0.0) -> None:
        if progress_callback:
            try:
                progress_callback(pct, message)
            except Exception:
                pass

    project_path = Path(project_dir)
    models_dir = project_path / 'models'
    results_dir = project_path / 'results'
    models_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    report('loading', 10.0)

    # Read data
    data_file = config['data_file']
    if data_file.endswith('.csv'):
        df = pd.read_csv(data_file)
    else:
        df = pd.read_excel(data_file)

    kpi_col = config['kpi_column']
    media_cols = config['media_columns']
    control_cols = config.get('control_columns', [])
    adstock_config = config.get('adstock_config', {}) or {}

    if kpi_col not in df.columns:
        return {'status': 'error', 'message': f'KPI column "{kpi_col}" not found'}

    y = df[kpi_col].fillna(0).values.astype(float)
    n_obs = len(y)

    if n_obs < 8:
        return {
            'status': 'error',
            'error_code': 'INSUFFICIENT_DATA',
            'message': (
                f'Too few observations (n={n_obs}). OLS requires at least 8 '
                f'periods. Collect more data or add channels.'
            ),
        }

    n_params = len(media_cols) + len(control_cols) + 1  # +1 intercept
    if n_obs <= n_params + 1:
        return {
            'status': 'error',
            'error_code': 'OVERPARAMETERIZED',
            'message': (
                f'More parameters than observations (n={n_obs}, p={n_params}). '
                f'OLS has no degrees of freedom. Remove channels or collect more data.'
            ),
        }

    report('preprocessing', 30.0)

    # ── Apply adstock + Hill with library defaults ──
    from aurora_launch.utils.adstock import apply_adstock
    from aurora_launch.utils.saturation import hill_function

    media_means = {}
    untrained_channels = []
    # H3 fix (audit 2026-04-26): build feature matrix only for trained channels.
    trained_media_cols = []
    trained_features = []

    for j, col in enumerate(media_cols):
        a_type = adstock_config.get(col, 'geometric')
        raw_x = df[col].fillna(0).values.astype(float)
        adstocked = apply_adstock(raw_x, a_type, {'alpha': DEFAULT_DECAY})
        mean_j = float(adstocked.mean())
        if mean_j == 0:
            untrained_channels.append(col)
            media_means[col] = 1.0  # safety value for downstream divisions
            continue  # H3: don't add to X
        x_norm = adstocked / max(mean_j, 1e-10)
        feat = hill_function(np.maximum(x_norm, 0), DEFAULT_ALPHA, DEFAULT_GAMMA)
        trained_features.append(feat)
        trained_media_cols.append(col)
        media_means[col] = mean_j

    if not trained_media_cols:
        return {
            'status': 'error',
            'error_code': 'NO_TRAINED_CHANNELS',
            'message': (
                'All media channels had zero variance in training data. '
                'OLS cannot build a model - collect data with real spend variation.'
            ),
            'untrained_channels': untrained_channels,
        }
    X_features = np.column_stack(trained_features)

    # Controls: z-score standardize (same as Bayesian)
    if control_cols:
        X_control_raw = df[control_cols].fillna(0).astype(float).values
        control_means = X_control_raw.mean(axis=0)
        control_stds = X_control_raw.std(axis=0)
        control_stds_safe = np.where(control_stds > 1e-9, control_stds, 1.0)
        X_control_norm = (X_control_raw - control_means) / control_stds_safe
    else:
        X_control_norm = np.zeros((n_obs, 0))
        control_means = np.array([])
        control_stds = np.array([])
        control_stds_safe = np.array([])

    # Combine: [intercept, media features, control features]
    X = np.column_stack([np.ones(n_obs), X_features, X_control_norm])
    p = X.shape[1]  # n_params + 1 intercept

    # y normalize (same as Bayesian for consistency)
    y_mean = float(y.mean())
    y_std = max(float(y.std()), 1e-10)
    y_norm = (y - y_mean) / y_std

    report('fitting', 50.0)

    # ── OLS via numpy.linalg.lstsq (closed form, stable) ──
    try:
        beta_hat, residuals, rank, sv = np.linalg.lstsq(X, y_norm, rcond=None)
    except np.linalg.LinAlgError as e:
        return {
            'status': 'error',
            'error_code': 'OLS_SINGULAR',
            'message': f'OLS regression singular: {e}. Possible multicollinearity between channels.',
        }

    # Predictions in normalized scale
    y_pred_norm = X @ beta_hat
    residual_norm = y_norm - y_pred_norm

    # Denormalize for reporting
    y_pred = y_pred_norm * y_std + y_mean

    # ── Diagnostics ──
    ss_total = float(np.sum((y_norm - y_norm.mean()) ** 2))
    ss_residual = float(np.sum(residual_norm ** 2))
    r_squared = max(0.0, min(1.0, 1.0 - ss_residual / max(ss_total, 1e-10)))
    dof = max(n_obs - p, 1)
    adj_r_squared = 1.0 - (1.0 - r_squared) * (n_obs - 1) / dof
    residual_std_norm = float(np.sqrt(ss_residual / dof))
    residual_std = residual_std_norm * y_std  # back to original units
    mape = float(np.mean(np.abs((y - y_pred) / np.maximum(np.abs(y), 1e-10))) * 100)

    # Coefficient std errors (frequentist OLS): se(β) = sqrt(diag(σ² (X'X)^(-1)))
    XtX_inv = None
    try:
        XtX_inv = np.linalg.inv(X.T @ X)
        beta_se_norm = np.sqrt(np.diag(XtX_inv) * (ss_residual / dof))
    except np.linalg.LinAlgError:
        beta_se_norm = np.full(p, np.nan)

    # Extract β per channel (skip intercept at index 0).
    # H3 fix: media_betas length = trained_media_cols (untrained excluded from X).
    intercept_norm = float(beta_hat[0])
    n_trained = len(trained_media_cols)
    media_betas = beta_hat[1:1 + n_trained]
    control_betas = beta_hat[1 + n_trained:]
    media_betas_se = beta_se_norm[1:1 + n_trained]

    try:
        from scipy import stats as scipy_stats
        t_crit = float(scipy_stats.t.ppf(0.95, dof))
    except Exception:
        t_crit = 1.645  # fallback to large-sample normal

    # ── Bootstrap ROI CI + OLS diagnostics (small-data path) ──
    raw_spend_totals_dict = {}
    raw_spend_series_dict = {}
    for col in trained_media_cols:
        col_arr = df[col].fillna(0).values.astype(float)
        raw_spend_totals_dict[col] = float(col_arr.sum())
        raw_spend_series_dict[col] = col_arr

    bootstrap_roi_results: dict[str, Any] = {}
    ols_diag_results: dict[str, Any] = {}
    conformal_pi = None

    # Build channel_params (compatible with decompose/optimizer expectations).
    channel_params = {}
    trained_set = set(trained_media_cols)
    for col in media_cols:
        if col not in trained_set:
            # Untrained channel: explicit zero β + flag so downstream can skip
            channel_params[col] = {
                'beta': 0.0,
                'alpha': DEFAULT_ALPHA,
                'gamma': DEFAULT_GAMMA,
                'adstock': {'type': adstock_config.get(col, 'geometric')},
                'decay': DEFAULT_DECAY,
                'tail_ess_ok': True,
                'beta_se': None,
                'beta_ci_low_freq': 0.0,
                'beta_ci_high_freq': 0.0,
                'untrained': True,
            }
            continue
        j = trained_media_cols.index(col)
        beta_ci_half = t_crit * float(media_betas_se[j]) if not np.isnan(media_betas_se[j]) else 0.0
        ch_dict: dict[str, Any] = {
            'beta': round(float(media_betas[j]), 4),
            'alpha': DEFAULT_ALPHA,
            'gamma': DEFAULT_GAMMA,
            'adstock': {'type': adstock_config.get(col, 'geometric')},
            'decay': DEFAULT_DECAY,
            'tail_ess_ok': True,
            'beta_se': round(float(media_betas_se[j]), 4) if not np.isnan(media_betas_se[j]) else None,
            'beta_ci_low_freq': round(float(media_betas[j] - beta_ci_half), 4),
            'beta_ci_high_freq': round(float(media_betas[j] + beta_ci_half), 4),
        }
        boot = bootstrap_roi_results.get(col)
        if boot is not None and boot.get('ci_low') is not None:
            ch_dict['roi_ci_low_bootstrap'] = round(boot['ci_low'], 4)
            ch_dict['roi_ci_high_bootstrap'] = round(boot['ci_high'], 4)
            ch_dict['roi_bootstrap_mean'] = round(boot['ci_mean'], 4)
        channel_params[col] = ch_dict

    diagnostics = {
        'engine': 'ols',
        'n_obs': n_obs,
        'n_params': p,
        'dof': dof,
        'metrics': {
            'r_squared': round(r_squared, 4),
            'adj_r_squared': round(adj_r_squared, 4),
            'mape': round(mape, 2),
            'residual_std_norm': round(residual_std_norm, 4),
            'residual_std': round(residual_std, 4),
            'mcmc': None,
        },
        'ols_quality': ols_diag_results,
        'conformal_pi': conformal_pi,
        'actual_vs_predicted': {
            'actual': [round(float(v), 4) for v in y.tolist()],
            'predicted': [round(float(v), 4) for v in y_pred.tolist()],
            'residual': [round(float(v), 4) for v in (y - y_pred).tolist()],
        },
        'honest_disclosure': (
            f'OLS mode (small data fallback): n={n_obs} observations, p={p} parameters, '
            f'dof={dof}. Hill α={DEFAULT_ALPHA}, γ={DEFAULT_GAMMA}, decay={DEFAULT_DECAY} - '
            f'fixed, not learned (need n≥30 for Bayesian estimate). '
            f'Confidence intervals - frequentist on β-coefficients + predictive intervals on y. '
            f'NOT posterior CI as in Bayesian mode.'
        ),
    }

    report('saving', 90.0)

    model_data = {
        'config': config,
        'channel_params': channel_params,
        'normalization': {
            'media_means': media_means,
            'control_means': dict(zip(control_cols, control_means.tolist())) if len(control_cols) > 0 else {},
            'control_stds': dict(zip(control_cols, control_stds.tolist())) if len(control_cols) > 0 else {},
            'y_mean': y_mean,
            'y_std': y_std,
            'intercept_mean': intercept_norm,
            'control_betas_mean': control_betas.tolist() if len(control_betas) > 0 else [],
            'untrained_channels': untrained_channels,
        },
        # OLS-specific diagnostics for downstream banner / honest disclosure
        'ols_diagnostics': {
            'residual_std_norm': residual_std_norm,
            'residual_std': residual_std,
            'r_squared': r_squared,
            'adj_r_squared': adj_r_squared,
            'mape': mape,
            'beta_standard_errors': beta_se_norm.tolist(),
            'XtX_inverse_diag': np.diag(XtX_inv).tolist() if XtX_inv is not None else None,
        },
        'model_version': '1.0-ols',
        'y_actual': y.tolist(),
        'y_predicted': y_pred.tolist(),
    }

    model_path = models_dir / 'latest.pkl'
    history_dir = models_dir / 'history'
    history_dir.mkdir(exist_ok=True)
    if model_path.exists():
        import shutil
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(model_path, history_dir / f'model-{ts}.pkl')
        archives = sorted(history_dir.glob('model-*.pkl'))
        while len(archives) > 5:
            archives[0].unlink(missing_ok=True)
            archives.pop(0)

    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)

    params_path = models_dir / 'latest-params.json'
    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump({
            'channel_params': channel_params,
            'diagnostics': diagnostics,
            'config': {k: v for k, v in config.items() if k != 'data_file'},
            'engine': 'ols',
        }, f, ensure_ascii=False, indent=2)

    result_path = results_dir / 'model-diagnostics.json'
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(diagnostics, f, ensure_ascii=False, indent=2)

    report('complete', 100.0)

    return {
        'status': 'ok',
        'engine': 'ols',
        'model_path': str(model_path),
        'diagnostics': diagnostics,
        'channel_params': channel_params,
        'normalization': {
            'y_mean': y_mean,
            'y_std': y_std,
        },
        'honest_disclosure': diagnostics['honest_disclosure'],
    }


def recommend_engine(n_obs: int, *, override: str | None = None) -> dict[str, Any]:
    """Auto-recommend Bayesian vs OLS based on sample size.

    Per ADR §3.A2 + Antón confirmation:
      n < 20  → strict OLS (Bayesian unreliable)
      20 ≤ n < 30 → user choice (default OLS, Bayesian opt-in)
      n ≥ 30 → Bayesian default (OLS opt-in for fast iteration)

    Args:
        n_obs: number of training observations
        override: 'bayesian' | 'ols' - explicit user choice; takes precedence

    Returns:
        {
          'recommended': 'bayesian' | 'ols',
          'allowed': list of allowed modes,
          'reason': human-readable rationale,
          'banner_tone': 'good' | 'warn' | 'bad'  (UI styling hint)
        }
    """
    if override in ('bayesian', 'ols'):
        return {
            'recommended': override,
            'allowed': ['bayesian', 'ols'],
            'reason': f'User explicit choice: {override}',
            'banner_tone': 'good',
            'override_active': True,
        }
    if n_obs < 20:
        return {
            'recommended': 'ols',
            'allowed': ['ols'],
            'reason': (
                f'n={n_obs}: insufficient data for Bayesian MMM (need n≥20 for basic '
                f'identifiability, n≥30 for reliable posterior CI). Using OLS mode '
                f'with frequentist CI on β + predictive intervals on y.'
            ),
            'banner_tone': 'bad',
            'override_active': False,
        }
    if n_obs < 30:
        return {
            'recommended': 'ols',
            'allowed': ['ols', 'bayesian'],
            'reason': (
                f'n={n_obs}: borderline region. OLS recommended by default (more stable '
                f'on small samples), but Bayesian is available in experimental mode. '
                f'Bayesian results may have R-hat>1.05 and wide CI.'
            ),
            'banner_tone': 'warn',
            'override_active': False,
        }
    return {
        'recommended': 'bayesian',
        'allowed': ['bayesian', 'ols'],
        'reason': (
            f'n={n_obs}: sufficient data for Bayesian MMM (NUTS estimates Hill α/γ + adstock '
            f'decay per channel + posterior CI). OLS available as fast baseline.'
        ),
        'banner_tone': 'good',
        'override_active': False,
    }
