"""
Локальный инструмент сборки aurora-sidecar binary для разработчиков.

Использование:
    python tools/build_sidecar.py [--skip-tests] [--debug] [--keep-dist]
                                  [--target TRIPLE] [--no-uninstall-dev]

Скрипт выполняет:
1. Определение target triple текущей платформы (или из --target)
2. Проверку / установку PyInstaller >= 6.0
3. (Опционально) удаление dev-инструментов из venv для минимального бинаря
4. Запуск PyInstaller с packaging/aurora-sidecar.spec
5. Копирование бинаря в src-tauri/binaries/aurora-sidecar-{triple}[.exe]
6. Очистку dist/ (если не --keep-dist)
7. Smoke-тест через ping/pong IPC (если не --skip-tests)

Требования: Python 3.10+, активный venv с runtime-зависимостями проекта.
Spec-файл (packaging/aurora-sidecar.spec) не изменяется — он production-ready.
"""

from __future__ import annotations

import argparse
import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

# На Windows stdout может быть cp1251 — переключаем в UTF-8 (Python 3.7+).
# Только если stdout поддерживает reconfigure (не BytesIO и т.п.).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Корень репо: родительская папка от tools/
REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Вспомогательные функции ──────────────────────────────────────────────────


def log(msg: str) -> None:
    """Печать с префиксом [build_sidecar]."""
    print(f"[build_sidecar] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    """Печать ошибки в stderr и завершение с кодом code."""
    print(f"[build_sidecar] ОШИБКА: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def detect_target_triple() -> str:
    """Определить Tauri target triple по платформе и архитектуре."""
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Windows":
        return "x86_64-pc-windows-msvc"
    if system == "Linux":
        return "x86_64-unknown-linux-gnu"
    if system == "Darwin":
        # Apple Silicon vs Intel
        if machine in ("arm64", "aarch64"):
            return "aarch64-apple-darwin"
        return "x86_64-apple-darwin"
    die(f"Неизвестная платформа: {system}. Укажите --target вручную.")
    raise SystemExit(1)  # недостижимо, для mypy


def is_ci() -> bool:
    """Вернуть True если запущено в CI окружении (CI=true)."""
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def ensure_pyinstaller() -> None:
    """Проверить наличие PyInstaller; установить если отсутствует."""
    try:
        import importlib

        importlib.import_module("PyInstaller")
        log("PyInstaller найден, установка не требуется.")
    except ImportError:
        log("PyInstaller не установлен. Устанавливаю pyinstaller>=6.0 ...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"],
            check=False,
        )
        if result.returncode != 0:
            die(
                "Не удалось установить PyInstaller. Установите вручную: pip install pyinstaller>=6.0"
            )


def uninstall_dev_tools() -> None:
    """Удалить dev-инструменты из активного venv для минимизации бинаря."""
    dev_packages = ["pytest", "pytest-cov", "hypothesis", "ruff", "mypy"]
    log(f"Удаление dev-инструментов: {', '.join(dev_packages)}")
    # subprocess без check=True — игнорируем ошибки (пакеты могут отсутствовать)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y"] + dev_packages,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        for line in result.stdout.splitlines():
            if line.strip():
                log(f"  pip: {line.strip()}")
    log("Dev-инструменты убраны (или уже отсутствовали).")


def ask_uninstall_dev() -> bool:
    """Спросить разработчика о удалении dev-инструментов."""
    print(
        "\n[build_sidecar] ВНИМАНИЕ: для минимального бинаря PyInstaller не должен\n"
        "  видеть dev-инструменты (pytest, mypy, ruff и т.д.). Скрипт может\n"
        "  удалить их из вашего venv перед сборкой.\n"
        "\n"
        "  Если вы используете этот venv для разработки — удаление сломает\n"
        "  тест-окружение. Вы можете восстановить их через:\n"
        "    pip install -e '.[dev]'\n"
        "\n"
        "  Альтернатива: передайте --no-uninstall-dev (бинарь будет немного крупнее).\n",
        flush=True,
    )
    try:
        answer = input("[build_sidecar] Удалить dev-инструменты? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # Неинтерактивный режим без CI= — безопасно пропустить
        log("Не удалось прочитать ответ. Пропускаю удаление dev-инструментов.")
        return False
    return answer in ("y", "yes", "д", "да")


def run_pyinstaller(debug_mode: bool) -> int:
    """Запустить pyinstaller с aurora-sidecar.spec. Вернуть код завершения."""
    spec_path = REPO_ROOT / "packaging" / "aurora-sidecar.spec"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_path),
        "--distpath",
        str(REPO_ROOT / "dist"),
        "--clean",
    ]
    if debug_mode:
        cmd += ["--log-level", "DEBUG"]

    log(f"Запуск PyInstaller: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


def find_built_binary() -> Path | None:
    """Найти собранный бинарь в dist/."""
    dist_dir = REPO_ROOT / "dist"
    # PyInstaller может создать aurora-sidecar.exe (Windows) или aurora-sidecar
    for candidate in ("aurora-sidecar.exe", "aurora-sidecar"):
        p = dist_dir / candidate
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def copy_binary(src: Path, target_triple: str) -> Path:
    """Скопировать бинарь в src-tauri/binaries/ с суффиксом target triple."""
    binaries_dir = REPO_ROOT / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)

    ext = ".exe" if platform.system() == "Windows" else ""
    dest_name = f"aurora-sidecar-{target_triple}{ext}"
    dest = binaries_dir / dest_name

    log(f"Копирование: {src} -> {dest}")
    shutil.copy2(str(src), str(dest))
    return dest


def run_smoke_test(binary_path: Path) -> None:
    """
    Smoke-тест: отправить ping через stdin, проверить pong в stdout.
    Использует AURORA_SIDECAR_AUTH_TOKEN из env или генерирует новый токен.
    """
    log("Запуск smoke-теста (ping → pong) ...")

    auth_token = os.environ.get("AURORA_SIDECAR_AUTH_TOKEN") or secrets.token_hex(32)
    request_json = f'{{"id":1,"method":"ping","params":{{}},"auth":"{auth_token}"}}\n'

    env = os.environ.copy()
    env["AURORA_SIDECAR_AUTH_TOKEN"] = auth_token

    try:
        proc = subprocess.Popen(
            [str(binary_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except OSError as exc:
        die(f"Не удалось запустить бинарь для smoke-теста: {exc}")

    # Audit L-1 (этап 1.7): 10s было рискованно для медленных CI-раннеров
    # (PyInstaller cold start распаковывает 200-400 MB во temp).
    # 30s по умолчанию + override через env AURORA_SMOKE_TIMEOUT.
    smoke_timeout = int(os.environ.get("AURORA_SMOKE_TIMEOUT", "30"))
    try:
        stdout_data, stderr_data = proc.communicate(
            input=request_json.encode(),
            timeout=smoke_timeout,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        die(
            f"Smoke-тест: бинарь не ответил в течение {smoke_timeout}s. "
            f"Установите AURORA_SMOKE_TIMEOUT=60 для медленных CI.",
            code=1,
        )

    response = stdout_data.decode(errors="replace")

    if '"pong"' not in response:
        stderr_text = stderr_data.decode(errors="replace").strip()
        log(f"Ответ sidecar: {response!r}")
        if stderr_text:
            log(f"Stderr sidecar: {stderr_text}")
        die("Smoke-тест ПРОВАЛЕН — в ответе нет 'pong'.", code=1)

    # Выводим первую строку ответа (не всю — может быть мусор из PyInstaller boot)
    first_line = response.strip().splitlines()[0] if response.strip() else response
    log(f"Smoke-тест пройден: {first_line}")


def print_binary_info(dest: Path, target_triple: str) -> None:
    """Напечатать итоговую информацию о бинаре."""
    size_bytes = dest.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    log("─" * 60)
    log(f"Бинарь:        {dest}")
    log(f"Target triple: {target_triple}")
    log(f"Размер:        {size_mb:.1f} MB ({size_bytes:,} байт)")

    if size_mb < 5.0:
        log(
            "ПРЕДУПРЕЖДЕНИЕ: бинарь подозрительно мал (<5 MB). Возможно, spec собрал неполный бандл."
        )

    log("─" * 60)


# ── Главная функция ──────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Локальная сборка aurora-sidecar PyInstaller binary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Пропустить smoke-тест после сборки.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Передать --log-level DEBUG в PyInstaller.",
    )
    parser.add_argument(
        "--target",
        metavar="TRIPLE",
        default=None,
        help="Переопределить target triple (по умолчанию определяется автоматически).",
    )
    parser.add_argument(
        "--keep-dist",
        action="store_true",
        help="Не удалять dist/ после копирования бинаря.",
    )
    parser.add_argument(
        "--no-uninstall-dev",
        action="store_true",
        help="Пропустить удаление dev-инструментов (бинарь будет крупнее).",
    )
    args = parser.parse_args()

    # ── Шаг 1: определить target triple ─────────────────────────────────────
    target_triple = args.target or detect_target_triple()
    log(f"Target triple: {target_triple}")

    # ── Шаг 2: убедиться в наличии PyInstaller ──────────────────────────────
    ensure_pyinstaller()

    # ── Шаг 3: обработка dev-инструментов ───────────────────────────────────
    if args.no_uninstall_dev:
        log("--no-uninstall-dev: пропускаю удаление dev-инструментов. Бинарь может быть крупнее.")
    elif is_ci():
        log("CI-режим обнаружен (CI=true): автоматически удаляю dev-инструменты.")
        uninstall_dev_tools()
    else:
        if ask_uninstall_dev():
            uninstall_dev_tools()
        else:
            log("Пропускаю удаление dev-инструментов по выбору разработчика.")

    # ── Шаг 4: запустить PyInstaller ────────────────────────────────────────
    log("Начинаю сборку через PyInstaller ...")
    rc = run_pyinstaller(debug_mode=args.debug)
    if rc != 0:
        die(f"PyInstaller завершился с кодом {rc}.", code=rc)

    # ── Шаг 5: найти собранный бинарь ───────────────────────────────────────
    built = find_built_binary()
    if built is None:
        die(
            "Бинарь не найден в dist/ после сборки. Проверьте вывод PyInstaller выше.",
            code=2,
        )
    log(f"Собранный бинарь: {built} ({built.stat().st_size / 1024 / 1024:.1f} MB)")

    # ── Шаг 6: скопировать в src-tauri/binaries/ ────────────────────────────
    dest = copy_binary(built, target_triple)

    # ── Шаг 7: удалить dist/ если не --keep-dist ────────────────────────────
    dist_dir = REPO_ROOT / "dist"
    if not args.keep_dist:
        log(f"Удаляю dist/ ({dist_dir}) ...")
        shutil.rmtree(dist_dir, ignore_errors=True)
    else:
        log(f"--keep-dist: dist/ сохранён ({dist_dir}).")

    # ── Шаг 8: smoke-тест ───────────────────────────────────────────────────
    if not args.skip_tests:
        run_smoke_test(dest)
    else:
        log("--skip-tests: smoke-тест пропущен.")

    # ── Финальный отчёт ──────────────────────────────────────────────────────
    print_binary_info(dest, target_triple)


if __name__ == "__main__":
    main()
