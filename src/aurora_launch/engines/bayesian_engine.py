"""
Bayesian MMM training engine using PyMC5.
Marketing Mix Model with Adstock + Hill saturation.

Ported from Aurora Econometrica (sidecar/econometrica/engines/modeler.py).

Adaptations applied:
1. Import paths: sidecar.econometrica.utils.X / utils.X → aurora_launch.utils.X
                 engines.X → aurora_launch.engines.X
2. progress_callback signature changed from fn(dict) to fn(pct: float, message: str).
   Callback is plain Callable — no HTTP SSE, no streaming. Exceptions swallowed.
3. Removed FastAPI-specific imports (none were in modeler.py originally).
4. D-06 dual-granularity note: modeler assumes weekly data in several places
   (e.g. half-life reporting is in "weeks"). Monthly data accepted without changes
   since period labels are generic — caller should note that "week" == "period"
   when training on monthly granularity. No functional rewrite needed.
5. Math kernel 100% identical: priors, NUTS tier logic, Hill formula, adstock scan.

Dual-tier MCMC (Tier-1 NumPyro, Tier-2 PyTensor):
  Tier-1: NumPyro NUTS (JAX JIT + vectorized chains) - 5-15× faster.
  Tier-2: PyTensor NUTS (cores=1) - stable, but 3-5× slower.
  Full fail: honest RuntimeError with MMM_SAMPLER_EXHAUSTED code.
  Metropolis NOT used as Tier-3 fallback - on MMM gives r_hat > 2.0.

JAX is optional (Tier-1 only). Not a hard dependency.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _find_msvc_via_vswhere() -> str | None:
    """Locate MSVC cl.exe directory via official vswhere.exe.

    vswhere is always at %ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer\\vswhere.exe
    regardless of VS version/edition. Returns bin path containing cl.exe, or None.
    Side effect: adds the path to os.environ['PATH'] so subsequent PyTensor subprocess calls find it.
    """
    import subprocess
    import glob

    vswhere = os.path.join(
        os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
        'Microsoft Visual Studio', 'Installer', 'vswhere.exe'
    )
    if not os.path.isfile(vswhere):
        return None

    try:
        result = subprocess.run(
            [vswhere, '-latest', '-products', '*',
             '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
             '-property', 'installationPath'],
            capture_output=True, text=True, timeout=10
        )
        vs_path = result.stdout.strip()
        if not vs_path:
            return None
    except Exception:
        return None

    pattern = os.path.join(vs_path, 'VC', 'Tools', 'MSVC', '*', 'bin', 'Hostx64', 'x64', 'cl.exe')
    matches = glob.glob(pattern)
    if not matches:
        return None

    cl_exe = sorted(matches)[-1]
    bin_dir = os.path.dirname(cl_exe)

    vcvars = os.path.join(vs_path, 'VC', 'Auxiliary', 'Build', 'vcvars64.bat')
    if os.path.isfile(vcvars):
        try:
            proc = subprocess.run(
                f'"{vcvars}" >nul 2>&1 && set',
                shell=True, capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if '=' in line:
                        key, _, val = line.partition('=')
                        if key.upper() in ('PATH', 'INCLUDE', 'LIB', 'LIBPATH', 'WINDOWSSDKDIR',
                                           'WINDOWSSDKVERSION', 'VCINSTALLDIR', 'VCTOOLSINSTALLDIR',
                                           'VSINSTALLDIR'):
                            os.environ[key] = val
                return bin_dir
        except Exception:
            pass

    current_path = os.environ.get('PATH', '')
    if bin_dir not in current_path:
        os.environ['PATH'] = f"{bin_dir};{current_path}"
    return bin_dir


def check_compiler() -> bool:
    """Check if C compiler is available (for NUTS sampler).

    Windows strategy:
    1. Try cl.exe via PATH (activated via vcvars, or manually added)
    2. Try g++ (MinGW)
    3. Fall back to vswhere.exe to locate MSVC Build Tools installation
    """
    import subprocess
    import platform
    try:
        if platform.system() == 'Windows':
            for cmd in [['cl.exe'], ['g++', '--version']]:
                try:
                    subprocess.run(cmd, capture_output=True, timeout=5)
                    return True
                except FileNotFoundError:
                    continue
            return _find_msvc_via_vswhere() is not None
        else:
            result = subprocess.run(['gcc', '--version'], capture_output=True, timeout=5)
            return result.returncode == 0
    except Exception:
        return False


def get_mcmc_params(has_compiler: bool) -> dict:
    """MCMC parameters based on environment (Windows optimization).

    Defaults bumped 2026-04-19 to 4/2000/2000 - on JAX/NUTS seconds,
    but gives reliable R-hat (4 chains) and accurate ROI CI (2000 draws + 2000 tune).
    """
    if has_compiler:
        return {'chains': 4, 'draws': 2000, 'tune': 2000, 'sampler': 'NUTS'}
    # No compiler → Metropolis fallback conserved. Smaller defaults since
    # Metropolis 4×2000×2000 = tens of minutes.
    return {'chains': 2, 'draws': 1000, 'tune': 500, 'sampler': 'Metropolis'}


def train_model(
    config: dict,
    project_dir: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """Train a Bayesian MMM model.

    Args:
        config: {
            'data_file': str,          # Path to clean xlsx/csv
            'kpi_column': str,         # Target variable
            'media_columns': list,     # Media channel columns
            'control_columns': list,   # Control variable columns
            'date_column': str,        # Date column
            'adstock_config': dict,    # {channel: 'geometric'|'weibull'}
            'mcmc_override': dict|None # Override chains/draws/tune
        }
        project_dir: Path to project directory for saving results
        progress_callback: optional fn(pct: float, message: str).
            pct in [0, 100]. Exceptions in callback are swallowed.

    Returns:
        JSON-serializable result with diagnostics
    """
    def report(message: str, pct: float = 0.0) -> None:
        """Phase-level progress - no per-draw callback instability."""
        if progress_callback:
            try:
                progress_callback(pct, message)
            except Exception:
                pass  # never crash training due to callback error

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
    date_col = config.get('date_column', 'date')
    adstock_config = config.get('adstock_config', {})
    merge_rules = config.get('merge_rules', {}) or {}

    # ─── KPI registry activation (v2.0 foundation, D.1) ─────────────────
    kpi_type = config.get('kpi_type', 'sales')
    # AUDIT-1: guard for KPI types beyond 'sales' - awareness requires logit-Normal
    # likelihood (not yet implemented). Fail fast with clear error.
    if kpi_type != 'sales':
        return {
            'status': 'error',
            'error_code': 'KPI_TYPE_NOT_IMPLEMENTED',
            'message': (
                f"kpi_type='{kpi_type}' not yet supported in production. "
                f"Only kpi_type='sales' is available."
            ),
        }

    # Build minimal kpi_config inline to avoid dependency on kpi_registry
    # (which lives in Optimizer but not in Launch). Sales mode frozen values.
    class _KpiConfig:
        gammas_alpha = 3
        gammas_beta = 3
        obs_sigma_prior = 0.3
        brand_beta_sigma = 0.7
        perf_beta_sigma = 0.3
        mixed_beta_sigma = 0.5
        brand_mu_logit_prior = (0.7, 0.3)
        perf_mu_logit_prior = (-1.4, 0.7)
        mixed_mu_logit_prior = (-1.4, 0.7)
        likelihood = 'normal'
        kpi_kind = 'monetary'

    kpi_config = _KpiConfig()

    # ─── JAX backend enforcement (v2.0 foundation, D.2) ─────────────────
    _has_weibull = any(t == 'weibull' for t in adstock_config.values())
    if _has_weibull and os.environ.get('AURORA_NUTS_BACKEND', 'auto').lower() == 'pymc':
        return {
            'status': 'error',
            'error_code': 'WEIBULL_REQUIRES_JAX_BACKEND',
            'message': (
                "AURORA_NUTS_BACKEND=pymc + Weibull adstock = poor performance "
                "(Toeplitz pt.scan on CPU). Switch AURORA_NUTS_BACKEND to 'auto' "
                "or 'numpyro', or set all channels to 'geometric'."
            ),
        }

    # Trust Level 3: channel_categories - brand / performance / mixed.
    raw_categories = config.get('channel_categories', {}) or {}
    from aurora_launch.utils.channel_categorization import (
        validate_categorization_for_hierarchical,
        is_hierarchical_eligible,
        resolve_per_channel_categories,
    )
    channel_categories, categorization_warnings = validate_categorization_for_hierarchical(
        raw_categories, media_cols
    )
    use_hierarchical = is_hierarchical_eligible(channel_categories)
    per_channel_cats = resolve_per_channel_categories(channel_categories, media_cols)
    if categorization_warnings:
        for w in categorization_warnings:
            logger.warning(f'[Trust3 categorization] {w}')

    # Parse dates
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])

    # ── v2.0.0 (ADR-019 §5): РФ holiday auto-injection ──
    holiday_cols_injected = []
    if date_col in df.columns:
        try:
            from aurora_launch.utils.holiday_calendar_ru import generate_holiday_dummies
            holiday_df = generate_holiday_dummies(df[date_col])
            for hcol in holiday_df.columns:
                if hcol not in df.columns:
                    df[hcol] = holiday_df[hcol].values
                    holiday_cols_injected.append(hcol)
                    if hcol not in control_cols:
                        control_cols.append(hcol)
            if holiday_cols_injected:
                logger.info(f'Auto-injected {len(holiday_cols_injected)} РФ holiday dummies')
        except Exception as e:
            logger.warning('Holiday auto-injection skipped: %s', e)

    # ── Validate columns BEFORE any computation ──────────────────────────
    if kpi_col not in df.columns:
        return {
            'status': 'error',
            'error_code': 'MISSING_KPI_COLUMN',
            'message': f'KPI column "{kpi_col}" not found in data file. '
                       f'Available columns: {", ".join(df.columns[:20].tolist())}'
                       + ('...' if len(df.columns) > 20 else ''),
        }
    missing_media = [c for c in media_cols if c not in df.columns]
    if missing_media:
        return {
            'status': 'error',
            'error_code': 'MISSING_MEDIA_COLUMNS',
            'message': (
                f'Media columns missing from file: {", ".join(repr(c) for c in missing_media[:10])}'
                + (f' (and {len(missing_media) - 10} more)' if len(missing_media) > 10 else '')
            ),
            'missing_columns': missing_media,
        }
    missing_control = [c for c in control_cols if c not in df.columns]
    if missing_control:
        return {
            'status': 'error',
            'error_code': 'MISSING_CONTROL_COLUMNS',
            'message': (
                f'Control columns missing from file: {", ".join(repr(c) for c in missing_control[:10])}'
                + (f' (and {len(missing_control) - 10} more)' if len(missing_control) > 10 else '')
            ),
            'missing_columns': missing_control,
        }

    y = df[kpi_col].values.astype(float)
    n_obs = len(y)
    n_params = len(media_cols) + len(control_cols) + 1  # +1 for intercept

    # Apply adstock transformations
    from aurora_launch.utils.adstock import apply_adstock

    X_media = pd.DataFrame()
    adstock_params_used = {}
    raw_media = pd.DataFrame()
    for col in media_cols:
        a_type = adstock_config.get(col, 'geometric')
        raw_arr = df[col].fillna(0).values.astype(float)
        raw_media[col] = raw_arr
        X_media[col] = apply_adstock(raw_arr, a_type)  # default decay for mean estimate
        adstock_params_used[col] = {'type': a_type}

    X_control = df[control_cols].fillna(0).astype(float) if control_cols else pd.DataFrame()

    # Normalize media - Robyn-style spend/mean (P0-1/2/9 fix, math-fix-v1.0.13).
    raw_means = X_media.mean()
    untrained_channels = [c for c in media_cols if float(raw_means.get(c, 0)) == 0]
    media_means = raw_means.replace(0, 1)  # avoid div/0; flagged separately
    X_media_norm = X_media / media_means
    if untrained_channels:
        logger.warning(
            f"Untrained channels (zero variance in training data): {untrained_channels}."
        )

    # Normalize controls
    untrained_controls = []
    if len(control_cols) > 0:
        control_means = X_control.mean()
        control_stds_raw = X_control.std()
        for col in control_cols:
            if control_stds_raw[col] < 1e-10:
                untrained_controls.append(col)
                logger.warning('Control column %s has zero variance', col)
        control_stds = control_stds_raw.replace(0, 1)
        X_control_norm = (X_control - control_means) / control_stds
    else:
        control_means = pd.Series(dtype=float)
        control_stds = pd.Series(dtype=float)
        X_control_norm = pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────
    # v2.0.0 (ADR-019 §4): Signed factor categorization
    # ─────────────────────────────────────────────────────────────────────
    control_prior_mus: list[float] = []
    control_kinds: list[str] = []

    _kpi_type = config.get('kpi_type', 'sales')
    _is_otc_or_count = _kpi_type in ('sales_packs', 'leads', 'registrations',
                                      'subscriptions', 'loyalty_cards',
                                      'app_installs', 'count_custom', 'profit')
    _competitor_mu_override = config.get('competitor_prior_mu')
    if _competitor_mu_override is not None:
        _competitor_mu = float(_competitor_mu_override)
    elif _is_otc_or_count:
        _competitor_mu = 0.0
    else:
        _competitor_mu = -0.3

    if len(control_cols) > 0:
        try:
            for col in control_cols:
                # Simple heuristic if column_detection not available
                col_upper = col.upper()
                if any(h in col_upper for h in ('COMPETITOR', 'КОНКУР', 'COMPET')):
                    kind = 'signed_competitor'
                elif any(h in col_upper for h in ('PRICE', 'ЦЕНА', 'COST')):
                    kind = 'signed_price'
                elif any(h in col_upper for h in ('HOLIDAY', 'ПРАЗДН', 'HOLIDAY_')):
                    kind = 'holiday'
                elif any(h in col_upper for h in ('WEATHER', 'ПОГОДА', 'TEMP')):
                    kind = 'signed_weather'
                elif any(h in col_upper for h in ('MACRO', 'GDP', 'ВВП', 'ИНФЛ')):
                    kind = 'signed_macro'
                else:
                    kind = 'control'
                control_kinds.append(kind)
                if kind == 'signed_competitor':
                    control_prior_mus.append(_competitor_mu)
                elif kind in ('signed_price', 'signed_weather', 'signed_macro', 'holiday'):
                    control_prior_mus.append(0.0)
                elif kind == 'control':
                    control_prior_mus.append(0.2)
                else:
                    control_prior_mus.append(0.0)
        except Exception as e:
            logger.warning('Signed factor classification fallback: %s — using uniform mu=0', e)
            control_prior_mus = [0.0] * len(control_cols)
            control_kinds = ['unknown'] * len(control_cols)

    y_mean, y_std = y.mean(), max(y.std(), 1e-10)
    y_norm = (y - y_mean) / y_std

    # MCMC parameters
    has_compiler = check_compiler()
    mcmc = config.get('mcmc_override') or get_mcmc_params(has_compiler)
    chains = mcmc.get('chains', 4)
    draws = mcmc.get('draws', 2000)
    tune = mcmc.get('tune', 2000)

    report('compiling', 20.0)

    logger.info(f"Training MMM: {n_obs} obs, {len(media_cols)} media, {len(control_cols)} control, "
                f"MCMC: {chains} chains × {draws} draws (compiler={'yes' if has_compiler else 'no'})")

    try:
        import pymc as pm

        with pm.Model() as mmm:
            # Priors - tightened 2026-04-19 to fix NUTS funnel / divergences on small data.
            intercept = pm.Normal('intercept', mu=0, sigma=0.5)

            use_horseshoe = bool(config.get('use_horseshoe', False))
            if use_horseshoe:
                horseshoe_tau = pm.HalfCauchy('horseshoe_tau', beta=0.1)
                horseshoe_lambda = pm.HalfCauchy('horseshoe_lambda', beta=1.0, shape=len(media_cols))
                media_betas = pm.HalfNormal(
                    'media_betas',
                    sigma=horseshoe_tau * horseshoe_lambda,
                    shape=len(media_cols),
                )
            elif use_hierarchical:
                # Trust Level 3: hierarchical brand vs performance priors.
                # Non-centered z reparameterization avoids funnel.
                import pytensor.tensor as pt
                brand_sigma = pm.HalfNormal('brand_sigma', sigma=kpi_config.brand_beta_sigma)
                perf_sigma = pm.HalfNormal('perf_sigma', sigma=kpi_config.perf_beta_sigma)
                mixed_sigma = pm.HalfNormal('mixed_sigma', sigma=kpi_config.mixed_beta_sigma)
                _sigma_lookup = {'brand': brand_sigma, 'performance': perf_sigma, 'mixed': mixed_sigma}
                sigma_vec = pt.stack([_sigma_lookup[cat] for cat in per_channel_cats])
                media_betas_z = pm.HalfNormal('media_betas_z', sigma=1.0, shape=len(media_cols))
                media_betas = pm.Deterministic('media_betas', sigma_vec * media_betas_z)
            else:
                media_betas = pm.HalfNormal('media_betas', sigma=0.3, shape=len(media_cols))

            # Control coefficients
            # v2.0.0 (ADR-019 §4): per-column prior mean based on factor type
            if len(control_cols) > 0:
                import numpy as _np
                _control_mu_array = _np.array(control_prior_mus, dtype=float)
                control_betas = pm.Normal(
                    'control_betas',
                    mu=_control_mu_array,
                    sigma=0.3,
                    shape=len(control_cols),
                )
                control_effect = pm.math.dot(X_control_norm.values.astype(float), control_betas)
            else:
                control_effect = 0

            # Hill saturation - tighter priors for stable geometry
            alphas = pm.Gamma('alphas', alpha=5, beta=3, shape=len(media_cols))
            gammas = pm.Beta('gammas', alpha=kpi_config.gammas_alpha, beta=kpi_config.gammas_beta, shape=len(media_cols))

            # ─────────────────────────────────────────────────────────────────
            # Phase 1.1 - hierarchical adstock decay (logit-normal parameterization)
            # ─────────────────────────────────────────────────────────────────
            import pytensor.tensor as pt
            from pytensor.scan import scan as pt_scan

            adstock_sigma_logit = pm.HalfNormal('adstock_sigma_logit', sigma=1.0)
            adstock_z = pm.Normal('adstock_z', mu=0.0, sigma=1.0, shape=len(media_cols))
            if use_hierarchical:
                _b_mu, _b_sg = kpi_config.brand_mu_logit_prior
                _p_mu, _p_sg = kpi_config.perf_mu_logit_prior
                _m_mu, _m_sg = kpi_config.mixed_mu_logit_prior
                brand_mu_logit = pm.Normal('brand_mu_logit', mu=_b_mu, sigma=_b_sg)
                perf_mu_logit = pm.Normal('perf_mu_logit', mu=_p_mu, sigma=_p_sg)
                mixed_mu_logit = pm.Normal('mixed_mu_logit', mu=_m_mu, sigma=_m_sg)
                _mu_lookup = {'brand': brand_mu_logit, 'performance': perf_mu_logit, 'mixed': mixed_mu_logit}
                mu_vec = pt.stack([_mu_lookup[cat] for cat in per_channel_cats])
                adstock_decay = pm.Deterministic(
                    'adstock_decay',
                    pm.math.sigmoid(mu_vec + adstock_sigma_logit * adstock_z),
                )
            else:
                _sp_mu, _sp_sg = kpi_config.perf_mu_logit_prior
                adstock_mu_logit = pm.Normal('adstock_mu_logit', mu=_sp_mu, sigma=_sp_sg)
                adstock_decay = pm.Deterministic(
                    'adstock_decay',
                    pm.math.sigmoid(adstock_mu_logit + adstock_sigma_logit * adstock_z),
                )

            # Saturated media effect - Phase 1.1 per-channel scan-based adstock.
            adstock_means_per_channel = []
            media_effect = 0
            for i, col in enumerate(media_cols):
                a_type = adstock_config.get(col, 'geometric')
                if a_type == 'geometric':
                    raw_x = raw_media[col].values
                    adstock_init = pt.as_tensor_variable(raw_x[0])
                    adstock_seq, _ = pt_scan(
                        fn=lambda x_t, prev, d: x_t + d * prev,
                        sequences=[pt.as_tensor_variable(raw_x[1:])],
                        outputs_info=[adstock_init],
                        non_sequences=[adstock_decay[i]],
                    )
                    adstock_full = pt.concatenate([[adstock_init], adstock_seq])
                else:
                    adstock_full = pt.as_tensor_variable(X_media[col].values)
                # C1 fix: normalize by IN-MODEL mean per draw (correct math)
                in_model_mean = adstock_full.mean()
                in_model_mean_safe = pt.maximum(in_model_mean, 1e-10)
                adstock_means_per_channel.append(
                    pm.Deterministic(f'adstock_mean_{i}', in_model_mean_safe)
                )
                x_norm = adstock_full / in_model_mean_safe
                x_safe = pm.math.maximum(x_norm, 0)
                saturated = x_safe ** alphas[i] / (x_safe ** alphas[i] + gammas[i] ** alphas[i] + 1e-10)
                media_effect = media_effect + media_betas[i] * saturated

            # Likelihood
            mu = intercept + media_effect + control_effect
            sigma = pm.HalfNormal('sigma', sigma=kpi_config.obs_sigma_prior)
            pm.Normal('obs', mu=mu, sigma=sigma, observed=y_norm)

            report('sampling', 25.0)

            # ───────────────────────────────────────────────────────────────
            # Tier-based MCMC sampling with fallback (v1.0.9)
            # ───────────────────────────────────────────────────────────────
            _backend = os.environ.get('AURORA_NUTS_BACKEND', 'auto').lower()
            _use_numpyro = False
            _jax_ref = None
            if _backend in ('auto', 'numpyro'):
                try:
                    import numpyro  # noqa: F401
                    import jax
                    _jax_ref = jax
                    _use_numpyro = True
                    logger.info(
                        f'MCMC backend: NumPyro NUTS (JAX) - '
                        f'numpyro={numpyro.__version__}, jax={jax.__version__}'
                    )
                except ImportError:
                    if _backend == 'numpyro':
                        raise RuntimeError(
                            'AURORA_NUTS_BACKEND=numpyro but NumPyro/JAX not installed'
                        )
                    logger.warning('NumPyro/JAX not available - using PyTensor NUTS')

            trace = None
            _sampling_errors: list[tuple[str, str]] = []

            def _is_partial_bug(exc: BaseException) -> bool:
                msg = str(exc)
                return 'functools.partial' in msg or "'__name__'" in msg

            # ── Tier 1: NumPyro NUTS ───────────────────────────────────
            if _use_numpyro and _backend != 'pymc':
                _n_devices = len(_jax_ref.devices()) if _jax_ref is not None else 1
                _chain_method_env = os.environ.get('AURORA_MCMC_CHAIN_METHOD', '').lower()
                if _chain_method_env in ('parallel', 'vectorized', 'sequential'):
                    _chain_method = _chain_method_env
                else:
                    _chain_method = 'parallel' if _n_devices > 1 else 'vectorized'
                logger.info(
                    f'NumPyro chain_method={_chain_method} '
                    f'(jax_devices={_n_devices}, chains={chains})'
                )
                try:
                    logger.info(
                        f'Sampling: Tier-1 NumPyro NUTS '
                        f'(chains={chains}, draws={draws}, tune={tune}, method={_chain_method})'
                    )
                    trace = pm.sample(
                        draws=draws,
                        tune=tune,
                        chains=chains,
                        return_inferencedata=True,
                        progressbar=True,
                        nuts_sampler='numpyro',
                        chain_method=_chain_method,
                        target_accept=0.95,
                    )
                    logger.info('Tier-1 NumPyro NUTS: SUCCESS')
                except AttributeError as e:
                    if _is_partial_bug(e):
                        logger.warning(
                            f'Tier-1 NumPyro NUTS: functools.partial bug '
                            f'({str(e)[:150]}) - falling back to Tier-2 PyTensor NUTS'
                        )
                        _sampling_errors.append(('numpyro', f'partial bug: {str(e)[:200]}'))
                        trace = None
                    else:
                        raise
                except Exception as e:
                    _sampling_errors.append(
                        ('numpyro', f'{type(e).__name__}: {str(e)[:200]}')
                    )
                    logger.error(
                        f'Tier-1 NumPyro NUTS failed on non-partial error: '
                        f'{type(e).__name__}: {e}'
                    )
                    raise

            # ── Tier 2: PyTensor NUTS ──────────────────────────────────
            if trace is None:
                logger.info(
                    f'Sampling: Tier-2 PyTensor NUTS '
                    f'(chains={chains}, draws={draws}, tune={tune}, cores=1)'
                )
                try:
                    def _draw_cb(trace_slice, draw):
                        pass
                    try:
                        trace = pm.sample(
                            draws=draws,
                            tune=tune,
                            chains=chains,
                            cores=1,
                            return_inferencedata=True,
                            progressbar=True,
                            callback=_draw_cb,
                            target_accept=0.95,
                        )
                    except TypeError:
                        trace = pm.sample(
                            draws=draws,
                            tune=tune,
                            chains=chains,
                            cores=1,
                            return_inferencedata=True,
                            progressbar=True,
                            target_accept=0.95,
                        )
                    logger.info('Tier-2 PyTensor NUTS: SUCCESS')
                except AttributeError as e:
                    if _is_partial_bug(e):
                        _sampling_errors.append(
                            ('pytensor', f'partial bug: {str(e)[:200]}')
                        )
                        logger.error(
                            'Tier-2 PyTensor NUTS also failed on functools.partial. '
                            'Model structurally incompatible with current PyMC 5 build.'
                        )
                        trace = None
                    else:
                        raise
                except Exception as e:
                    _sampling_errors.append(
                        ('pytensor', f'{type(e).__name__}: {str(e)[:200]}')
                    )
                    raise

            # ── Full fail: honest error (NO Metropolis - gives r_hat > 2) ──
            if trace is None:
                _err_summary = '\n'.join(
                    f'  - {tier}: {msg}' for tier, msg in _sampling_errors
                )
                raise RuntimeError(
                    'MMM_SAMPLER_EXHAUSTED: could not train model with any '
                    'MCMC backend (NumPyro, PyTensor).\n'
                    f'Attempts:\n{_err_summary}\n\n'
                    'This is a structural incompatibility between PyMC 5 and the '
                    'model configuration (Adstock/Hill custom Deterministic).'
                )

        report('diagnostics', 90.0)

        # Diagnostics
        r_hat_values = []
        per_param_rhat = {}
        hierarchical_rhat_warning: str | None = None
        hierarchical_priors_summary: dict[str, float] = {}
        try:
            import arviz as az
            summary = az.summary(trace)
            r_hat_values = summary['r_hat'].values.tolist()
            key_params = {'intercept', 'sigma'} | {f'media_betas[{i}]' for i in range(len(media_cols))}
            if use_hierarchical:
                key_params |= {
                    'brand_sigma', 'perf_sigma', 'mixed_sigma',
                    'brand_mu_logit', 'perf_mu_logit', 'mixed_mu_logit',
                }
            for param in summary.index:
                if param in key_params:
                    per_param_rhat[param] = round(float(summary.loc[param, 'r_hat']), 4)
            if use_hierarchical:
                hyper_names = ['brand_sigma', 'perf_sigma', 'brand_mu_logit', 'perf_mu_logit']
                hyper_rhats = [per_param_rhat[n] for n in hyper_names if n in per_param_rhat]
                if hyper_rhats and max(hyper_rhats) > 1.05:
                    over_threshold = {n: per_param_rhat[n] for n in hyper_names if per_param_rhat.get(n, 0) > 1.05}
                    hierarchical_rhat_warning = (
                        f'Hierarchical hyperparameters did not converge: {over_threshold}. '
                        f'Consider increasing tune/draws or revert to single-prior path.'
                    )
                    logger.warning(f'[Trust3 R-hat gate] {hierarchical_rhat_warning}')
        except Exception:
            pass

        r_hat_max = max(r_hat_values) if r_hat_values else 1.0
        divergences = int(trace.sample_stats['diverging'].sum()) if hasattr(trace, 'sample_stats') else 0

        # Posterior predictions - reconstructed from posterior means directly.
        y_pred_norm = None
        try:
            import numpy as _np
            intercept_mean = float(trace.posterior['intercept'].mean(dim=['chain', 'draw']).values)
            media_betas_mean = trace.posterior['media_betas'].mean(dim=['chain', 'draw']).values
            alphas_mean = trace.posterior['alphas'].mean(dim=['chain', 'draw']).values
            gammas_mean = trace.posterior['gammas'].mean(dim=['chain', 'draw']).values

            media_effect_pred = _np.zeros(n_obs)
            for i, col in enumerate(media_cols):
                x_ch = X_media_norm[col].values
                alpha_i = float(alphas_mean[i])
                gamma_i = float(gammas_mean[i])
                beta_i = float(media_betas_mean[i])
                x_safe = _np.maximum(x_ch, 0)
                saturated = x_safe ** alpha_i / (x_safe ** alpha_i + gamma_i ** alpha_i + 1e-10)
                media_effect_pred += beta_i * saturated

            control_effect_pred = _np.zeros(n_obs)
            if len(control_cols) > 0:
                control_betas_mean_arr = trace.posterior['control_betas'].mean(dim=['chain', 'draw']).values
                control_effect_pred = X_control_norm.values.astype(float) @ _np.asarray(control_betas_mean_arr)

            y_pred_norm = intercept_mean + media_effect_pred + control_effect_pred
            logger.info(f"y_pred reconstructed from posterior means ({n_obs} obs)")
        except Exception as e:
            logger.exception(f"y_pred reconstruction failed: {e}")
            import numpy as _np
            y_pred_norm = _np.zeros(n_obs)

        y_pred = y_pred_norm * y_std + y_mean

        # Dates for actual_vs_predicted
        dates_list = None
        if date_col in df.columns:
            try:
                dates_list = df[date_col].dt.strftime('%Y-%m-%d').tolist()
            except Exception:
                dates_list = None

        # Metrics (simple inline computation matching Optimizer behavior)
        r_squared = float(1.0 - np.sum((y - y_pred) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-10))
        r_squared = max(0.0, min(1.0, r_squared))
        mape = float(np.mean(np.abs((y - y_pred) / np.maximum(np.abs(y), 1e-10))) * 100)
        rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))

        diagnostics: dict[str, Any] = {
            'status': 'ok',
            'n_obs': n_obs,
            'n_params': n_params,
            'metrics': {
                'r_squared': round(r_squared, 4),
                'mape': round(mape, 2),
                'rmse': round(rmse, 4),
                'r_hat_max': round(r_hat_max, 4),
                'divergences': divergences,
                'mcmc': {
                    'chains': int(chains),
                    'draws': int(draws),
                    'tune': int(tune),
                    'target_accept': 0.95,
                },
            },
            'per_param_rhat': per_param_rhat,
            'hierarchical': {'enabled': bool(use_hierarchical)},
            'actual_vs_predicted': {
                'actual': [round(float(v), 4) for v in y.tolist()],
                'predicted': [round(float(v), 4) for v in y_pred.tolist()],
                'dates': dates_list,
            },
        }
        if use_hierarchical:
            diagnostics['hierarchical'] = {
                'enabled': True,
                'channel_categories': dict(channel_categories),
                'categorization_warnings': list(categorization_warnings),
                'rhat_warning': hierarchical_rhat_warning,
                'priors_summary': hierarchical_priors_summary,
            }

        # Extract posterior means for channel contributions
        media_beta_means = trace.posterior['media_betas'].mean(dim=['chain', 'draw']).values.tolist()
        alpha_means = trace.posterior['alphas'].mean(dim=['chain', 'draw']).values.tolist()
        gamma_means = trace.posterior['gammas'].mean(dim=['chain', 'draw']).values.tolist()

        # Phase 1.9: extract FULL posterior samples for CI propagation.
        media_betas_samples = np.asarray(
            trace.posterior['media_betas'].stack(sample=('chain', 'draw')).values, dtype=np.float32
        )
        alphas_samples = np.asarray(
            trace.posterior['alphas'].stack(sample=('chain', 'draw')).values, dtype=np.float32
        )
        gammas_samples = np.asarray(
            trace.posterior['gammas'].stack(sample=('chain', 'draw')).values, dtype=np.float32
        )

        # Phase 1.1: hierarchical adstock decay samples.
        try:
            adstock_decay_samples = np.asarray(
                trace.posterior['adstock_decay'].stack(sample=('chain', 'draw')).values, dtype=np.float32
            )
            adstock_decay_means = trace.posterior['adstock_decay'].mean(dim=['chain', 'draw']).values.tolist()
            adstock_sigma_logit_mean = float(trace.posterior['adstock_sigma_logit'].mean().values)
            if use_hierarchical:
                for group in ('brand', 'performance', 'mixed'):
                    var_name = f'{group if group != "performance" else "perf"}_mu_logit'
                    if var_name in trace.posterior:
                        hierarchical_priors_summary[f'{group}_mu_logit_mean'] = float(
                            trace.posterior[var_name].mean().values
                        )
                    sigma_name = f'{group if group != "performance" else "perf"}_sigma'
                    if sigma_name in trace.posterior:
                        hierarchical_priors_summary[f'{group}_sigma_mean'] = float(
                            trace.posterior[sigma_name].mean().values
                        )
                adstock_mu_logit_mean = float(np.mean([
                    hierarchical_priors_summary.get(f'{g}_mu_logit_mean', -1.4)
                    for g in ('brand', 'performance', 'mixed')
                    if f'{g}_mu_logit_mean' in hierarchical_priors_summary
                ]) if hierarchical_priors_summary else -1.4)
            else:
                adstock_mu_logit_mean = float(trace.posterior['adstock_mu_logit'].mean().values)
        except KeyError:
            logger.warning("adstock_decay not in trace - falling back to defaults (v1.1.5 compat)")
            adstock_decay_samples = np.full((len(media_cols), media_betas_samples.shape[1]), 0.5, dtype=np.float32)
            adstock_decay_means = [0.5] * len(media_cols)
            adstock_mu_logit_mean = -1.4
            adstock_sigma_logit_mean = 0.5

        # C1 fix: extract in-model adstock_mean per channel posterior.
        adstock_means_posterior = {}
        for i, col in enumerate(media_cols):
            try:
                am_mean = float(trace.posterior[f'adstock_mean_{i}'].mean(dim=['chain', 'draw']).values)
                adstock_means_posterior[col] = am_mean
            except (KeyError, ValueError):
                adstock_means_posterior[col] = float(media_means.get(col, 1.0))

        # Tail-ESS check per channel (Vehtari rule: tail_ess ≥ 100·n_chains).
        try:
            import arviz as az
            tail_ess_threshold = 100 * int(chains)
            param_var_names = ['media_betas', 'alphas', 'gammas']
            try:
                _ = trace.posterior['adstock_decay']
                param_var_names.append('adstock_decay')
            except (KeyError, AttributeError):
                pass
            ess_per_param: dict[str, np.ndarray] = {}
            for vname in param_var_names:
                try:
                    ess_per_param[vname] = az.ess(trace, var_names=[vname], method='tail')[vname].values
                except Exception as _vess_err:
                    logger.warning(f"Tail-ESS failed for {vname}: {_vess_err}. Skipping.")
            tail_ess_ok_per_channel = []
            for i in range(len(media_cols)):
                ok = True
                for vname, ess_arr in ess_per_param.items():
                    try:
                        if i < len(ess_arr) and float(ess_arr[i]) < tail_ess_threshold:
                            ok = False
                            break
                    except (IndexError, ValueError, TypeError):
                        pass
                tail_ess_ok_per_channel.append(bool(ok))
        except Exception as _ess_err:
            logger.warning(f"Tail-ESS computation failed: {_ess_err}. Treating as OK (defensive).")
            tail_ess_ok_per_channel = [True] * len(media_cols)

        channel_params = {}
        for i, col in enumerate(media_cols):
            channel_params[col] = {
                'beta': round(media_beta_means[i], 4),
                'alpha': round(alpha_means[i], 4),
                'gamma': round(gamma_means[i], 4),
                'adstock': adstock_params_used[col],
                'tail_ess_ok': tail_ess_ok_per_channel[i],
                'decay': round(float(adstock_decay_means[i]), 4),
                'adstock_mean_posterior': round(float(adstock_means_posterior.get(col, 1.0)), 4),
            }

        report('saving', 95.0)

        # Extract intercept + control betas posterior means for decompose baseline.
        intercept_mean_posterior = float(trace.posterior['intercept'].mean(dim=['chain', 'draw']).values)
        control_betas_mean_posterior = []
        if len(control_cols) > 0:
            control_betas_mean_posterior = trace.posterior['control_betas'].mean(dim=['chain', 'draw']).values.tolist()

        # Phase 1.9: full posterior samples for CI propagation.
        intercept_samples = np.asarray(
            trace.posterior['intercept'].stack(sample=('chain', 'draw')).values, dtype=np.float32
        )
        if len(control_cols) > 0:
            control_betas_samples = np.asarray(
                trace.posterior['control_betas'].stack(sample=('chain', 'draw')).values, dtype=np.float32
            )
        else:
            control_betas_samples = np.zeros((0, intercept_samples.shape[0]), dtype=np.float32)

        model_data = {
            'config': config,
            'channel_params': channel_params,
            'normalization': {
                'media_means': media_means.to_dict(),
                'control_means': control_means.to_dict() if len(control_cols) > 0 else {},
                'control_stds': control_stds.to_dict() if len(control_cols) > 0 else {},
                'y_mean': float(y_mean),
                'y_std': float(y_std),
                'intercept_mean': intercept_mean_posterior,
                'control_betas_mean': control_betas_mean_posterior,
                'untrained_channels': untrained_channels,
                'control_kinds': control_kinds,
                'holiday_cols_injected': holiday_cols_injected,
                'control_prior_mus': control_prior_mus,
                'untrained_controls': untrained_controls,
            },
            'posterior_samples': {
                'media_betas': media_betas_samples,
                'alphas': alphas_samples,
                'gammas': gammas_samples,
                'intercept': intercept_samples,
                'control_betas': control_betas_samples,
                'adstock_decay': adstock_decay_samples,
                'adstock_mu_logit_mean': adstock_mu_logit_mean,
                'adstock_sigma_logit_mean': adstock_sigma_logit_mean,
                'media_columns': list(media_cols),
                'control_columns': list(control_cols),
                'n_chains': int(chains),
                'n_draws': int(draws),
            },
            'model_version': '1.3' if use_hierarchical else '1.2',
            'channel_categories': dict(channel_categories),
            'categorization_warnings': list(categorization_warnings),
            'use_hierarchical': bool(use_hierarchical),
            'hierarchical_priors': hierarchical_priors_summary,
            'y_actual': y.tolist(),
            'y_predicted': y_pred.tolist(),
            'causal_artifact_path': None,
            'kpi_type': kpi_type,
            'kpi_likelihood': kpi_config.likelihood,
            'channel_adstock_types': dict(adstock_config),
        }

        model_path = models_dir / 'latest.pkl'

        # Model versioning: archive previous model before overwriting
        history_dir = models_dir / 'history'
        history_dir.mkdir(exist_ok=True)
        if model_path.exists():
            import shutil
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            shutil.copy2(model_path, history_dir / f'model-{ts}.pkl')
            prev_params = models_dir / 'latest-params.json'
            if prev_params.exists():
                shutil.copy2(prev_params, history_dir / f'params-{ts}.json')
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
                'mcmc': mcmc,
                'has_compiler': has_compiler,
            }, f, ensure_ascii=False, indent=2)

        result_path = results_dir / 'model-diagnostics.json'
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(diagnostics, f, ensure_ascii=False, indent=2)

        report('complete', 100.0)

        return {
            'status': 'ok',
            'model_path': str(model_path),
            'diagnostics': diagnostics,
            'channel_params': channel_params,
            'normalization': {
                'y_mean': float(y_mean),
                'y_std': float(y_std),
            },
            'mcmc_info': {
                **mcmc,
                'has_compiler': has_compiler,
            },
        }

    except ImportError as e:
        return {
            'status': 'error',
            'message': f'Package not installed: {e}. Run: pip install pymc arviz pytensor',
            'error_code': 'IMPORT_ERROR',
        }
    except RuntimeError as e:
        msg = str(e)
        if 'MMM_SAMPLER_EXHAUSTED' in msg:
            logger.error(f"MMM sampler exhausted: {msg}")
            return {
                'status': 'error',
                'message': msg,
                'error_code': 'MMM_SAMPLER_EXHAUSTED',
            }
        logger.exception("Model training failed (RuntimeError)")
        return {
            'status': 'error',
            'message': f'Model training error: {msg[:300]}',
            'error_code': 'RUNTIME_ERROR',
        }
    except AttributeError as e:
        msg = str(e)
        if 'functools.partial' in msg or "'__name__'" in msg:
            logger.exception("functools.partial bug outside sampling block")
            return {
                'status': 'error',
                'message': f'Model serialization error: {msg[:200]}. Code: SERIALIZATION_ERROR.',
                'error_code': 'SERIALIZATION_ERROR',
            }
        logger.exception("Model training failed (AttributeError)")
        return {
            'status': 'error',
            'message': f'Model training error: {msg[:300]}',
            'error_code': 'ATTRIBUTE_ERROR',
        }
    except Exception as e:
        logger.exception("Model training failed (unexpected)")
        return {
            'status': 'error',
            'message': f'Model training error: {str(e)[:300]}',
            'error_code': 'UNKNOWN_ERROR',
        }
