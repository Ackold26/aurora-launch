"""Sample bundle factory для pilot demos (Phase Σ.0.4).

Provides 3 pre-trained pilot scenarios from real Эконометрика test datasets:
  A) Кагоцел proxy → Венарус recipient (cross-category transfer)
  B) Афала proxy → Афалаза recipient (same-manufacturer relaunch)
  C) Multi-proxy: Афала + Импаза → Афалаза (premium multi-proxy demo)

XLSX adapter normalises Эконометрика wide-format к unified DataFrame:
  Date, channel_<id>_spend, channel_<id>_impressions, ..., sales_brand, sales_competitors

Sample bundles ship с pre-computed synthetic-but-realistic posterior_samples
для each proxy brand. Real PyMC training of pilot data is offline-only
(slow, ~3-5 minutes per scenario) — synthetic posterior derived from data
statistics (mean β, std β by historical correlation) для UX demo speed.

Phase Σ.0.4 deliverable: bundles loadable by orchestrator, demo "Open Sample"
button в Wizard works <5s cold start (per Pf-01 budget).
"""

from aurora_launch.sample_bundles.econometrica_xlsx_adapter import (
    EconometricaDataset,
    EconometricaXLSXError,
    load_econometrica_xlsx,
)
from aurora_launch.sample_bundles.synthetic_posterior import (
    SyntheticPosteriorError,
    derive_synthetic_posterior,
)

__all__ = [
    "EconometricaDataset",
    "EconometricaXLSXError",
    "SyntheticPosteriorError",
    "derive_synthetic_posterior",
    "load_econometrica_xlsx",
]
