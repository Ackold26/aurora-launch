"""WizardSession schema — single source of truth для wizard state.

Phase 1.C.1 BTA-2: до этой версии wizard +page.svelte имел ~12 разбросанных
state variables (importedFile, mappingDone, selectedProxy, anchorsData, etc).
Customer на step 5 нажимал Back → state мог потеряться. App crash перед
save → весь wizard прогресс терялся.

Решение: единая Pydantic schema WizardSession — autosaved в ProjectDB
`_kv_store` (v003) через ключ `wizard.session.draft`. Recovery dialog при
reload sidecar'a: «Восстановить незаконченный сеанс?» (UX-3).

Schema живёт здесь как Pydantic — auto-exported в TypeScript через
gen:types → frontend wizardSession.svelte.ts получает типизированный
$state runes object.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_FROZEN = ConfigDict(frozen=False, extra="forbid", validate_assignment=True)
# frozen=False — wizard state мутабелен (customer добавляет данные по шагам).
# validate_assignment=True — каждое присваивание поля проверяется по схеме.


WizardStep = Literal["import", "mapping", "proxy", "similarity", "anchors", "forecast", "cert"]


class ColumnMapping(BaseModel):
    """Сопоставление колонки XLSX к каноническому полю Aurora.

    Customer на step 1 указывает: какая колонка в его файле = brand /
    period / sales / channel_spend_tv / etc. Используется sidecar
    парсером для нормализации данных перед forecast.
    """

    model_config = _FROZEN

    source_column: str = Field(min_length=1, description="Имя колонки в XLSX")
    canonical_field: str = Field(
        min_length=1,
        description="Каноническое поле Aurora (brand, period, sales, channel_spend_*)",
    )


class WizardAnchorsDraft(BaseModel):
    """Draft RecipientAnchors данные собранные customer'ом на step 4.

    Похоже на RecipientAnchorsPayload из forecast_bundle.py, но wizard
    позволяет partial fill (customer ещё не закончил) — поэтому все поля
    Optional. На моменте save_bundle wizard валидирует полную форму.
    """

    model_config = _FROZEN

    market_size: float | None = None
    market_size_cv: float = Field(ge=0.0, default=0.10)
    pricing_index: float | None = None
    elasticity: float | None = None

    # Trajectory pattern picker (SO-1): customer выбирает predefined +
    # intensity 1-10 вместо ручного per-period слайдеров. Custom mode =
    # manual числа.
    planned_share_pattern: Literal["rampup", "sustain", "decline", "custom"] = "sustain"
    planned_share_intensity: int = Field(ge=1, le=10, default=5)
    planned_share_custom: list[float] | None = None  # only when pattern='custom'

    distribution_pattern: Literal["rampup", "sustain", "decline", "custom"] = "sustain"
    distribution_intensity: int = Field(ge=1, le=10, default=8)
    distribution_custom: list[float] | None = None

    has_seasonality: bool = False
    seasonality_pattern: Literal["flat", "yearly", "custom"] = "flat"
    seasonality_custom: list[float] | None = None

    @field_validator("market_size", "pricing_index", "elasticity", "market_size_cv")
    @classmethod
    def _finite_scalar(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError(f"value must be finite, got {v!r}")
        return v


class WizardSimilarityResult(BaseModel):
    """Snapshot similarity результата (chosen proxy → recipient) cached в session."""

    model_config = _FROZEN

    score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["High", "Medium", "Low", "Insufficient"]
    dimensions: dict[str, float]
    computed_at: str = Field(min_length=1, description="ISO-8601 UTC timestamp")


class WizardSession(BaseModel):
    """Полное состояние wizard сессии — persistable + restorable.

    Сохраняется в `_kv_store` под ключом `wizard.session.draft` после каждого
    значимого изменения (debounced 500ms на frontend). При sidecar restart
    customer видит recovery dialog.
    """

    model_config = _FROZEN

    session_id: str = Field(min_length=1, description="Stable UUID для wizard session")
    step: int = Field(ge=0, le=6, default=0, description="Current wizard step index")

    # Step 0: import
    imported_file_path: str | None = None
    imported_adapter_id: str | None = None
    imported_record_count: int | None = None
    imported_columns: list[str] | None = None

    # Step 1: mapping
    column_mapping: list[ColumnMapping] = Field(default_factory=list)
    mapping_done: bool = False

    # Step 2: proxy
    selected_proxy_path: str | None = None
    selected_proxy_label: str | None = None  # human-readable name

    # Step 3: similarity (cached after computation)
    similarity_result: WizardSimilarityResult | None = None

    # Step 4: anchors
    anchors_draft: WizardAnchorsDraft | None = None
    anchors_done: bool = False

    # Step 5: forecast
    forecast_handle_id: str | None = None
    forecast_completed: bool = False
    forecast_horizon: int = Field(ge=1, default=26)

    # Step 6: cert + save
    cert_signed: bool = False
    saved_bundle_path: str | None = None

    # Metadata
    created_at: str = Field(min_length=1, description="ISO-8601 UTC timestamp")
    last_saved_at: str = Field(min_length=1, description="ISO-8601 UTC timestamp")

    def is_recoverable(self) -> bool:
        """Можно ли предложить customer'у восстановить сессию?

        True если есть хоть один значимый шаг помимо нулевого (import
        finished или дальше). Empty draft (just opened wizard) — не
        предлагаем recovery, customer и так на step 0.
        """
        return self.imported_file_path is not None or self.step > 0
