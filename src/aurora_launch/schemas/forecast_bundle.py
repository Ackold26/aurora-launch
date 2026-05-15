"""Канонический формат forecast.json внутри .aurora bundle.

Контракт между сидекаром (writer) и Inspector / Reproduce-Python (reader).

До v0.1.0 GA: forecast.json пиcaлся только в тестах (test_phase_2_smart_diff).
Production wizard вообще не сохранял прогноз в bundle, поэтому Inspector B-5
fix («real n_recipient из forecast.json») в проде возвращал None.

С версии v0.1.1 (этап 1 ROADMAP_POST_V0_1_0, пункт 1.3) сидекар умеет
composing forecast.json из state мастера и пишет его в bundle вместе с
anchors + spend_plan, чтобы M-09 Reproduce-Python смог точно воспроизвести
прогноз.

Schema versioning:
- `version="1"` — текущий формат (этот файл).
- Legacy bundles до v0.1.1 не имеют `version` поля — loader детектит и
  читает как v0 (anchors=None, spend_plan=None, n_recipient может быть 0).
"""

from __future__ import annotations

import json
import math
from typing import Any, Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_FROZEN = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


def _reject_non_finite(value: float, *, name: str) -> float:
    """Audit A-1 (этап 1.7): reject NaN / +-Inf на write пути.

    Python json.dumps по умолчанию принимает NaN/Inf и кодирует как
    'NaN'/'Infinity' — это **invalid JSON** по RFC 8259 (никакой JS-клиент
    или другой язык не распарсит). rfc8785 (JCS canonical) ещё строже:
    FloatDomainError. Принимая non-finite на write пути, bundle становится
    не-хешируемым (canonical падает) и не-парсящимся JS-стороной.
    """
    if not math.isfinite(value):
        raise ValueError(f"{name}={value!r} must be finite (NaN/Infinity не сохраняются)")
    return value


# Зеркало RecipientAnchors из engines/pure_transfer_engine.py, но как
# отдельная сериализуемая модель — bundle schema не должна импортировать
# math-движок (избегаем циклов + позволяем читать bundle без numpy/scipy).
class RecipientAnchorsPayload(BaseModel):
    """Поля RecipientAnchors в форме, пригодной для JSON-bundle."""

    model_config = _FROZEN

    market_size: float = Field(gt=0)
    market_size_cv: float = Field(ge=0, default=0.10)
    planned_share_trajectory: list[float] = Field(min_length=1)
    distribution_trajectory: list[float] = Field(min_length=1)
    pricing_index: float = Field(gt=0)
    elasticity: float = Field(ge=0)
    seasonality: list[float] | None = None

    @field_validator("market_size", "market_size_cv", "pricing_index", "elasticity")
    @classmethod
    def _scalar_finite(cls, v: float) -> float:
        return _reject_non_finite(v, name="anchors scalar")

    @field_validator("planned_share_trajectory", "distribution_trajectory", "seasonality")
    @classmethod
    def _trajectory_finite(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        for i, x in enumerate(v):
            _reject_non_finite(x, name=f"anchors trajectory[{i}]")
        return v

    @model_validator(mode="after")
    def _trajectory_lengths_match(self) -> RecipientAnchorsPayload:
        if len(self.planned_share_trajectory) != len(self.distribution_trajectory):
            raise ValueError(
                f"planned_share_trajectory ({len(self.planned_share_trajectory)}) "
                f"and distribution_trajectory ({len(self.distribution_trajectory)}) "
                f"must have same length"
            )
        if self.seasonality is not None and len(self.seasonality) != len(
            self.planned_share_trajectory
        ):
            raise ValueError(
                f"seasonality length {len(self.seasonality)} ≠ trajectory length "
                f"{len(self.planned_share_trajectory)}"
            )
        for x in self.planned_share_trajectory:
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"planned_share value {x} out of [0, 1]")
        for x in self.distribution_trajectory:
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"distribution value {x} out of [0, 1]")
        return self


class ForecastPoint(BaseModel):
    """Одна точка прогноза. `week_index` — period-index (для monthly granularity
    это month-index; имя оставлено из legacy совместимости с Inspector reader)."""

    model_config = _FROZEN

    week_index: int = Field(ge=0)
    point: float
    ci_lower: float
    ci_upper: float

    @field_validator("point", "ci_lower", "ci_upper")
    @classmethod
    def _finite_value(cls, v: float) -> float:
        return _reject_non_finite(v, name="forecast point")

    @model_validator(mode="after")
    def _ci_ordering(self) -> ForecastPoint:
        if not (self.ci_lower <= self.point <= self.ci_upper):
            raise ValueError(
                f"CI ordering broken at week_index={self.week_index}: "
                f"ci_lower={self.ci_lower} ≤ point={self.point} ≤ ci_upper={self.ci_upper}"
            )
        return self


