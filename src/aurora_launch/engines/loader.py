"""Pickle persistence helpers for Aurora Launch math engines.

Ported from Aurora Econometrica (sidecar/econometrica/engines/persistence.py).
Adapted for standalone use (no FastAPI, no HTTP server).

Import paths updated:
  from sidecar.econometrica.utils.X → from aurora_launch.utils.X
  from econometrica.utils.X         → from aurora_launch.utils.X

Migration ladder for model_version:
- v1.0       - initial OLS path (rejected by decompose guard, MODEL_OUTDATED)
- v1.0-ols   - Sprint 2 small-data fallback (point estimates, no posterior CI)
- v1.1       - v1.0.13+ Bayesian baseline (z-score → spend/mean Hill normalization)
- v1.1.1     - Phase 1.1 hierarchical adstock decay (logit-normal, sampled per channel)
- v1.2       - v1.0.16 baseline (post-audit fixes, three-way alignment)
- v1.3       - Trust Level 3 (Brand vs Performance Split, channel_categories field)
- v2.0       - v1.2.0 (Awareness KPI + Weibull learnable). Additive optional fields.
- v2.0.0     - Aurora MMM Optimizer v2.0.0 (ADR-019). Additive diagnostics caching.
"""

from __future__ import annotations

import logging
import os
import pickle
import re
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Semantic version comparison helper (avoids stdlib `packaging` dep)
_VERSION_RE = re.compile(r'(\d+)\.(\d+)(?:\.(\d+))?')


def _parse_version(v: str) -> tuple[int, int, int]:
    """Parse 'X.Y' or 'X.Y.Z' (with optional suffix like '1.0-ols') → (X, Y, Z) tuple.

    Returns (0, 0, 0) for unparseable strings (defensive default - treated as
    legacy pre-v1.0).

    Why: string `<` comparison broken - '1.10' < '1.3' lexicographically (audit fix).
    """
    if not isinstance(v, str):
        return (0, 0, 0)
    m = _VERSION_RE.match(v)
    if not m:
        return (0, 0, 0)
    major, minor, patch = m.groups()
    return (int(major), int(minor), int(patch) if patch else 0)


def load_model_with_compat(model_path: Path | str) -> dict[str, Any]:
    """Load pickle with backward-compat fields injected.

    Trust Level 3 contract:
    - `channel_categories` always present (empty dict if pre-v1.3 pickle).
    - `model_version` always present (default '1.0' if field missing - legacy).
    - Old fields preserved verbatim.

    NB: Does not infer categories automatically - leaves `{}` for downstream choice.
    Decompose/optimizer/etc. can call `infer_categories_heuristic()`
    if they need categories, but does NOT persist in pickle (read-only access pattern).

    Raises:
        FileNotFoundError if path does not exist.
        pickle.UnpicklingError on corrupt files.
    """
    p = Path(model_path)
    with open(p, 'rb') as f:
        model_data = pickle.load(f)

    # Defensive defaults (v1.0 legacy may lack these fields entirely)
    model_data.setdefault('model_version', '1.0')
    model_data.setdefault('channel_categories', {})

    # v2.0 additive fields (default to pre-v2.0 behavior)
    model_data.setdefault('kpi_type', 'sales')
    model_data.setdefault('kpi_likelihood', 'normal')
    model_data.setdefault('awareness_aggregation_mode', None)
    model_data.setdefault('channel_adstock_types', {})       # default per-channel = 'geometric'
    model_data.setdefault('weibull_params_per_channel', {})  # learned (peak_week, tail_decay)
    model_data.setdefault('comparison_baseline_posterior', None)  # for ROI shift toggle
    model_data.setdefault('feature_flags_used', [])          # telemetry

    # Phase 2 (Planning Mode) - pre-Phase-2 pickles get None defaults; G2 inference
    # helpers compute lazily when planning mode actually queries them.
    model_data.setdefault('training_granularity', None)
    model_data.setdefault('train_x_norm_quantiles', None)
    model_data.setdefault('seasonality_detected', None)

    # v1.3.0 additive fields (per ADR-017 - schema bump skipped, in-memory inject only).
    _inject_v13_defaults(model_data)

    # v2.0.0 additive diagnostics caching fields (PRE_FLIGHT N13, ADR-019 §10).
    # All default to None/empty for v1.3.x backward compat.
    _inject_v20_defaults(model_data)

    return model_data


