"""Сторожа INV-50 для устаревшего пути расчёта прогноза.

Внешний аудит 2026-07-30 (два High):

1. Устаревший путь (`methods_forecast.py`, ветка legacy prior-predictive)
   испускал `forecast_completed` БЕЗ ключа `forecast`. Фронт (мастер) в этом
   случае подставлял `engine_mode: 'pure_transfer'` и пустую сигнатуру, и
   инспектор печатал клиенту «прогноз построен методом переноса, без
   сэмплирования». Ложны оба утверждения: переноса не было, а выборка была
   (`prior_predictive_samples_real(n_samples=50)`, CI по 2,5/97,5 процентилям).
   Предпосылка не редкая: мастер зовёт `start_forecast` со свежим
   `crypto.randomUUID()` (`frontend/src/routes/wizard/+page.svelte`), которого в
   ProjectDB заведомо нет, — значит устаревший путь брался КАЖДЫЙ раз.

2. Честная ветка «метод расчёта не указан» была недостижима для бандлов,
   которые пишет сам продукт: `engine_mode` не допускал null, поэтому писателю
   нечем было сказать «режим неизвестен», кроме подстановки чужого режима.

Тесты ниже сторожат обе стороны: эмиссию сигнатуры устаревшим путём и запись
`engine_mode: null` в forecast.json через боевой sidecar-метод.

Изоляция: ProjectDB создаётся под `tmp_path` (фикстура ниже повторяет
`isolated_sidecar_db` из test_phase_pi_3d_e2e_integration.py) — ни один тест не
пишет в профиль пользователя.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest


@pytest.fixture
def isolated_sidecar_db(tmp_path, monkeypatch):
    """ProjectDB-синглтон на изолированном незашифрованном файле под tmp_path."""
    db_dir = tmp_path / "aurora_data"
    db_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURORA_PROJECT_DB_PATH", str(db_dir))

    import aurora_launch.sidecar.methods as _methods_mod

    _methods_mod._PROJECT_DB = None

    def _get_plain_db():
        if _methods_mod._PROJECT_DB is not None:
            return _methods_mod._PROJECT_DB
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB

        blobs_dir = db_dir / "blobs"
        blobs_dir.mkdir(parents=True, exist_ok=True)
        db = ProjectDB(db_dir / "projects.db", BlobStore(blobs_dir))  # no encryption_key
        _methods_mod._PROJECT_DB = db
        return _methods_mod._PROJECT_DB

    monkeypatch.setattr(_methods_mod, "_get_project_db", _get_plain_db)

    yield tmp_path

    if _methods_mod._PROJECT_DB is not None:
        try:
            _methods_mod._PROJECT_DB.close()
        except Exception:  # noqa: BLE001 — cleanup best-effort
            pass
    _methods_mod._PROJECT_DB = None


def _run_legacy_forecast(monkeypatch, *, horizon_weeks: int = 3) -> list[tuple[str, dict]]:
    """Прогнать start_forecast по устаревшему пути и вернуть все события.

    `project_id` заведомо отсутствует в ProjectDB — ровно то, что делает мастер
    со своим случайным UUID.
    """
    emitted: list[tuple[str, dict]] = []

    from aurora_launch.sidecar import events as _events_mod

    monkeypatch.setattr(
        _events_mod,
        "emit",
        lambda name, params: emitted.append((name, params)),
    )

    from aurora_launch.sidecar.methods import dispatch

    result = dispatch(
        "start_forecast",
        {
            "project_id": "no-such-project-in-db-2026-07-30",
            "horizon_weeks": horizon_weeks,
            "seed": 42,
        },
    )

    import aurora_launch.sidecar.methods as _methods_mod

    thread = _methods_mod._forecast_threads.get(result["forecast_handle"])
    if thread is not None:
        thread.join(timeout=30.0)
        assert not thread.is_alive(), "поток прогноза не завершился за 30 с"

    return emitted


class TestLegacyPathAnnouncesItsOwnMethod:
    """Устаревший путь обязан называть себя, а не молчать."""

    def test_legacy_completed_event_carries_own_signature(
        self, isolated_sidecar_db, monkeypatch
    ):
        emitted = _run_legacy_forecast(monkeypatch)

        completed = [params for name, params in emitted if name == "forecast_completed"]
        assert completed, f"устаревший путь не дошёл до completed: {[n for n, _ in emitted]}"

        payload = completed[0]
        assert payload.get("path") == "legacy_prior_predictive", (
            "тест ловит не тот путь расчёта — проверьте фикстуру project_id"
        )

        summary = payload.get("forecast")
        assert summary is not None, (
            "forecast_completed устаревшего пути снова без сводки — фронту нечего "
            "записать в forecast.json, и он вернётся к подстановке чужого режима"
        )
        assert summary["methodology_signature"] == "legacy_prior_predictive_v1", (
            f"сигнатура устаревшего пути изменилась: {summary['methodology_signature']!r}. "
            "Клиентский текст оговорки подобран по префиксу legacy_prior_predictive "
            "(frontend/src/lib/components/inspector/ForecastTab.svelte)"
        )

    def test_legacy_summary_does_not_substitute_engine_mode(
        self, isolated_sidecar_db, monkeypatch
    ):
        """У устаревшего пути нет режима из EngineMode — только null.

        Любое из четырёх значений здесь было бы ложью о методе: переноса не
        было, регрессии по данным клиента не было, байеса не было.
        """
        emitted = _run_legacy_forecast(monkeypatch)
        summary = next(
            params["forecast"]
            for name, params in emitted
            if name == "forecast_completed" and params.get("forecast")
        )

        assert summary["engine_mode"] is None, (
            f"устаревший путь подставил режим {summary['engine_mode']!r} — "
            "это заявка клиенту о методе, который не исполнялся"
        )
        assert "granularity" not in summary, (
            "устаревший путь считает безымянные периоды — подставленная "
            "гранулярность была бы такой же неизмеренной величиной"
        )

    def test_legacy_summary_points_match_progress_events(
        self, isolated_sidecar_db, monkeypatch
    ):
        """Сводка описывает тот же прогноз, что уехал в progress-события."""
        emitted = _run_legacy_forecast(monkeypatch, horizon_weeks=3)
        progress = [params for name, params in emitted if name == "forecast_progress"]
        summary = next(
            params["forecast"]
            for name, params in emitted
            if name == "forecast_completed" and params.get("forecast")
        )

        assert summary["horizon_periods"] == len(progress) == 3
        assert [p["point_forecast"] for p in summary["points"]] == [
            p["point_forecast"] for p in progress
        ]


class TestUnknownEngineModeReachesTheBundle:
    """«Режим неизвестен» обязан доезжать до forecast.json как null."""

    def _compose(self, params: dict[str, Any]) -> dict[str, Any]:
        from aurora_launch.sidecar.methods import dispatch

        base: dict[str, Any] = {
            "horizon_weeks": 2,
            "weekly_points": [
                {"week_index": 0, "point": 1000.0, "ci_lower": 900.0, "ci_upper": 1100.0},
                {"week_index": 1, "point": 1050.0, "ci_lower": 940.0, "ci_upper": 1160.0},
            ],
        }
        base.update(params)
        result = dispatch("compose_forecast_json", base)
        blob = base64.b64decode(result["forecast_json_base64"])
        return json.loads(blob.decode("utf-8"))

    def test_null_engine_mode_written_as_null(self):
        """Писатель передал null — в файле обязан быть null, не 'pure_transfer'.

        Это ровно тот бандл, который производит мастер после устаревшего пути:
        сигнатура есть, режима нет.
        """
        written = self._compose(
            {"engine_mode": None, "methodology_signature": "legacy_prior_predictive_v1"}
        )

        assert written["engine_mode"] is None, (
            f"неизвестный режим записан как {written['engine_mode']!r} — "
            "инспектор объявит клиенту метод, которого не было"
        )
        assert written["methodology_signature"] == "legacy_prior_predictive_v1"

    def test_null_engine_mode_survives_read_back(self):
        """Чтение бандла не подменяет null дефолтом."""
        from aurora_launch.schemas.forecast_bundle import load_forecast_json

        written = self._compose({"engine_mode": None})
        loaded = load_forecast_json(json.dumps(written).encode("utf-8"))

        assert loaded.engine_mode is None

    def test_absent_key_still_defaults_to_pure_transfer(self):
        """Обратная совместимость: не передал ключ — прежнее поведение."""
        written = self._compose({})

        assert written["engine_mode"] == "pure_transfer"