EngineMode = Literal[
    "pure_transfer",
    "transfer_with_bias_check",
    "ols_with_proxy_priors",
    "bayesian_with_proxy_priors",
]

Granularity = Literal["monthly", "weekly"]


class ForecastJsonV1(BaseModel):
    """Канонический формат forecast.json — v1."""

    model_config = _FROZEN

    version: Literal["1"] = "1"
    horizon_weeks: int = Field(ge=1)
    granularity: Granularity = "monthly"
    engine_mode: EngineMode = "pure_transfer"
    methodology_signature: str = ""
    n_recipient: int = Field(ge=0, default=0)
    weekly_points: list[ForecastPoint] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    # Новые поля v1 (по сравнению с legacy / тестовым форматом)
    anchors: RecipientAnchorsPayload | None = None
    spend_plan: dict[str, list[float]] | None = None

    coverage_target: float = Field(ge=0.0, le=1.0, default=0.95)
    seed: int = 42

    # Observability — НЕ участвует в canonical hash (см. to_canonical_bytes).
    # ISO-8601 UTC с суффиксом Z, заполняется писателем (None в тестах).
    produced_at: str | None = None

    @field_validator("spend_plan")
    @classmethod
    def _spend_plan_finite(
        cls, v: dict[str, list[float]] | None
    ) -> dict[str, list[float]] | None:
        """Audit B-1 (этап 1.7 Sonnet): spend_plan был пропущен в A-1 fix.
        NaN/Inf в any канале → невалидный JSON + FloatDomainError на canonical hash.
        """
        if v is None:
            return v
        for channel, values in v.items():
            for i, x in enumerate(values):
                _reject_non_finite(x, name=f"spend_plan[{channel!r}][{i}]")
        return v

    @model_validator(mode="after")
    def _points_match_horizon(self) -> ForecastJsonV1:
        if len(self.weekly_points) != self.horizon_weeks:
            raise ValueError(
                f"horizon_weeks={self.horizon_weeks} ≠ len(weekly_points)={len(self.weekly_points)}"
            )
        if self.anchors is not None:
            traj_len = len(self.anchors.planned_share_trajectory)
            if traj_len != self.horizon_weeks:
                raise ValueError(
                    f"anchors.planned_share_trajectory length {traj_len} ≠ horizon_weeks {self.horizon_weeks}"
                )
        if self.spend_plan is not None:
            for ch, values in self.spend_plan.items():
                if len(values) != self.horizon_weeks:
                    raise ValueError(
                        f"spend_plan[{ch!r}] length {len(values)} ≠ horizon_weeks {self.horizon_weeks}"
                    )
        return self

    def to_canonical_bytes(self) -> bytes:
        """JCS RFC-8785 canonical serialization для stable cross-machine hash.

        `produced_at` исключается из canonical — это observability метка,
        не участвует в reproducibility. Без exclusion bundle byte-identity
        тестов сломалась бы при разнице timestamp'ов между runs (см.
        feedback_bundle_byte_identity_observability_exclusion.md).
        """
        data = self.model_dump(mode="json", exclude={"produced_at"})
        return rfc8785.dumps(data)

    def to_bundle_bytes(self) -> bytes:
        """Pretty-printed JSON (с produced_at) для записи в .aurora bundle.

        Это не canonical — используем для human-readability при `unzip` +
        `cat forecast.json`. Hashing использует to_canonical_bytes().
        """
        data = self.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def load_forecast_json(blob: bytes) -> ForecastJsonV1:
    """Прочитать forecast.json bytes с backwards-compat для legacy bundles.

    Legacy формат (до v0.1.1 + test_phase_2_smart_diff fixture):
    - Нет `version` поля → assume v0
    - Нет `anchors` / `spend_plan` → None в результате
    - Может не быть `methodology_signature` / `warnings` → defaults
    - Может не быть `n_recipient` / `granularity` → defaults (0, "monthly")
    - `engine_mode` может отсутствовать или быть legacy строкой → defaults

    Любой `extra` ключ из legacy блоба игнорируется (НЕ raise),
    потому что иначе модель с extra="forbid" не примет старые файлы.
    """
    data = json.loads(blob.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"forecast.json root must be object, got {type(data).__name__}")

    raw_version = data.get("version")

    # Legacy-detect: нет `version` ключа → v0 → нужно нормализовать
    if raw_version is None:
        data = _normalize_legacy_to_v1(data)
    elif raw_version != "1":
        # Audit A-2 (этап 1.7): защита от future major-version bundles.
        # Без явной проверки model_validate упадёт с непонятной ошибкой про
        # extra-field; здесь даём осмысленное сообщение клиенту.
        raise ValueError(
            f"forecast.json version={raw_version!r} не поддерживается этим Aurora Launch "
            f"(понимаю только version='1'). Обновите Aurora Launch до новой версии."
        )

    return ForecastJsonV1.model_validate(data)