def _inject_v13_defaults(model_data: dict[str, Any]) -> None:
    """Inject v1.3.0 additive fields with defaults derived from v1.2 state.

    Per ADR-017 (Bundle schema v1.3 additive). Mutates dict in place.
    """
    kpi_type = model_data.get('kpi_type') or 'sales'

    # kpi_kind from registry (graceful fallback to 'monetary' if KPI not registered).
    if 'kpi_kind' not in model_data:
        try:
            from aurora_launch.engines.kpi_registry import get_kpi_config
            kpi_kind = get_kpi_config(kpi_type).kpi_kind
        except Exception:
            kpi_kind = 'monetary'  # safe fallback
        model_data['kpi_kind'] = kpi_kind

    # per_channel_input: default - all media columns as 'monetary'.
    if 'per_channel_input' not in model_data:
        config = model_data.get('config') or {}
        media_cols_raw = config.get('media_columns')
        media_cols = list(media_cols_raw) if media_cols_raw else []
        legacy_objective = config.get('analysis_objective', 'roi')
        if legacy_objective == 'effectiveness':
            default_metric = 'physical'
        else:
            default_metric = 'monetary'
        model_data['per_channel_input'] = {ch: default_metric for ch in media_cols}

    # derived_mode: lazy compute if absent.
    if 'derived_mode' not in model_data:
        model_data['derived_mode'] = 'roi'  # safe fallback

    model_data.setdefault('value_per_count_unit', None)
    model_data.setdefault('value_per_count_unit_label', '')
    model_data.setdefault('value_per_count_unit_source', None)
    model_data.setdefault('goal_seek_history', [])
    model_data.setdefault('safe_corridor_cache', None)


def _inject_v20_defaults(model_data: dict[str, Any]) -> None:
    """Inject v2.0.0 additive diagnostics fields with None/empty defaults.

    Per ADR-019 §10 + PRE_FLIGHT N13. Mutates dict in-place.
    """
    model_data.setdefault('signed_factor_priors_used', {})
    model_data.setdefault('holiday_dummies_injected', [])
    model_data.setdefault('mcmc_diagnostics', None)
    model_data.setdefault('backtest_results', None)
    model_data.setdefault('ppc_results', None)
    model_data.setdefault('sensitivity_tornado_cache', None)
    model_data.setdefault('analysis_mode', None)


def get_kpi_type(model_data: dict[str, Any]) -> str:
    """Return KPI type from pickle. Default 'sales' for backward compat."""
    return str(model_data.get('kpi_type') or 'sales')


def is_awareness_model(model_data: dict[str, Any]) -> bool:
    """True if pickle trained in awareness mode."""
    return get_kpi_type(model_data) == 'awareness'


def get_adstock_type(model_data: dict[str, Any], channel: str) -> str:
    """Return adstock type for a specific channel.

    Returns:
        'geometric' (default) or 'weibull'.
    """
    types = model_data.get('channel_adstock_types') or {}
    return str(types.get(channel) or 'geometric')


def get_weibull_params(
    model_data: dict[str, Any], channel: str
) -> dict[str, float] | None:
    """Return learned Weibull params for channel, None if geometric.

    Returns:
        {'peak_week_median', 'tail_decay_median', 'lam_median', 'k_median'} or None.
    """
    if get_adstock_type(model_data, channel) != 'weibull':
        return None
    params = model_data.get('weibull_params_per_channel') or {}
    channel_params = params.get(channel)
    if channel_params is None:
        import warnings
        warnings.warn(
            f"Channel '{channel}' marked as Weibull in pickle, but params missing in "
            f"weibull_params_per_channel. Falling back to geometric. "
            f"Possible corrupted pickle or incomplete training.",
            RuntimeWarning,
            stacklevel=2,
        )
    return channel_params


def has_baseline_posterior(model_data: dict[str, Any]) -> bool:
    """True if pickle contains cached single-prior baseline for ROI shift comparison."""
    return model_data.get('comparison_baseline_posterior') is not None


def get_baseline_posterior(model_data: dict[str, Any]) -> dict[str, Any] | None:
    """Return cached baseline posterior summary, or None."""
    return model_data.get('comparison_baseline_posterior')


def get_feature_flags(model_data: dict[str, Any]) -> list[str]:
    """Return telemetry feature flags used during training."""
    flags = model_data.get('feature_flags_used') or []
    return list(flags)


def get_channel_categories(
    model_data: dict[str, Any],
    fallback_heuristic: bool = True,
) -> dict[str, str]:
    """Get channel categories from pickle, optionally with heuristic fallback.

    Args:
        model_data: loaded pickle dict
        fallback_heuristic: if True and categories empty - derive from channel names
                          via auto-suggestion confidence ≥ 0.7

    Returns:
        {channel_name: 'brand'|'performance'|'mixed'}
    """
    categories = dict(model_data.get('channel_categories') or {})
    if categories:
        return categories
    if not fallback_heuristic:
        return {}
    from aurora_launch.utils.channel_categorization import infer_categories_heuristic
    media_cols = model_data.get('media_columns') or model_data.get('config', {}).get('media_columns', [])
    if not media_cols:
        return {}
    return infer_categories_heuristic(list(media_cols))


def is_hierarchical_model(model_data: dict[str, Any]) -> bool:
    """True if pickle trained hierarchically (v1.3+ with non-empty categories).

    Audit fix: semantic version compare - string `<` broken on '1.10' vs '1.3'.
    """
    version = _parse_version(str(model_data.get('model_version') or ''))
    if version < (1, 3):
        return False
    cats = model_data.get('channel_categories') or {}
    if not cats:
        return False
    n_brand = sum(1 for c in cats.values() if c == 'brand')
    n_perf = sum(1 for c in cats.values() if c == 'performance')
    return n_brand >= 2 or n_perf >= 2