def _normalize_legacy_to_v1(legacy: dict[str, Any]) -> dict[str, Any]:
    """Привести legacy forecast.json к форме v1 с минимальными изменениями.

    Эвристики:
    - Проставить `version="1"`.
    - Заполнить defaults для отсутствующих обязательных полей.
    - Сохранить `weekly_points` как есть.
    - Отбросить extra ключи, которые не входят в схему v1 (чтобы model
      с extra="forbid" не raise).
    """
    allowed_keys = set(ForecastJsonV1.model_fields.keys())
    normalized: dict[str, Any] = {}
    for k, v in legacy.items():
        if k in allowed_keys:
            normalized[k] = v
    normalized["version"] = "1"
    # Дефолты для обязательных полей если legacy их не включает
    normalized.setdefault("granularity", "monthly")
    normalized.setdefault("engine_mode", "pure_transfer")
    normalized.setdefault("methodology_signature", "")
    normalized.setdefault("n_recipient", 0)
    normalized.setdefault("warnings", [])
    # Audit H-3 (этап 1.7): legacy `engine_mode` может быть из older codebase,
    # сейчас не входить в текущий Literal. Без graceful fallback Pydantic
    # выдаст невнятный `literal_error` про конкретные строки. Заменяем
    # на pure_transfer по умолчанию + warning в самом bundle.
    _KNOWN_ENGINE_MODES = {
        "pure_transfer",
        "transfer_with_bias_check",
        "ols_with_proxy_priors",
        "bayesian_with_proxy_priors",
    }
    if normalized["engine_mode"] not in _KNOWN_ENGINE_MODES:
        legacy_mode = normalized["engine_mode"]
        normalized["engine_mode"] = "pure_transfer"
        warnings_list = list(normalized.get("warnings", []))
        warnings_list.append(
            f"Legacy bundle had unknown engine_mode={legacy_mode!r}, "
            f"normalised to 'pure_transfer'. Reproducibility limited."
        )
        normalized["warnings"] = warnings_list
    # horizon_weeks — обязательно. Если нет → derive из weekly_points
    if "horizon_weeks" not in normalized and "weekly_points" in normalized:
        normalized["horizon_weeks"] = len(normalized["weekly_points"])
    return normalized


def compose_forecast_json_bytes(
    *,
    horizon_weeks: int,
    weekly_points: list[dict[str, Any]],
    engine_mode: EngineMode = "pure_transfer",
    granularity: Granularity = "monthly",
    methodology_signature: str = "",
    n_recipient: int = 0,
    warnings: list[str] | None = None,
    anchors: dict[str, Any] | None = None,
    spend_plan: dict[str, list[float]] | None = None,
    coverage_target: float = 0.95,
    seed: int = 42,
    produced_at: str | None = None,
) -> bytes:
    """Один-shot helper: построить ForecastJsonV1 + сериализовать в bundle bytes.

    Используется sidecar method `compose_forecast_json` (см. methods.py).
    Все поля валидируются через Pydantic — если frontend передал кривой
    payload, raise ValidationError, sidecar возвращает 400-эквивалент.
    """
    payload = ForecastJsonV1(
        horizon_weeks=horizon_weeks,
        weekly_points=[ForecastPoint.model_validate(p) for p in weekly_points],
        engine_mode=engine_mode,
        granularity=granularity,
        methodology_signature=methodology_signature,
        n_recipient=n_recipient,
        warnings=list(warnings or []),
        anchors=RecipientAnchorsPayload.model_validate(anchors) if anchors else None,
        spend_plan=spend_plan,
        coverage_target=coverage_target,
        seed=seed,
        produced_at=produced_at,
    )
    return payload.to_bundle_bytes()