def is_v20_compatible(model_data: dict[str, Any]) -> bool:
    """Return True if pickle was saved by v2.0.0+ engine.

    Contract:
    - v2.0.0+ pickle: model_version >= (2, 0, 0) AND analysis_mode is not None.
    - v1.3.x pickle: either condition fails.
    """
    version = _parse_version(str(model_data.get('model_version') or ''))
    if version < (2, 0, 0):
        return False
    return model_data.get('analysis_mode') is not None


def _model_path_for_project(project_dir: str | Path) -> Path:
    """Return canonical latest.pkl path for a project directory."""
    return Path(project_dir) / 'models' / 'latest.pkl'


def save_v20_diagnostics(project_dir: str | Path, diagnostics: dict[str, Any]) -> None:
    """Append v2.0.0 diagnostics into existing latest.pkl atomically.

    Reads the current pickle, merges diagnostics fields, bumps model_version
    to '2.0.0', then atomically replaces the file via temp-rename pattern.

    Args:
        project_dir: project directory containing models/latest.pkl
        diagnostics: dict with any subset of v2.0.0 diagnostics fields.

    Raises:
        FileNotFoundError: if latest.pkl is absent.
        pickle.UnpicklingError: on corrupt pickle.
        OSError: on disk I/O failure.
    """
    _V20_ALLOWED_FIELDS = frozenset({
        'signed_factor_priors_used',
        'holiday_dummies_injected',
        'mcmc_diagnostics',
        'backtest_results',
        'ppc_results',
        'sensitivity_tornado_cache',
        'analysis_mode',
    })

    model_path = _model_path_for_project(project_dir)
    if not model_path.exists():
        raise FileNotFoundError(
            f"latest.pkl not found: {model_path}. "
            f"Train a model before saving diagnostics."
        )

    model_data = load_model_with_compat(model_path)

    applied_fields: list[str] = []
    for key, value in diagnostics.items():
        if key in _V20_ALLOWED_FIELDS:
            model_data[key] = value
            applied_fields.append(key)
        else:
            logger.warning(
                "save_v20_diagnostics: unknown field %r ignored (allowlist)", key
            )

    model_data['model_version'] = '2.0.0'

    models_dir = model_path.parent
    models_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=models_dir, suffix='.pkl.tmp', prefix='latest_'
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, 'wb') as f:
            pickle.dump(model_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_path, model_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    logger.info(
        "save_v20_diagnostics: persisted fields %s to %s (model_version→2.0.0)",
        applied_fields, model_path,
    )


def load_v20_diagnostics(project_dir: str | Path) -> dict[str, Any]:
    """Return cached v2.0.0 diagnostics fields from latest.pkl.

    Safe for v1.3.x pickles - returns a dict with all v2.0.0 diagnostics keys
    present but set to their default (None / empty) values.

    Returns:
        dict with diagnostics keys + '_v20_compatible' boolean flag.

    Raises:
        FileNotFoundError: if latest.pkl is absent.
    """
    model_path = _model_path_for_project(project_dir)
    if not model_path.exists():
        raise FileNotFoundError(f"latest.pkl not found: {model_path}.")

    model_data = load_model_with_compat(model_path)

    return {
        'signed_factor_priors_used': model_data.get('signed_factor_priors_used') or {},
        'holiday_dummies_injected': model_data.get('holiday_dummies_injected') or [],
        'mcmc_diagnostics': model_data.get('mcmc_diagnostics'),
        'backtest_results': model_data.get('backtest_results'),
        'ppc_results': model_data.get('ppc_results'),
        'sensitivity_tornado_cache': model_data.get('sensitivity_tornado_cache'),
        'analysis_mode': model_data.get('analysis_mode'),
        '_v20_compatible': is_v20_compatible(model_data),
    }


def clear_sensitivity_cache(project_dir: str | Path) -> bool:
    """Invalidate cached sensitivity_tornado_cache in latest.pkl.

    Uses same atomic temp-rename pattern as save_v20_diagnostics().

    Returns:
        True if cache was present and cleared.
        False if cache was already None (no-op, not an error).

    Raises:
        FileNotFoundError: if latest.pkl is absent.
    """
    model_path = _model_path_for_project(project_dir)
    if not model_path.exists():
        raise FileNotFoundError(f"latest.pkl not found: {model_path}.")

    model_data = load_model_with_compat(model_path)
    had_cache = model_data.get('sensitivity_tornado_cache') is not None

    if not had_cache:
        logger.debug(
            "clear_sensitivity_cache: cache already None for %s — no-op", project_dir
        )
        return False

    model_data['sensitivity_tornado_cache'] = None

    models_dir = model_path.parent
    fd, tmp_path_str = tempfile.mkstemp(
        dir=models_dir, suffix='.pkl.tmp', prefix='latest_'
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, 'wb') as f:
            pickle.dump(model_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_path, model_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    logger.info("clear_sensitivity_cache: cache cleared for %s", project_dir)
    return True
